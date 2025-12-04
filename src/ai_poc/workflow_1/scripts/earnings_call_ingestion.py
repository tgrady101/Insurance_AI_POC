import os
import csv
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage
import re

# Load environment variables from .env file
# Script is at: src/ai_poc/workflow_1/scripts/earnings_call_ingestion.py
# .env is at: .env (project root)
# Need to go up 4 levels: scripts -> workflow_1 -> ai_poc -> src -> root
env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Debug: Print if .env was loaded
if env_path.exists():
    print(f"Loading .env from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

# --- Configuration ---
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
DATA_STORE_ID = "insurance-filings-full"
GCS_BUCKET_NAME = f"{GCP_PROJECT_ID}-filings-bucket"
DATA_STORE_LOCATION = "global"
OUTPUT_DIR = "downloaded_earnings_calls"
CHUNKED_DIR = "chunked_earnings_calls"

# Chunking configuration
MAX_CHUNK_SIZE = 2000  # Characters per chunk for optimal AI context
CHUNK_OVERLAP = 200    # Character overlap between chunks for context continuity

# Note: Vertex AI Search automatically generates embeddings during document import.
# Manual embedding generation is not supported and not needed.

# API Configuration
# API Ninjas - Paid tier required for historical transcripts
# Get API key: https://www.api-ninjas.com/register
# Developer Plan: $39/month, 100K requests/month
# Supports year/quarter parameters and speaker-split transcripts
API_NINJAS_KEY = os.environ.get("API_NINJAS_KEY", "")
API_NINJAS_BASE_URL = "https://api.api-ninjas.com/v1"

# Debug: Check if API key was loaded
if API_NINJAS_KEY:
    print(f"API_NINJAS_KEY loaded: {API_NINJAS_KEY[:10]}... (length: {len(API_NINJAS_KEY)})")
else:
    print("API_NINJAS_KEY not found in environment variables")

# Alternative: Free manual download from company investor relations pages
USE_FREE_SOURCE = os.environ.get("USE_FREE_SOURCE", "false").lower() == "true"

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

# --- Earnings Call Fetching Functions ---

def fetch_earnings_from_sec(ticker, company_name, start_year):
    """
    Fetch earnings-related content from SEC EDGAR as a free alternative.
    Looks for 8-K filings (which often contain earnings announcements).
    """
    print(f"  -> Searching SEC EDGAR for earnings-related filings (since {start_year})")
    print(f"  -> NOTE: This free method provides earnings announcements from 8-K filings")
    print(f"  -> For full transcripts, use a paid API (FMP, Alpha Vantage, etc.)")
    
    # Get CIK from the CSV if available, otherwise skip
    # For now, create placeholder that explains the limitation
    downloaded_files = []
    
    print(f"  -> Free SEC EDGAR integration available but not implemented in this version")
    print(f"  -> Recommendation: Use a paid transcript API or manually download from:")
    print(f"     - Company investor relations page")
    print(f"     - Seeking Alpha (seekingalpha.com)")
    print(f"     - The Motley Fool")
    
    return downloaded_files

def fetch_earnings_call_transcripts_api_ninjas(ticker, start_year, max_periods=12):
    """
    Fetch earnings call transcripts using API Ninjas (Paid tier required).
    Developer Plan: $39/month for 100K requests.
    
    Args:
        ticker: Stock ticker symbol
        start_year: Earliest year to consider
        max_periods: Maximum number of quarters to fetch (default: 12 = last 3 years)
    """
    if not API_NINJAS_KEY:
        print(f"  -> ERROR: API_NINJAS_KEY not set")
        print(f"  -> Get API key from: https://www.api-ninjas.com/register")
        print(f"  -> Required: Developer plan ($39/month) or higher")
        return []
    
    print(f"  -> Fetching earnings calls for {ticker} (last {max_periods} quarters)")
    print(f"  -> Using API Ninjas (Paid tier: 100K requests/month)")
    
    current_year = datetime.now().year
    current_quarter = (datetime.now().month - 1) // 3 + 1  # 0-2=Q1, 3-5=Q2, 6-8=Q3, 9-11=Q4
    
    downloaded_files = []
    request_count = 0
    
    # Build list of quarters to fetch (most recent first, then reverse)
    quarters_to_fetch = []
    year = current_year
    quarter = current_quarter
    
    while len(quarters_to_fetch) < max_periods and year >= start_year:
        quarters_to_fetch.append((year, quarter))
        quarter -= 1
        if quarter < 1:
            quarter = 4
            year -= 1
    
    # Reverse to fetch oldest first (better for resuming after rate limit)
    quarters_to_fetch.reverse()
    
    print(f"  -> Target quarters: {', '.join([f'{y}Q{q}' for y, q in quarters_to_fetch])}")
    
    # Iterate through selected quarters
    for year, quarter in quarters_to_fetch:
        try:
            # Check if file already exists (skip API request)
            call_date = datetime(year, quarter * 3, 1)
            filename = f"{ticker}_EARNINGS_{year}_Q{quarter}_{call_date.strftime('%Y-%m-%d')}.txt"
            file_path = os.path.join(OUTPUT_DIR, filename)
            
            if os.path.exists(file_path):
                print(f"     -> ✓ Already downloaded: Q{quarter} {year}")
                downloaded_files.append(file_path)
                continue
            
            # API Ninjas endpoint with year and quarter parameters
            url = f"{API_NINJAS_BASE_URL}/earningstranscript"
            headers = {'X-Api-Key': API_NINJAS_KEY}
            params = {
                'ticker': ticker,
                'year': str(year),
                'quarter': str(quarter)
            }
            
            print(f"     -> Fetching Q{quarter} {year} transcript...")
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                request_count += 1
                
                # Extract transcript content
                # API Ninjas returns: {"ticker": "MSFT", "year": "2024", "quarter": "2", "transcript": "...", "transcript_split": [...]}
                if isinstance(data, dict) and 'transcript' in data:
                    transcript_text = data.get('transcript', '')
                    transcript_split = data.get('transcript_split', [])
                    
                    # Prefer transcript_split (speaker-aware) if available, otherwise use plain transcript
                    if transcript_split and len(transcript_split) > 0:
                        # Use speaker-split version for better chunking
                        full_content = ""
                        for segment in transcript_split:
                            speaker = segment.get('speaker', 'Unknown Speaker')
                            role = segment.get('role', '')
                            company = segment.get('company', '')
                            text = segment.get('text', '')
                            
                            # Format: "Speaker Name - Role (Company):\nText\n\n"
                            if role and company:
                                full_content += f"{speaker} - {role} ({company}):\n{text}\n\n"
                            elif role:
                                full_content += f"{speaker} - {role}:\n{text}\n\n"
                            else:
                                full_content += f"{speaker}:\n{text}\n\n"
                    elif transcript_text:
                        # Use plain transcript if split version not available
                        full_content = transcript_text
                    else:
                        print(f"     -> No content for Q{quarter} {year}")
                        continue
                    
                    # Save transcript to file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(full_content)
                    
                    downloaded_files.append(file_path)
                    
                    if transcript_split:
                        print(f"     -> ✓ Saved: {filename} ({len(transcript_split)} speakers, {len(full_content):,} chars)")
                    else:
                        print(f"     -> ✓ Saved: {filename} ({len(full_content):,} chars)")
                    
                    # Minimal rate limiting (100K requests/month = plenty of headroom)
                    import time
                    time.sleep(0.5)
                else:
                    print(f"     -> No transcript found for Q{quarter} {year}")
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 402:
                    print(f"     -> Payment Required: Upgrade to paid plan at https://www.api-ninjas.com/pricing")
                    return downloaded_files
                elif e.response.status_code == 404:
                    print(f"     -> Not found: Q{quarter} {year}")
                else:
                    print(f"     -> HTTP Error {e.response.status_code}: {e}")
                continue
            except Exception as e:
                print(f"     -> Error: {e}")
                continue
                
        except requests.exceptions.HTTPError as e:
            print(f"     -> HTTP Error: {e}")
            if e.response.status_code == 403:
                print(f"     -> ERROR: 403 Forbidden - Check your API key validity")
            continue
        except Exception as e:
            print(f"     -> Error: {e}")
            continue
    
    print(f"  -> Downloaded {len(downloaded_files)} transcripts for {ticker} (used {request_count} API requests)")
    return downloaded_files

def fetch_company_earnings_calls(company, start_year, max_periods=8):
    """Fetch earnings call transcripts for a company.
    
    Args:
        company: Dictionary with 'Ticker' and 'Company' keys
        start_year: Earliest year to consider
        max_periods: Maximum number of quarters to fetch (default: 8)
    """
    ticker = company['Ticker']
    company_name = company['Company']
    
    print(f"\n[{ticker}] {company_name}")
    
    if USE_FREE_SOURCE:
        # Use free SEC EDGAR alternative - look for 8-K filings with earnings
        return fetch_earnings_from_sec(ticker, company_name, start_year)
    else:
        # Use API Ninjas (Paid: 100K requests/month)
        return fetch_earnings_call_transcripts_api_ninjas(ticker, start_year, max_periods)

# --- Chunking Functions ---

def create_speaker_aware_chunks(file_path):
    """
    Create chunks from earnings call transcript with speaker awareness.
    Preserves context by keeping speaker segments together and adding metadata.
    """
    print(f"  -> Chunking transcript: {os.path.basename(file_path)}")
    
    # Extract metadata from filename
    metadata = extract_metadata_from_filename(os.path.basename(file_path))
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  -> ERROR: Could not read file {os.path.basename(file_path)}. Reason: {e}")
        return []
    
    # Parse transcript to identify speakers (common patterns)
    # Most transcripts have patterns like:
    # "Speaker Name - Role" or "Speaker Name:" followed by text
    speaker_pattern = re.compile(r'^([A-Z][A-Za-z\s\.]+(?:\s-\s[A-Za-z\s,\.&]+)?):?\s*$', re.MULTILINE)
    
    # Split content into sections by speaker
    sections = []
    current_speaker = "Unknown"
    current_text = []
    
    for line in content.split('\n'):
        match = speaker_pattern.match(line.strip())
        if match:
            # Save previous section
            if current_text:
                sections.append({
                    'speaker': current_speaker,
                    'text': '\n'.join(current_text).strip()
                })
            # Start new section
            current_speaker = match.group(1).strip()
            current_text = []
        else:
            current_text.append(line)
    
    # Add final section
    if current_text:
        sections.append({
            'speaker': current_speaker,
            'text': '\n'.join(current_text).strip()
        })
    
    # Create chunks maintaining speaker context
    chunks = []
    chunk_num = 0
    
    for section in sections:
        speaker = section['speaker']
        text = section['text']
        
        # If section is small enough, keep as single chunk
        if len(text) <= MAX_CHUNK_SIZE:
            if text.strip():  # Only add non-empty chunks
                chunk_num += 1
                chunks.append(create_chunk_document(
                    file_path=file_path,
                    chunk_num=chunk_num,
                    content=text,
                    metadata=metadata,
                    speaker=speaker
                ))
        else:
            # Split long sections with overlap
            for i in range(0, len(text), MAX_CHUNK_SIZE - CHUNK_OVERLAP):
                chunk_text = text[i:i + MAX_CHUNK_SIZE]
                if chunk_text.strip():
                    chunk_num += 1
                    chunks.append(create_chunk_document(
                        file_path=file_path,
                        chunk_num=chunk_num,
                        content=chunk_text,
                        metadata=metadata,
                        speaker=speaker
                    ))
    
    print(f"     -> Created {len(chunks)} chunks from {len(sections)} speaker sections")
    return chunks

def create_chunk_document(file_path, chunk_num, content, metadata, speaker="Unknown"):
    """Create a Document object for a chunk with enhanced metadata."""
    filename = os.path.basename(file_path)
    doc_id = sanitize_document_id(f"{filename}_chunk_{chunk_num}")
    
    # Create summary/description for the chunk
    quarter = metadata.get("quarter", "N/A")
    summary = f"Earnings call {quarter} {metadata.get('year', '?')} - {speaker}: {content[:250]}..."
    
    # Build metadata
    struct_data = {
        "ticker": metadata.get("ticker", "Unknown"),
        "company": metadata.get("company", "Unknown"),
        "quarter": metadata.get("quarter", "N/A"),
        "year": metadata.get("year", 0),
        "call_date": metadata.get("call_date", "Unknown"),
        "speaker": speaker,
        "chunk_number": chunk_num,
        "document_type": "earnings_call_transcript",
        "source_file": filename,
        "summary": summary
    }
    
    # Create Document object
    doc = discoveryengine.Document(
        id=doc_id,
        struct_data=struct_data,
        content=discoveryengine.Document.Content(
            mime_type="text/plain",
            raw_bytes=content.encode('utf-8')
        )
    )
    
    return doc

def extract_metadata_from_filename(filename):
    """Extract metadata from earnings call filename."""
    # Expected format: TICKER_EARNINGS_YEAR_QUARTER_DATE.txt
    # Example: AIG_EARNINGS_2024_Q3_2024-11-01.txt
    parts = filename.replace('.txt', '').split('_')
    
    metadata = {
        "ticker": "Unknown",
        "company": "Unknown",
        "year": 0,
        "quarter": "N/A",  # String format: Q1, Q2, Q3, Q4
        "call_date": "Unknown"
    }
    
    if len(parts) >= 5:
        metadata["ticker"] = parts[0]
        metadata["year"] = int(parts[2]) if parts[2].isdigit() else 0
        # Extract quarter string from "Q3" -> "Q3"
        quarter_str = parts[3]
        if quarter_str.startswith('Q') and len(quarter_str) == 2 and quarter_str[1:].isdigit():
            metadata["quarter"] = quarter_str  # Store as "Q3" not 3
        else:
            metadata["quarter"] = "N/A"
        metadata["call_date"] = parts[4]
    
    return metadata

# --- Chunk Management Functions ---

def chunk_transcripts(local_file_paths):
    """Chunks transcripts, saves to disk, and converts to Document objects for import.
    
    Note: Vertex AI Search automatically generates embeddings during import.
    """
    print("\n--- Step 2: Chunking Transcripts ---")
    
    all_chunks = []
    for file_path in local_file_paths:
        chunks = create_speaker_aware_chunks(file_path)
        all_chunks.extend(chunks)
    
    if not all_chunks:
        print("  -> No chunks were created.")
        return None
    
    print(f"  -> Total chunks created: {len(all_chunks)}")
    
    # Save chunks to disk
    os.makedirs(CHUNKED_DIR, exist_ok=True)
    chunk_file = os.path.join(CHUNKED_DIR, f"earnings_chunks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
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

# --- Import Functions ---

def import_to_vertex_ai(document_chunks):
    """Import document chunks to Vertex AI Search using inline source."""
    print(f"\n--- Step 3: Importing to Vertex AI Search ---")
    
    discovery_client = discoveryengine.DocumentServiceClient()
    parent = f"projects/{GCP_PROJECT_ID}/locations/{DATA_STORE_LOCATION}/collections/default_collection/dataStores/{DATA_STORE_ID}/branches/default_branch"
    
    # Batch import (max 100 documents per request)
    batch_size = 100
    total_batches = (len(document_chunks) + batch_size - 1) // batch_size
    
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

# --- Main Function ---

def main():
    """Main function to orchestrate the earnings call ingestion workflow."""
    print("--- Starting Earnings Call Ingestion Script ---")

    csv_path = "C:\\Users\\tgrad\\OneDrive\\Documents\\Projects\\commercial_lines.csv"
    
    if not os.path.exists(csv_path):
        print(f"ERROR: Cannot find input file at {csv_path}")
        sys.exit(1)
    
    # Configuration (define early so it can be used in error messages)
    start_year = int(datetime.now().year) - 3
    max_periods = 12  # Last 12 quarters (3 years)
    
    # Check API configuration
    if not USE_FREE_SOURCE and not API_NINJAS_KEY:
        print("\n" + "="*70)
        print("API NINJAS KEY NEEDED (PAID TIER REQUIRED)")
        print("="*70)
        print("\nAPI Ninjas Developer Plan: $39/month for 100K requests\n")
        print("QUICK START:")
        print("1. Get API Ninjas API key:")
        print("   → Visit: https://www.api-ninjas.com/register")
        print("   → Sign up and subscribe to Developer plan ($39/month)")
        print("   → Copy your API key from dashboard\n")
        print("2. Set environment variable:")
        print("   → PowerShell: $env:API_NINJAS_KEY = 'your-api-key-here'")
        print("   → CMD: set API_NINJAS_KEY=your-api-key-here\n")
        print("3. Run this script again!")
        print("\nEXPECTED USAGE:")
        print(f"  • 7 companies × {max_periods} transcripts each = {7 * max_periods} total requests")
        print(f"  • 100K requests/month = Download all transcripts instantly!")
        print(f"  • Cost: $39/month (cancel anytime)\n")
        print("FEATURES:")
        print("  • Historical transcripts with year/quarter selection")
        print("  • Speaker-split transcripts for better AI analysis")
        print("  • No rate limiting (within 100K/month)")
        print("  • Production-ready with 99% uptime SLA\n")
        print("ALTERNATIVE OPTIONS:")
        print("  • Manual download: Free but 14-21 hours of work")
        print("  • SEC 8-K filings: Set USE_FREE_SOURCE=true (limited data)")
        print("="*70)
        sys.exit(1)
    
    if USE_FREE_SOURCE:
        print("\n" + "!"*70)
        print("USING FREE SOURCE MODE")
        print("!"*70)
        print("Note: Free sources provide limited earnings data")
        print("- SEC 8-K filings contain earnings announcements, not full transcripts")
        print("- For full Q&A transcripts, use API Ninjas ($39/month)")
        print("- Consider manual download from company investor relations pages")
        print("!"*70 + "\n")
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n--- Step 1: Fetching Earnings Call Transcripts (last {max_periods} quarters) ---")
    print(f"Estimated API requests: 7 companies × {max_periods} quarters = {7 * max_periods} requests")
    print(f"Days needed (at 100K/month): Instant!\n")
    
    with open(csv_path, mode='r', encoding='utf-8') as infile:
        companies_to_analyze = list(csv.DictReader(infile))
    
    all_local_files = []
    for company in companies_to_analyze:
        if company.get('Financial Report Country') == "USA":
            downloaded = fetch_company_earnings_calls(company, start_year, max_periods)
            all_local_files.extend(downloaded)

    if not all_local_files:
        print("\nNo transcripts were found or downloaded.")
        print("\nTo proceed:")
        print("1. Get a paid API key and set $env:USE_FREE_SOURCE = 'false'")
        print("2. OR manually download transcript files to:", OUTPUT_DIR)
        print("   - Format: {TICKER}_EARNINGS_{YEAR}_Q{Q}_{DATE}.txt")
        print("   - Example: AIG_EARNINGS_2024_Q3_2024-11-01.txt")
        print("3. Re-run this script - it will process existing files")
        sys.exit(0)

    # Chunk transcripts and save to disk
    chunk_file = chunk_transcripts(all_local_files)
    
    if not chunk_file:
        print("\nNo chunks were created. Exiting.")
        sys.exit(0)

    # Load chunks and import to Vertex AI
    print("\n--- Step 3: Preparing for Vertex AI Import ---")
    document_chunks = load_chunks_from_file(chunk_file)
    
    if not document_chunks:
        print("  -> No chunks to import.")
        sys.exit(0)
    
    import_to_vertex_ai(document_chunks)
    
    print("\n--- Earnings Call Ingestion Complete ---")
    print(f"  -> Total transcripts downloaded: {len(all_local_files)}")
    print(f"  -> Total chunks created: {len(document_chunks)}")
    print(f"  -> Chunks saved to: {chunk_file}")
    print(f"  -> Import submitted to: {DATA_STORE_ID}")
    print("\nMonitor import progress in Google Cloud Console:")
    print(f"https://console.cloud.google.com/gen-app-builder/data-stores/{DATA_STORE_ID}")

if __name__ == "__main__":
    main()
