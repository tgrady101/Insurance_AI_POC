import os
import csv
import sys
import json
import requests
from datetime import datetime
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage
from markdownify import markdownify as md
from bs4 import BeautifulSoup
import re
import google.generativeai as genai

# --- Configuration ---
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
DATA_STORE_ID = "insurance-filings-full"
GCS_BUCKET_NAME = f"{GCP_PROJECT_ID}-filings-bucket"
DATA_STORE_LOCATION = "global"
OUTPUT_DIR = "downloaded_reports"
CHUNKED_DIR = "chunked_reports"

# Chunking configuration (token-based using Gemini tokenizer)
MAX_CHUNK_TOKENS = 2000    # Target tokens per chunk for optimal AI context
CHUNK_OVERLAP_TOKENS = 50  # Token overlap between chunks for context continuity

# Initialize Gemini model for tokenization
_tokenizer_model = None

def get_tokenizer():
    """Get or initialize the Gemini tokenizer model."""
    global _tokenizer_model
    if _tokenizer_model is None:
        _tokenizer_model = genai.GenerativeModel('gemini-1.5-flash')
        print("  -> Initialized Gemini tokenizer")
    return _tokenizer_model

def count_tokens(text: str) -> int:
    """Count tokens in text using Gemini's tokenizer."""
    if not text:
        return 0
    try:
        model = get_tokenizer()
        result = model.count_tokens(text)
        return result.total_tokens
    except Exception as e:
        # Fallback to character-based estimate if API fails
        print(f"  -> Warning: Tokenizer API failed ({e}), using estimate")
        return len(text) // 4  # ~4 chars per token fallback

def chunk_text_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """
    Split text into chunks based on actual token count.
    Uses binary search to find optimal chunk boundaries that respect token limits.
    """
    if not text.strip():
        return []
    
    # If text fits in one chunk, return as-is
    if count_tokens(text) <= max_tokens:
        return [text]
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        # Binary search for the maximum end position that fits in max_tokens
        low = start + 1
        high = min(start + max_tokens * 6, text_len)  # Estimate: ~6 chars/token max
        best_end = start + 100  # Minimum chunk size
        
        while low <= high:
            mid = (low + high) // 2
            chunk_candidate = text[start:mid]
            tokens = count_tokens(chunk_candidate)
            
            if tokens <= max_tokens:
                best_end = mid
                low = mid + 1
            else:
                high = mid - 1
        
        # Try to break at a sentence or word boundary
        chunk_text = text[start:best_end]
        
        # Look for natural break points (sentence end, paragraph, word boundary)
        if best_end < text_len:
            search_start = int(len(chunk_text) * 0.8)
            break_chars = ['. ', '.\n', '\n\n', '\n', ' ']
            
            for break_char in break_chars:
                last_break = chunk_text.rfind(break_char, search_start)
                if last_break > search_start:
                    chunk_text = chunk_text[:last_break + len(break_char)]
                    best_end = start + len(chunk_text)
                    break
        
        chunks.append(chunk_text.strip())
        
        # Move start position, accounting for overlap
        if overlap_tokens > 0 and best_end < text_len:
            overlap_chars = overlap_tokens * 4  # Estimate for overlap positioning
            overlap_start = max(start, best_end - overlap_chars)
            start = overlap_start
        else:
            start = best_end
        
        # Safety check to prevent infinite loop
        if start >= text_len or (len(chunks) > 1 and chunks[-1] == chunks[-2]):
            break
    
    return chunks

# Note: Vertex AI Search automatically generates embeddings during document import.
# Manual embedding generation is not supported and not needed.

# --- Helper Functions ---

def sanitize_document_id(doc_id):
    """
    Sanitize document ID to match Vertex AI pattern: [a-zA-Z0-9-_]*
    Replaces all invalid characters with underscores.
    """
    # Replace common invalid characters
    sanitized = doc_id.replace('.', '_').replace('#', '_').replace('(', '').replace(')', '')
    sanitized = sanitized.replace('|', '_').replace(',', '_').replace('&', '_')
    # Remove any remaining invalid characters (anything not alphanumeric, hyphen, or underscore)
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', sanitized)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized

