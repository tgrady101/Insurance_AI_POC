"""
Test search functionality in Vertex AI Search data store.
"""
from google.cloud import discoveryengine_v1 as discoveryengine

# Configuration
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
DATA_STORE_ID = "insurance-filings-full"
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
    
    # Try searches similar to what ADK agents use (no filters - just natural language queries)
    queries = [
        {
            "query": "HIG Hartford 2025 Q3 Business Insurance segment commercial insurance",
            "description": "HIG Q3 2025 - natural language query (no filter)"
        },
        {
            "query": "TRV Travelers 2025 third quarter Business Insurance segment premiums combined ratio",
            "description": "TRV Q3 2025 - business insurance metrics (no filter)"
        },
        {
            "query": "WRB W.R. Berkley 2025 Q3 Insurance segment earned premiums",
            "description": "WRB Q3 2025 - insurance segment (no filter)"
        }
    ]
    
    for query_config in queries:
        query = query_config["query"]
        description = query_config.get("description", "")
        
        print(f"\n{'='*80}")
        print(f"Query: '{description}'")
        print(f"Text: {query}")
        print(f"{'='*80}")
        
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            # No filter - ADK agents use pure text queries
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
            print(f"\n✓ Found {len(results)} results\n")
            
            if results:
                for i, result in enumerate(results[:3], 1):  # Show first 3 results
                    doc = result.document
                    print(f"  Result {i}:")
                    print(f"  {'-'*76}")
                    doc_id = doc.name.split('/')[-1]
                    
                    # Display structured data
                    if hasattr(doc, 'struct_data') and doc.struct_data:
                        struct_dict = dict(doc.struct_data)
                        print(f"    Ticker:  {struct_dict.get('ticker', 'N/A')}")
                        print(f"    Form:    {struct_dict.get('form_type', 'N/A')}")
                        print(f"    Quarter: Q{struct_dict.get('quarter', 'N/A')} {struct_dict.get('year', 'N/A')}")
                        print(f"    Section: {struct_dict.get('section', 'N/A')[:60]}")
                        
                        # Show snippet of content if available
                        content = struct_dict.get('content', '')
                        if content:
                            preview = content[:200].replace('\n', ' ')
                            print(f"    Preview: {preview}...")
                    print()
            else:
                print("  ⚠️  No results returned")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n" + "="*80)
    print("Search test complete")

if __name__ == "__main__":
    test_search()
