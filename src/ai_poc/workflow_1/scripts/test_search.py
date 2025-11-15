"""
Test search functionality in Vertex AI Search data store.
"""
from google.cloud import discoveryengine_v1 as discoveryengine

# Configuration
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
DATA_STORE_ID = "insurance-filings"
DATA_STORE_LOCATION = "global"
SEARCH_ENGINE_ID = "insurance-poc_1763083298659"  # From your screenshot URL

def test_search():
    """Test a simple search query and retrieve full documents."""
    print("Testing Vertex AI Search...")
    
    search_client = discoveryengine.SearchServiceClient()
    doc_client = discoveryengine.DocumentServiceClient()
    
    # Build the serving config path
    serving_config = f"projects/{GCP_PROJECT_ID}/locations/{DATA_STORE_LOCATION}/collections/default_collection/dataStores/{DATA_STORE_ID}/servingConfigs/default_config"
    
    print(f"Serving config: {serving_config}\n")
    
    # Try a simple search
    queries = [
        "Can you comment on the potential impact of tariffs on your business?"
    ]
    
    for query in queries:
        print(f"\nSearching for: '{query}'")
        
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5,
            # Request full document content
            content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True,
                    max_snippet_count=3
                ),
                extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                    max_extractive_answer_count=1,
                    max_extractive_segment_count=3
                )
            )
        )
        
        try:
            response = search_client.search(request=request)
            
            results = list(response.results)
            print(f"  Found {len(results)} results")
            
            if results:
                for i, result in enumerate(results[:2], 1):  # Show first 2 results
                    doc = result.document
                    print(f"\n  {'='*80}")
                    print(f"  Result {i}:")
                    print(f"  {'='*80}")
                    doc_id = doc.name.split('/')[-1]
                    print(f"  ID: {doc_id}")
                    
                    # Display structured data
                    if hasattr(doc, 'struct_data') and doc.struct_data:
                        struct_dict = dict(doc.struct_data)
                        print(f"\n  Metadata:")
                        print(f"    Title: {struct_dict.get('title', 'N/A')}")
                        print(f"    Ticker: {struct_dict.get('ticker', 'N/A')}")
                        print(f"    Form: {struct_dict.get('form_type', 'N/A')}")
                        print(f"    Filing Date: {struct_dict.get('filing_date', 'N/A')}")
                        print(f"    Year: {struct_dict.get('year', 'N/A')}")
                        print(f"    Quarter: {struct_dict.get('quarter', 'N/A')}")
                        print(f"    Section: {struct_dict.get('section', 'N/A')}")
                    
                    # Fetch full document using Document API
                    try:
                        full_doc_name = doc.name
                        full_doc = doc_client.get_document(name=full_doc_name)
                        
                        if hasattr(full_doc, 'content') and full_doc.content:
                            if hasattr(full_doc.content, 'raw_bytes') and full_doc.content.raw_bytes:
                                content_text = full_doc.content.raw_bytes.decode('utf-8')
                                print(f"\n  FULL DOCUMENT CONTENT:")
                                print(f"  {'-'*80}")
                                print(f"  {content_text[:1000]}")  # Show first 1000 chars
                                if len(content_text) > 1000:
                                    print(f"  ... (content continues)")
                                print(f"  {'-'*80}")
                                print(f"  Total content length: {len(content_text)} characters")
                        else:
                            print(f"\n  No raw content available in full document")
                    except Exception as e:
                        print(f"\n  Error fetching full document: {e}")
            else:
                print("  No results returned")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n" + "="*80)
    print("Search test complete")

if __name__ == "__main__":
    test_search()
