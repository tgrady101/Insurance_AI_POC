"""
Utility Agent - Utility Functions

Provides utility functions for quarter detection and data validation.
Document retrieval is now handled by Vertex AI Search grounding in the LLM agents.
"""

from typing import Dict, Tuple
from google.cloud import discoveryengine_v1 as discoveryengine
from datetime import datetime

from .config import (
    GCP_PROJECT_ID,
    DATA_STORE_ID,
    DATA_STORE_LOCATION,
    COMPANIES
)


class UtilityAgent:
    """
    Agent responsible for utility functions:
    - Finding latest complete quarter
    - Validating data availability
    
    Note: Document retrieval is handled by Vertex AI Search grounding
    configured in the specialized agents' LLM models.
    """
    
    def __init__(self):
        """Initialize the utility agent."""
        self.project_id = GCP_PROJECT_ID
        self.data_store_id = DATA_STORE_ID
        self.data_store_location = DATA_STORE_LOCATION
        
        # Initialize Vertex AI Search client for validation queries
        self.search_client = discoveryengine.SearchServiceClient()
        
        # Build serving config path
        self.serving_config = (
            f"projects/{self.project_id}/locations/{self.data_store_location}/"
            f"collections/default_collection/dataStores/{self.data_store_id}/"
            f"servingConfigs/default_config"
        )
        
        print(f"[OK] UtilityAgent initialized (utility functions only)")
        print(f"  Datastore: {self.data_store_id}")
        print(f"  Project: {self.project_id}")
        print(f"  Note: Document retrieval via LLM grounding")
    
    def _check_documents_exist(self, query: str, max_results: int = 3) -> bool:
        """
        Simple check if documents exist for a query (used for validation).
        
        Args:
            query: Search query string
            max_results: Number of results to check
        
        Returns:
            True if any documents found, False otherwise
        """
        request = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            page_size=max_results,
        )
        
        try:
            response = self.search_client.search(request)
            return len(list(response.results)) > 0
        except Exception as e:
            print(f"⚠️  Validation check error: {e}")
            return False
    
    def validate_data_availability(self, year: int, quarter: int) -> Dict[str, Dict]:
        """
        Validate that required documents are available for all companies.
        
        **COMMERCIAL SEGMENT FOCUS**: Validates SEC filings (10-K/10-Q) and 
        earnings calls that contain Commercial insurance segment data.
        
        Args:
            year: Target year
            quarter: Target quarter (1-4)
        
        Returns:
            Dictionary mapping ticker to availability status:
            {
                "TRV": {
                    "complete": True,
                    "sec_filing": True,
                    "earnings_call": True,
                    "requires_earnings_call": True,
                    "missing": []
                },
                ...
            }
        """
        print(f"\n📋 Validating data availability for Q{quarter} {year}...")
        
        availability = {}
        
        for company in COMPANIES:
            ticker = company["ticker"]
            has_earnings = company["has_earnings_calls"]
            
            # Check for SEC filing (10-K or 10-Q)
            filing_type = "10-K" if quarter == 4 else "10-Q"
            sec_query = f"{ticker} {filing_type} {year} Q{quarter}"
            has_sec_filing = self._check_documents_exist(sec_query)
            
            # Check for earnings call (if applicable)
            has_earnings_call = False
            if has_earnings:
                earnings_query = f"{ticker} earnings call {year} Q{quarter}"
                has_earnings_call = self._check_documents_exist(earnings_query)
            
            # Determine completeness
            missing = []
            if not has_sec_filing:
                missing.append("SEC filing")
            if has_earnings and not has_earnings_call:
                missing.append("earnings call")
            
            complete = len(missing) == 0
            
            availability[ticker] = {
                "complete": complete,
                "sec_filing": has_sec_filing,
                "earnings_call": has_earnings_call if has_earnings else None,
                "requires_earnings_call": has_earnings,
                "missing": missing
            }
            
            status = "✓" if complete else "✗"
            print(f"  {status} {ticker}: {', '.join(missing) if missing else 'Complete'}")
        
        complete_count = sum(1 for v in availability.values() if v["complete"])
        print(f"\n  Summary: {complete_count}/{len(COMPANIES)} companies complete")
        
        return availability
    
    def find_latest_complete_quarter(self) -> Tuple[int, int]:
        """
        Find the most recent quarter with complete data for all companies.
        
        Returns:
            Tuple of (year, quarter)
        """
        print("\n🔍 Finding latest complete quarter...")
        
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        
        # Determine the most recent COMPLETED quarter
        # Quarters end on: Mar 31 (Q1), Jun 30 (Q2), Sep 30 (Q3), Dec 31 (Q4)
        # Companies typically file 10-Q/10-K within 45 days after quarter end
        
        if current_month >= 11:  # November or December - Q3 complete, Q4 in progress
            latest_complete_quarter = 3
            latest_complete_year = current_year
        elif current_month >= 8:  # August-October - Q2 complete, Q3 in progress
            latest_complete_quarter = 2
            latest_complete_year = current_year
        elif current_month >= 5:  # May-July - Q1 complete, Q2 in progress
            latest_complete_quarter = 1
            latest_complete_year = current_year
        else:  # January-April - Q4 of previous year complete, Q1 in progress
            latest_complete_quarter = 4
            latest_complete_year = current_year - 1
        
        print(f"  Current date: {current_date.strftime('%B %d, %Y')}")
        print(f"  Latest complete quarter should be: Q{latest_complete_quarter} {latest_complete_year}")
        
        # Start checking from the latest complete quarter and go back up to 8 quarters
        check_year = latest_complete_year
        check_quarter = latest_complete_quarter
        
        for i in range(8):
            print(f"\n  Checking Q{check_quarter} {check_year}...")
            availability = self.validate_data_availability(check_year, check_quarter)
            
            complete_count = sum(1 for v in availability.values() if v["complete"])
            
            if complete_count == len(COMPANIES):
                print(f"\n✓ Latest complete quarter: Q{check_quarter} {check_year}")
                return check_year, check_quarter
            
            # Move to previous quarter
            check_quarter -= 1
            if check_quarter < 1:
                check_quarter = 4
                check_year -= 1
        
        # Default to the latest complete quarter if no data found
        print(f"\n⚠️  No complete quarter found in search, defaulting to Q{latest_complete_quarter} {latest_complete_year}")
        return latest_complete_year, latest_complete_quarter
    

