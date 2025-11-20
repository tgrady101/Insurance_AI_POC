"""
Upload Raw Files to Vertex AI Search (No Custom Chunking)

This script uploads earnings call transcripts and SEC filings directly to Vertex AI Search
without any custom chunking, allowing the platform to handle chunking automatically.
This enables A/B testing of custom chunking vs. default Vertex AI chunking.

Purpose:
- Compare custom speaker-aware chunking vs. Vertex AI's default chunking
- Test search quality differences between the two approaches
- Evaluate which chunking strategy provides better retrieval performance

Data Sources:
- downloaded_earnings_calls/: Earnings call transcripts (.txt)
- downloaded_reports/: SEC 10-K and 10-Q filings (.txt)

Target Datastore: insurance-filings-test (filings_data_store_testing)
"""

import os
import sys
import re
from datetime import datetime
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage
from google.api_core import retry

# --- Configuration ---
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
DATA_STORE_ID = "insurance-filings-test"  # Test datastore for default chunking
DATA_STORE_LOCATION = "global"
GCS_BUCKET_NAME = f"{GCP_PROJECT_ID}-test-datastore-bucket"

# Input directories
EARNINGS_CALLS_DIR = "downloaded_earnings_calls"
REPORTS_DIR = "downloaded_reports"

# Batch configuration
BATCH_SIZE = 100  # GCS URIs are small, can handle many per batch
OPERATION_TIMEOUT = 600  # 10 minutes per batch

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