# --- Main Functions ---

def truncate_gcs_bucket():
    """Deletes all objects from the configured GCS bucket."""
    print("\n--- Truncating GCS Bucket ---")
    gcs_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = gcs_client.bucket(GCS_BUCKET_NAME)
    
    blobs = list(bucket.list_blobs())
    if not blobs:
        print("  -> Bucket is already empty.")
        return
    
    print(f"  -> Found {len(blobs)} objects to delete.")
    for blob in blobs:
        try:
            blob.delete()
        except Exception as e:
            print(f"  -> ERROR: Failed to delete {blob.name}. Reason: {e}")
    
    print("  -> GCS bucket truncation complete.")

def truncate_vertex_ai_datastore():
    """Purges all documents from the Vertex AI data store."""
    print("\n--- Truncating Vertex AI Data Store ---")
    discovery_client = discoveryengine.DocumentServiceClient()
    
    parent = discovery_client.branch_path(
        project=GCP_PROJECT_ID,
        location=DATA_STORE_LOCATION,
        data_store=DATA_STORE_ID,
        branch="default_branch",
    )
    
    request = discoveryengine.PurgeDocumentsRequest(
        parent=parent,
        filter="*",  # Purge all documents
        force=True,
    )
    
    try:
        operation = discovery_client.purge_documents(request=request)
        print("  -> Successfully sent purge request.")
        print(f"  -> Operation Name: {operation.operation.name}")
        print("  -> Waiting for purge operation to complete...")
        response = operation.result(timeout=300)  # Wait up to 5 minutes
        print(f"  -> Purged {response.purge_count} documents from data store.")
        print("  -> Vertex AI data store truncation complete.")
    except Exception as e:
        print(f"  -> ERROR: Failed to purge Vertex AI data store. Reason: {e}")
        print("  -> Continuing with the workflow...")

def fetch_company_reports(company_info, start_year):
    """Fetches 10-K and 10-Q reports for a single US company."""
    cik = company_info.get('CIK')
    ticker = company_info.get('Ticker', 'UNKNOWN')

    if not cik or cik == 'N/A':
        print(f"  -> Skipping {company_info.get('Company')} (missing CIK).")
        return []

    print(f"  -> Fetching reports for {ticker} (CIK: {cik})...")
    
    headers = {'User-Agent': f'{GCP_PROJECT_ID} tgrady101@example.com'}
    cik_padded = str(cik).zfill(10)
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    
    try:
        response = requests.get(submissions_url, headers=headers)
        response.raise_for_status()
        submissions = response.json()
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
            print(f"  -> INFO: SEC API returned 404 Not Found for CIK {cik}. The data may not be available via this API. Skipping.")
        else:
            print(f"  -> ERROR: Could not fetch submissions for {ticker}. Reason: {e}")
        return []

    saved_files = []
    filings = submissions['filings']['recent']
    
    for i in range(len(filings['form'])):
        filing_date_str = filings['filingDate'][i]
        filing_year = int(filing_date_str.split('-')[0])
        form_type = filings['form'][i]

        if form_type in ['10-K', '10-Q'] and filing_year >= start_year:
            accession_num = filings['accessionNumber'][i]
            primary_doc = filings['primaryDocument'][i]
            
            filename = f"{ticker}_{form_type}_{filing_date_str}.html"
            filepath = os.path.join(OUTPUT_DIR, filename)

            if os.path.exists(filepath):
                saved_files.append(filepath)
                continue

            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_num.replace('-', '')}/{primary_doc}"
            
            try:
                doc_response = requests.get(doc_url, headers=headers)
                doc_response.raise_for_status()
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(doc_response.text)
                saved_files.append(filepath)

            except requests.exceptions.RequestException as e:
                print(f"  -> WARNING: Failed to download doc for {ticker} ({filing_date_str}). Reason: {e}")
    
    print(f"  -> Completed for {ticker}. Found/Downloaded {len(saved_files)} files.")
    return saved_files