def upload_file_to_gcs(file_path):
    """
    Upload a file to GCS and return its URI.
    Returns None if upload fails.
    """
    try:
        storage_client = storage.Client(project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        
        filename = os.path.basename(file_path)
        blob = bucket.blob(filename)
        
        # Upload the file
        blob.upload_from_filename(file_path)
        
        # Return GCS URI
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{filename}"
        return gcs_uri
        
    except Exception as e:
        print(f"  Error uploading {filename} to GCS: {e}")
        return None

def extract_earnings_metadata(filename):
    """
    Extract metadata from earnings call filename.
    Expected format: TICKER_EARNINGS_YEAR_QUARTER_DATE.txt
    Example: AIG_EARNINGS_2024_Q3_2024-11-01.txt
    """
    parts = filename.replace('.txt', '').split('_')
    
    metadata = {
        "ticker": "Unknown",
        "company": "Unknown",
        "year": 0,
        "quarter": 0,
        "quarter_str": "Unknown",
        "call_date": "Unknown",
        "document_type": "earnings_call_transcript"
    }
    
    try:
        if len(parts) >= 5:
            metadata["ticker"] = parts[0]
            # Year is parts[2]
            if parts[2].isdigit():
                metadata["year"] = int(parts[2])
            # Quarter is parts[3] (e.g., "Q3")
            quarter_str = parts[3]
            if quarter_str.startswith('Q') and quarter_str[1:].isdigit():
                metadata["quarter"] = int(quarter_str[1:])  # Q3 -> 3
                metadata["quarter_str"] = quarter_str
            # Date is parts[4]
            metadata["call_date"] = parts[4]
    except Exception as e:
        print(f"  Warning: Could not parse filename {filename}: {e}")
    
    return metadata

def extract_report_metadata(filename):
    """
    Extract metadata from SEC filing filename.
    Expected format: TICKER_FORM_FILING_DATE.html
    Example: AIG_10-Q_2024-11-04.html or AIG_10-K_2024-02-15.html
    """
    # Remove file extension
    base = filename.replace('.html', '').replace('.txt', '')
    parts = base.split('_')
    
    metadata = {
        "ticker": "Unknown",
        "company": "Unknown",
        "year": 0,
        "quarter": 0,
        "quarter_str": "Unknown",
        "filing_date": "Unknown",
        "form_type": "Unknown",
        "document_type": "sec_filing"
    }
    
    try:
        # Format: TICKER_FORM_DATE.html
        # Example: AIG_10-Q_2024-11-04.html or BRK.B_10-K_2024-02-15.html
        if len(parts) >= 3:
            metadata["ticker"] = parts[0]
            metadata["form_type"] = parts[1]  # 10-K or 10-Q
            metadata["filing_date"] = parts[2]  # YYYY-MM-DD
            
            # Extract year from filing date
            date_parts = parts[2].split('-')
            if len(date_parts) >= 1 and date_parts[0].isdigit():
                metadata["year"] = int(date_parts[0])
            
            # Determine quarter from filing date (approximate)
            if metadata["form_type"] == "10-Q" and len(date_parts) >= 2:
                month = int(date_parts[1])
                if month <= 5:  # Filed by May = Q1
                    metadata["quarter"] = 1
                    metadata["quarter_str"] = "Q1"
                elif month <= 8:  # Filed by Aug = Q2
                    metadata["quarter"] = 2
                    metadata["quarter_str"] = "Q2"
                else:  # Filed later = Q3
                    metadata["quarter"] = 3
                    metadata["quarter_str"] = "Q3"
            else:
                # 10-K has no quarter
                metadata["quarter"] = 0
                metadata["quarter_str"] = "Annual"
    except Exception as e:
        print(f"  Warning: Could not parse filename {filename}: {e}")
    
    return metadata

def create_document_from_file(file_path, metadata):
    """
    Create a Vertex AI Search Document from a file using GCS URI.
    File will be uploaded to GCS, then referenced in the Document.
    """
    filename = os.path.basename(file_path)
    doc_id = sanitize_document_id(filename.replace('.txt', '').replace('.html', ''))
    
    # Upload file to GCS
    gcs_uri = upload_file_to_gcs(file_path)
    if not gcs_uri:
        return None
    
    # Determine MIME type based on file extension
    mime_type = "text/html" if file_path.endswith('.html') else "text/plain"
    
    # Create struct_data from metadata
    struct_data = {
        "ticker": metadata.get("ticker", "Unknown"),
        "company": metadata.get("company", "Unknown"),
        "year": metadata.get("year", 0),
        "quarter": metadata.get("quarter", 0),
        "document_type": metadata.get("document_type", "Unknown"),
        "source_file": filename
    }
    
    # Add document-type specific fields
    if metadata.get("document_type") == "earnings_call_transcript":
        struct_data["call_date"] = metadata.get("call_date", "Unknown")
        struct_data["quarter_str"] = metadata.get("quarter_str", "Unknown")
    elif metadata.get("document_type") == "sec_filing":
        struct_data["filing_date"] = metadata.get("filing_date", "Unknown")
        struct_data["form_type"] = metadata.get("form_type", "Unknown")
        struct_data["quarter_str"] = metadata.get("quarter_str", "Unknown")
    
    # Create Document object with GCS URI reference
    # Vertex AI will fetch from GCS and chunk automatically
    doc = discoveryengine.Document(
        id=doc_id,
        struct_data=struct_data,
        content=discoveryengine.Document.Content(
            mime_type=mime_type,
            uri=gcs_uri
        )
    )
    
    return doc

def collect_files_from_directory(directory, file_type):
    """
    Collect all files from a directory, upload to GCS, and create Document objects.
    
    Args:
        directory: Path to directory containing files
        file_type: "earnings" or "reports" for appropriate metadata extraction
    
    Returns:
        List of Document objects with GCS URIs
    """
    if not os.path.exists(directory):
        print(f"  Warning: Directory not found: {directory}")
        return []
    
    documents = []
    # Support both .txt (earnings calls) and .html (SEC filings)
    files = [f for f in os.listdir(directory) if f.endswith('.txt') or f.endswith('.html')]
    
    print(f"\n--- Processing {len(files)} files from {directory} ---")
    print(f"  Uploading to GCS: gs://{GCS_BUCKET_NAME}")
    
    for idx, filename in enumerate(files, 1):
        file_path = os.path.join(directory, filename)
        
        # Extract metadata based on file type
        if file_type == "earnings":
            metadata = extract_earnings_metadata(filename)
        elif file_type == "reports":
            metadata = extract_report_metadata(filename)
        else:
            print(f"  Error: Unknown file_type '{file_type}'")
            continue
        
        # Create document (this uploads to GCS)
        doc = create_document_from_file(file_path, metadata)
        if doc:
            documents.append(doc)
            if idx % 10 == 0 or idx == len(files):
                print(f"  -> Uploaded {idx}/{len(files)} files to GCS")
    
    print(f"  ✓ Created {len(documents)} document objects with GCS URIs")
    return documents

def import_to_vertex_ai(documents):
    """
    Import documents to Vertex AI Search test datastore using GCS URIs.
    Documents are already in GCS - we just send URIs to Vertex AI.
    No size limits since we're using GCS references instead of inline content.
    """
    print(f"\n--- Importing {len(documents)} Documents to Vertex AI Search ---")
    print(f"  Datastore: {DATA_STORE_ID} (Test - Default Chunking)")
    print(f"  Method: GCS URI references (no size limits)")
    
    discovery_client = discoveryengine.DocumentServiceClient()
    parent = f"projects/{GCP_PROJECT_ID}/locations/{DATA_STORE_LOCATION}/collections/default_collection/dataStores/{DATA_STORE_ID}/branches/default_branch"
    
    # Batch documents (GCS URIs are small, can handle 100 per batch)
    batches = []
    for i in range(0, len(documents), BATCH_SIZE):
        batches.append(documents[i:i + BATCH_SIZE])
    
    print(f"  -> Created {len(batches)} batches of up to {BATCH_SIZE} documents each")
    
    successful_batches = 0
    failed_batches = 0
    
    for batch_num, batch in enumerate(batches, 1):
        request = discoveryengine.ImportDocumentsRequest(
            parent=parent,
            inline_source=discoveryengine.types.ImportDocumentsRequest.InlineSource(
                documents=batch
            ),
            reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        )

        try:
            operation = discovery_client.import_documents(request=request)
            print(f"  -> Batch {batch_num}/{len(batches)}: ✓ Imported {len(batch)} documents")
            successful_batches += 1
        except Exception as e:
            print(f"  -> Batch {batch_num}/{len(batches)}: ERROR - {e}")
            failed_batches += 1
    
    print(f"\n--- Import Summary ---")
    print(f"  Total Documents: {len(documents)}")
    print(f"  Successful Batches: {successful_batches}/{len(batches)}")
    print(f"  Failed Batches: {failed_batches}/{len(batches)}")
    print(f"\n  Note: Vertex AI will fetch documents from GCS and chunk automatically.")
    print(f"  GCS Bucket: gs://{GCS_BUCKET_NAME}")
    print(f"  Monitor progress in Google Cloud Console:")
    print(f"  https://console.cloud.google.com/gen-app-builder/locations/global/data-stores/{DATA_STORE_ID}")

def main():
    """
    Main function to upload raw files to GCS and import to Vertex AI Search test datastore.
    """
    print("=" * 80)
    print("UPLOAD RAW FILES VIA GCS TO VERTEX AI SEARCH (DEFAULT CHUNKING)")
    print("=" * 80)
    print(f"\nProject: {GCP_PROJECT_ID}")
    print(f"GCS Bucket: gs://{GCS_BUCKET_NAME}")
    print(f"Datastore: {DATA_STORE_ID}")
    print(f"Purpose: A/B test custom chunking vs. Vertex AI default chunking\n")
    
    # Verify GCS bucket exists
    print(f"--- Verifying GCS Bucket ---")
    try:
        storage_client = storage.Client(project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        if not bucket.exists():
            print(f"  ERROR: Bucket gs://{GCS_BUCKET_NAME} does not exist!")
            print(f"  Run 'terraform apply' to create the bucket.")
            sys.exit(1)
        print(f"  ✓ Bucket exists: gs://{GCS_BUCKET_NAME}")
    except Exception as e:
        print(f"  ERROR: Cannot access bucket: {e}")
        sys.exit(1)
    
    # Collect earnings call transcripts
    earnings_docs = collect_files_from_directory(EARNINGS_CALLS_DIR, "earnings")
    
    # Collect SEC filings
    report_docs = collect_files_from_directory(REPORTS_DIR, "reports")
    
    # Combine all documents
    all_documents = earnings_docs + report_docs
    
    if not all_documents:
        print("\n  ERROR: No documents found to upload!")
        print(f"  Check that files exist in:")
        print(f"    - {EARNINGS_CALLS_DIR}/")
        print(f"    - {REPORTS_DIR}/")
        sys.exit(1)
    
    print(f"\n--- Total Documents to Upload: {len(all_documents)} ---")
    print(f"  Earnings Calls: {len(earnings_docs)}")
    print(f"  SEC Filings: {len(report_docs)}")
    
    # Confirm upload
    response = input("\nProceed with upload to GCS and import to Vertex AI? (yes/no): ").strip().lower()
    if response != 'yes':
        print("  Upload cancelled.")
        sys.exit(0)
    
    # Import to Vertex AI (files will be uploaded to GCS during document creation)
    import_to_vertex_ai(all_documents)
    
    print("\n" + "=" * 80)
    print("UPLOAD COMPLETE")
    print("=" * 80)
    print("\nNext Steps:")
    print("  1. Monitor import progress in Google Cloud Console")
    print("  2. Wait for all documents to be ingested and indexed")
    print("  3. Compare search results between datastores:")
    print("     - insurance-filings (custom chunking)")
    print("     - insurance-filings-test (default chunking)")
    print("  4. Evaluate which chunking strategy provides better retrieval")
    print(f"\nFiles uploaded to: gs://{GCS_BUCKET_NAME}\n")

if __name__ == "__main__":
    main()