def chunk_documents(local_file_paths):
    """Chunks HTML files, saves to disk, and converts to Document objects for import.
    
    Note: Vertex AI Search automatically generates embeddings during import.
    """
    print("\n--- Step 2: Chunking Documents ---")
    
    all_chunks = []
    for file_path in local_file_paths:
        chunks = create_document_chunks(file_path)
        all_chunks.extend(chunks)
    
    if not all_chunks:
        print("  -> No chunks were created.")
        return None
    
    print(f"  -> Total chunks created: {len(all_chunks)}")
    
    # Save chunks to disk
    os.makedirs(CHUNKED_DIR, exist_ok=True)
    chunk_file = os.path.join(CHUNKED_DIR, f"chunks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    # Convert Document objects to serializable format for saving
    chunks_data = []
    for chunk in all_chunks:
        chunk_dict = {
            "id": chunk.id,
            "struct_data": dict(chunk.struct_data),
            "content": {
                "mime_type": chunk.content.mime_type,
                "raw_bytes": chunk.content.raw_bytes.decode('utf-8') if chunk.content.raw_bytes else ""
            }
        }
        chunks_data.append(chunk_dict)
    
    with open(chunk_file, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2)
    
    print(f"  -> Saved {len(all_chunks)} chunks to {chunk_file}")
    
    return chunk_file

def load_chunks_from_file(chunk_file):
    """Loads chunks from JSON file and converts to Document objects.
    
    Note: Vertex AI Search automatically generates embeddings during import.
    """
    print(f"\n--- Loading Chunks from {os.path.basename(chunk_file)} ---")
    
    with open(chunk_file, 'r', encoding='utf-8') as f:
        chunks_data = json.load(f)
    
    document_chunks = []
    for chunk_data in chunks_data:
        # Build the document
        doc = discoveryengine.Document(
            id=chunk_data["id"],
            struct_data=chunk_data["struct_data"],
            content=discoveryengine.Document.Content(
                mime_type=chunk_data["content"]["mime_type"],
                raw_bytes=chunk_data["content"]["raw_bytes"].encode('utf-8')
            )
        )
        document_chunks.append(doc)
    
    print(f"  -> Loaded {len(document_chunks)} chunks from file")
    
    return document_chunks

def extract_metadata_from_filename(filename):
    """Extract company ticker, form type, and filing date from filename."""
    # Expected format: TICKER_FORM_DATE.html
    parts = filename.replace('.html', '').split('_')
    if len(parts) >= 3:
        ticker = parts[0]
        form_type = parts[1]
        filing_date = parts[2]
        
        # Parse date for better filtering
        try:
            date_obj = datetime.strptime(filing_date, '%Y-%m-%d')
            year = date_obj.year
            
            # Determine quarter from filing date for 10-Q filings
            # 10-Q filings are due 40-45 days after quarter end
            if form_type == '10-Q':
                month = date_obj.month
                if month <= 5:  # Filed by May → Q1 (ended March 31)
                    quarter = "Q1"
                elif month <= 8:  # Filed by August → Q2 (ended June 30)
                    quarter = "Q2"
                elif month <= 11:  # Filed by November → Q3 (ended September 30)
                    quarter = "Q3"
                else:  # Filed in December → late Q3 filing
                    quarter = "Q3"
            else:
                quarter = "N/A"  # 10-K is annual, no quarter
        except:
            year = None
            quarter = "N/A"
        
        return {
            "ticker": ticker,
            "form_type": form_type,
            "filing_date": filing_date,
            "year": year,
            "quarter": quarter,
            "document_type": "SEC Filing",
            "industry": "Insurance"  # You can enhance this with company lookup
        }
    return {
        "ticker": "UNKNOWN",
        "form_type": "UNKNOWN",
        "filing_date": "UNKNOWN",
        "year": None,
        "quarter": "N/A",
        "document_type": "SEC Filing",
        "industry": "Insurance"
    }

def clean_text(text):
    """Clean and normalize text for better AI comprehension."""
    # Remove excessive whitespace
    text = re.sub(r' +', ' ', text)
    # Remove multiple consecutive newlines (but preserve table structure)
    text = re.sub(r'\n{4,}', '\n\n', text)
    return text.strip()

def extract_and_format_tables(soup):
    """
    Extract tables and add contextual information for better AI comprehension.
    Returns a mapping of table positions to formatted table strings.
    """
    tables = soup.find_all('table')
    table_contexts = {}
    
    for idx, table in enumerate(tables):
        # Look for table caption or preceding header
        caption = table.find('caption')
        if caption:
            table_title = caption.get_text(strip=True)
        else:
            # Look for a header element immediately before the table
            prev_sibling = table.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'b', 'strong'])
            if prev_sibling and len(prev_sibling.get_text(strip=True)) < 200:
                table_title = prev_sibling.get_text(strip=True)
            else:
                table_title = f"Table {idx + 1}"
        
        # Convert table to markdown
        table_md = md(str(table), heading_style="ATX")
        
        # Add context wrapper
        formatted_table = f"\n\n### {table_title}\n\n{table_md}\n\n"
        
        # Mark the table position
        table_marker = f"<!--TABLE_{idx}-->"
        table.insert_before(soup.new_string(table_marker))
        table_contexts[table_marker] = formatted_table
    
    return table_contexts

def generate_chunk_summary(content, section_title):
    """Generate a brief summary/description of the chunk for better AI context."""
    # Extract first meaningful sentence or paragraph
    lines = content.split('\n')
    summary_lines = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and len(line) > 20:
            summary_lines.append(line)
            if len(' '.join(summary_lines)) > 200:
                break
    
    summary = ' '.join(summary_lines)[:250]
    return f"{section_title}: {summary}" if summary else section_title

def split_large_chunk(content: str, max_tokens: int = MAX_CHUNK_TOKENS, overlap_tokens: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
    """
    Split large content into smaller chunks using token-based sizing with overlap.
    Uses the Gemini tokenizer for accurate token counting.
    
    Args:
        content: Text content to split
        max_tokens: Maximum tokens per chunk (default: MAX_CHUNK_TOKENS)
        overlap_tokens: Token overlap between chunks (default: CHUNK_OVERLAP_TOKENS)
    
    Returns:
        List of text chunks, each under max_tokens
    """
    content_tokens = count_tokens(content)
    if content_tokens <= max_tokens:
        return [content]
    
    # Use the token-based chunking function
    return chunk_text_by_tokens(content, max_tokens, overlap_tokens)

def create_document_chunks(file_path):
    """
    Parses an HTML 10-K/10-Q filing, splitting it by "Item" sections and converting
    tables to Markdown for better comprehension by the LLM.
    Returns a list of chunk dictionaries optimized for AI context.
    """
    print(f"  -> Chunking file: {os.path.basename(file_path)}")
    
    # Extract metadata from filename
    metadata = extract_metadata_from_filename(os.path.basename(file_path))
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"  -> ERROR: Could not read file {os.path.basename(file_path)}. Reason: {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    
    # Remove script and style elements for cleaner content
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Extract and preserve table context before general markdown conversion
    table_contexts = extract_and_format_tables(soup)
    
    # Multiple patterns to catch different formatting variations
    # Handle various whitespace characters (space, nbsp, etc.)
    # Pattern matches: "Item 1", "Item�1", "ITEM 1", "Item 1A", etc.
    section_patterns = [
        re.compile(r"item\s*\d{1,2}[a-z]?\b\.?", re.IGNORECASE),
        re.compile(r"^item[\s\xa0\u00a0]+\d{1,2}[a-z]?\b", re.IGNORECASE),  # nbsp and similar
    ]
    
    # Search in more tag types including span, td (table cells can contain headers)
    potential_headers = soup.find_all(['b', 'strong', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span', 'td'])
    
    sections = []
    seen_texts = set()  # Avoid duplicates
    
    for header in potential_headers:
        header_text = header.get_text(strip=True)
        
        # Headers should be reasonably short
        if len(header_text) > 250 or len(header_text) < 4:
            continue
        
        # Avoid duplicates
        if header_text in seen_texts:
            continue
        
        # Check if any pattern matches
        for pattern in section_patterns:
            if pattern.search(header_text):
                # Ensure it contains "item" keyword and starts with it (roughly)
                if header_text.lower().strip().startswith('item') or header_text.lower().strip().startswith('part'):
                    sections.append(header)
                    seen_texts.add(header_text)
                    break  # Don't add the same header multiple times
    
    print(f"  -> Found {len(sections)} potential Item sections")

    if not sections:
        print(f"  -> WARNING: No 'Item X.' sections found. Converting entire document.")
        full_content_md = md(str(soup), heading_style="ATX")
        
        # Replace table markers with formatted tables
        for marker, formatted_table in table_contexts.items():
            full_content_md = full_content_md.replace(marker, formatted_table)
        
        full_content_md = clean_text(full_content_md)
        
        # Split if too large (using token-based chunking)
        sub_chunks = split_large_chunk(full_content_md, MAX_CHUNK_TOKENS, CHUNK_OVERLAP_TOKENS)
        
        result = []
        for idx, sub_chunk in enumerate(sub_chunks):
            # Create and sanitize document ID
            raw_id = f"{os.path.basename(file_path)}_part_{idx+1}"
            chunk_id = sanitize_document_id(raw_id)
            summary = generate_chunk_summary(sub_chunk, f"{metadata['ticker']} {metadata['form_type']}")
            
            result.append(
                discoveryengine.Document(
                    id=chunk_id,
                    struct_data={
                        "title": f"{metadata['ticker']} {metadata['form_type']} - Part {idx+1}",
                        "description": summary,
                        "source_file": os.path.basename(file_path),
                        "ticker": metadata['ticker'],
                        "form_type": metadata['form_type'],
                        "filing_date": metadata['filing_date'],
                        "year": metadata.get('year'),
                        "quarter": metadata.get('quarter'),
                        "document_type": metadata.get('document_type'),
                        "industry": metadata.get('industry'),
                        "chunk_index": idx,
                        "total_chunks": len(sub_chunks),
                        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={metadata['ticker']}&type={metadata['form_type']}"
                    },
                    content=discoveryengine.Document.Content(
                        mime_type="text/plain",
                        raw_bytes=sub_chunk.encode('utf-8')
                    )
                )
            )
        return result

    document_chunks = []
    for i, section_tag in enumerate(sections):
        section_title = section_tag.get_text(strip=True)
        
        # Collect all content between this header and the next one
        section_content_html = []
        current_node = section_tag
        while True:
            current_node = current_node.find_next()
            if not current_node or (current_node in sections):
                break
            section_content_html.append(str(current_node))

        # Convert to Markdown and clean
        full_section_html = "".join(section_content_html)
        section_content_md = md(full_section_html, heading_style="ATX")
        
        # Replace table markers with formatted tables
        for marker, formatted_table in table_contexts.items():
            if marker in section_content_md:
                section_content_md = section_content_md.replace(marker, formatted_table)
        
        section_content_md = clean_text(section_content_md)
        
        # Add section header for context
        content_text = f"# {section_title}\n\n{section_content_md}"
        
        # Split if section is too large (using token-based chunking)
        sub_chunks = split_large_chunk(content_text, MAX_CHUNK_TOKENS, CHUNK_OVERLAP_TOKENS)
        
        for idx, sub_chunk in enumerate(sub_chunks):
            chunk_suffix = f"_part_{idx+1}" if len(sub_chunks) > 1 else ""
            # Create and sanitize document ID
            raw_id = f"{os.path.basename(file_path)}_{section_title}{chunk_suffix}"
            chunk_id = sanitize_document_id(raw_id)
            summary = generate_chunk_summary(sub_chunk, section_title)
            
            chunk_doc = discoveryengine.Document(
                id=chunk_id,
                struct_data={
                    "title": section_title,
                    "description": summary,
                    "source_file": os.path.basename(file_path),
                    "ticker": metadata['ticker'],
                    "form_type": metadata['form_type'],
                    "filing_date": metadata['filing_date'],
                    "year": metadata.get('year'),
                    "quarter": metadata.get('quarter'),
                    "document_type": metadata.get('document_type'),
                    "industry": metadata.get('industry'),
                    "section": section_title,
                    "chunk_index": idx if len(sub_chunks) > 1 else 0,
                    "total_chunks": len(sub_chunks) if len(sub_chunks) > 1 else 1,
                    "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={metadata['ticker']}&type={metadata['form_type']}"
                },
                content=discoveryengine.Document.Content(
                    mime_type="text/plain",
                    raw_bytes=sub_chunk.encode('utf-8')
                )
            )
            document_chunks.append(chunk_doc)
        
    print(f"  -> Created {len(document_chunks)} structured chunks for {os.path.basename(file_path)}.")
    return document_chunks

def import_to_vertex_ai(document_chunks):
    """
    Imports chunked documents to Vertex AI Search using inline source.
    """
    print("\n--- Step 3: Importing Documents to Vertex AI Search ---")
    discovery_client = discoveryengine.DocumentServiceClient()
    
    parent = discovery_client.branch_path(
        project=GCP_PROJECT_ID,
        location=DATA_STORE_LOCATION,
        data_store=DATA_STORE_ID,
        branch="default_branch",
    )

    if not document_chunks:
        print("  -> No document chunks to import.")
        return

    # Import documents in batches (API limit is 100 per request)
    batch_size = 100
    total_batches = (len(document_chunks) + batch_size - 1) // batch_size
    
    print(f"  -> Importing {len(document_chunks)} documents in {total_batches} batch(es)...")
    
    for i in range(0, len(document_chunks), batch_size):
        batch = document_chunks[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        request = discoveryengine.ImportDocumentsRequest(
            parent=parent,
            inline_source=discoveryengine.types.ImportDocumentsRequest.InlineSource(
                documents=batch
            ),
            reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        )

        try:
            operation = discovery_client.import_documents(request=request)
            print(f"  -> Batch {batch_num}/{total_batches}: Successfully sent import request for {len(batch)} documents.")
            print(f"     Operation Name: {operation.operation.name}")
        except Exception as e:
            print(f"  -> Batch {batch_num}/{total_batches}: ERROR - {e}")
    
    print("  -> All import batches submitted. Monitor progress in the Google Cloud Console.")


def main():
    """Main function to orchestrate the entire ingestion workflow."""
    print("--- Starting Deterministic Ingestion Script ---")

    csv_path = "C:\\Users\\tgrad\\OneDrive\\Documents\\Projects\\commercial_lines.csv"
    
    if not os.path.exists(csv_path):
        print(f"ERROR: Cannot find input file at {csv_path}")
        sys.exit(1)
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start_year = int(datetime.now().year) - 3

    # Step 0: Clean existing data
    truncate_gcs_bucket()
    truncate_vertex_ai_datastore()

    print(f"\n--- Step 1: Fetching Financial Reports (since {start_year}) ---")
    with open(csv_path, mode='r', encoding='utf-8') as infile:
        companies_to_analyze = list(csv.DictReader(infile))
    
    all_local_files = []
    for company in companies_to_analyze:
        if company.get('Financial Report Country') == "USA":
            downloaded = fetch_company_reports(company, start_year)
            all_local_files.extend(downloaded)

    if not all_local_files:
        print("\nNo files were found or downloaded. Exiting.")
        sys.exit(0)

    # Chunk documents and save to disk
    chunk_file = chunk_documents(all_local_files)
    
    if not chunk_file:
        print("\nNo document chunks were created. Exiting.")
        sys.exit(0)
    
    # Load chunks from disk and import to Vertex AI
    document_chunks = load_chunks_from_file(chunk_file)
    import_to_vertex_ai(document_chunks)

    print("\n--- Deterministic Ingestion Script Finished ---")


if __name__ == "__main__":
    main()