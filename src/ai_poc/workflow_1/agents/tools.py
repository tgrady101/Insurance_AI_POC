"""
ADK Tools for Competitive Intelligence Analysis

These tools wrap the specialized analysis agents as ADK FunctionTools,
allowing the root LlmAgent to use them.

Includes utility functions for:
- Quarter detection (finding latest complete quarter)
- Data availability validation

Observability:
- Integrated with Arize AX for automatic tracing of all tool executions
"""

from typing import Any, Dict, Tuple
import json
import os
from datetime import datetime
from google.adk.tools.function_tool import FunctionTool
from google.cloud import discoveryengine_v1 as discoveryengine

# Initialize Arize AX tracing if credentials are available
try:
    from ..arize_tracing.arize_config import setup_arize_tracing
    if os.getenv("ARIZE_SPACE_ID") and os.getenv("ARIZE_API_KEY"):
        _tracer = setup_arize_tracing()
except ImportError:
    _tracer = None
    pass  # Tracing is optional

# Import config and specialized agents
from .config import (
    GCP_PROJECT_ID,
    DATA_STORE_ID,
    DATA_STORE_LOCATION,
    COMPANIES
)
from .financial_metrics_agent import FinancialMetricsAgent
from .competitive_positioning_agent import CompetitivePositioningAgent
from .strategic_initiatives_agent import StrategicInitiativesAgent
from .risk_outlook_agent import RiskOutlookAgent


# =============================================================================
# Utility Functions (formerly in UtilityAgent)
# =============================================================================

# Initialize Vertex AI Search client for validation queries
_search_client = discoveryengine.SearchServiceClient()
_serving_config = (
    f"projects/{GCP_PROJECT_ID}/locations/{DATA_STORE_LOCATION}/"
    f"collections/default_collection/dataStores/{DATA_STORE_ID}/"
    f"servingConfigs/default_config"
)


def _check_documents_exist(query: str, max_results: int = 3) -> bool:
    """
    Simple check if documents exist for a query (used for validation).
    
    Args:
        query: Search query string
        max_results: Number of results to check
    
    Returns:
        True if any documents found, False otherwise
    """
    request = discoveryengine.SearchRequest(
        serving_config=_serving_config,
        query=query,
        page_size=max_results,
    )
    
    try:
        response = _search_client.search(request)
        return len(list(response.results)) > 0
    except Exception as e:
        print(f"⚠️  Validation check error: {e}")
        return False


def _validate_data_for_quarter(year: int, quarter: int) -> Dict[str, Dict]:
    """
    Validate that required documents are available for all companies.
    
    Args:
        year: Target year
        quarter: Target quarter (1-4)
    
    Returns:
        Dictionary mapping ticker to availability status
    """
    print(f"\n📋 Validating data availability for Q{quarter} {year}...")
    
    availability = {}
    
    for company in COMPANIES:
        ticker = company["ticker"]
        has_earnings = company["has_earnings_calls"]
        
        # Check for SEC filing (10-K or 10-Q)
        filing_type = "10-K" if quarter == 4 else "10-Q"
        sec_query = f"{ticker} {filing_type} {year} Q{quarter}"
        has_sec_filing = _check_documents_exist(sec_query)
        
        # Check for earnings call (if applicable)
        has_earnings_call = False
        if has_earnings:
            earnings_query = f"{ticker} earnings call {year} Q{quarter}"
            has_earnings_call = _check_documents_exist(earnings_query)
        
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


def _find_latest_complete_quarter() -> Tuple[int, int]:
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
    if current_month >= 11:  # November or December - Q3 complete
        latest_complete_quarter = 3
        latest_complete_year = current_year
    elif current_month >= 8:  # August-October - Q2 complete
        latest_complete_quarter = 2
        latest_complete_year = current_year
    elif current_month >= 5:  # May-July - Q1 complete
        latest_complete_quarter = 1
        latest_complete_year = current_year
    else:  # January-April - Q4 of previous year complete
        latest_complete_quarter = 4
        latest_complete_year = current_year - 1
    
    print(f"  Current date: {current_date.strftime('%B %d, %Y')}")
    print(f"  Latest complete quarter should be: Q{latest_complete_quarter} {latest_complete_year}")
    
    # Check from latest complete quarter, go back up to 8 quarters
    check_year = latest_complete_year
    check_quarter = latest_complete_quarter
    
    for i in range(8):
        print(f"\n  Checking Q{check_quarter} {check_year}...")
        availability = _validate_data_for_quarter(check_year, check_quarter)
        
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
    print(f"\n⚠️  No complete quarter found, defaulting to Q{latest_complete_quarter} {latest_complete_year}")
    return latest_complete_year, latest_complete_quarter


# =============================================================================
# Specialized Agents
# =============================================================================

_financial_agent = FinancialMetricsAgent()
_competitive_agent = CompetitivePositioningAgent()
_strategic_agent = StrategicInitiativesAgent()
_risk_agent = RiskOutlookAgent()


def find_latest_quarter() -> dict[str, Any]:
    """
    Automatically detect the most recent quarter with complete data for all 7 companies.
    
    Returns:
        Dictionary with 'year' (int), 'quarter' (int), 'status' (str), and 'message' (str).
        Example: {'year': 2024, 'quarter': 3, 'status': 'complete', 'message': '...'}
    """
    year, quarter = _find_latest_complete_quarter()
    return {
        "year": year,
        "quarter": quarter,
        "status": "complete",
        "message": f"Latest complete quarter: Q{quarter} {year}"
    }


def validate_data_availability(year: int, quarter: int) -> dict[str, Any]:
    """
    Check if required SEC filings and earnings call transcripts are available 
    for all 7 companies for a specific quarter.
    
    Note: Berkshire Hathaway (BRK.B) does not hold earnings calls by design,
    so only SEC filings are required for that company.
    
    Args:
        year: Year to check (e.g., 2024)
        quarter: Quarter to check (1-4)
    
    Returns:
        Dictionary with keys: year (int), quarter (int), total_companies (int),
        complete_companies (int), all_complete (bool), missing_data (list of str).
    
    Raises:
        ValueError: If quarter is not in range 1-4 or year is invalid
    """
    # Validate quarter range
    if not isinstance(quarter, int) or quarter < 1 or quarter > 4:
        raise ValueError(f"Quarter must be between 1 and 4, got: {quarter}")
    
    # Validate year range (reasonable bounds)
    from datetime import datetime
    current_year = datetime.now().year
    if not isinstance(year, int) or year < 2020:
        raise ValueError(f"Year must be 2020 or later, got: {year}")
    
    # Check if requesting future data
    current_quarter = (datetime.now().month - 1) // 3 + 1
    if year > current_year or (year == current_year and quarter > current_quarter):
        # Future quarter - return empty result
        return {
            "year": year,
            "quarter": quarter,
            "total_companies": 7,
            "complete_companies": 0,
            "complete_list": "",
            "missing_count": 7,
            "missing_summary": "Data not yet available (future quarter)",
            "all_complete": False,
            "status": "Future quarter - no data available"
        }
    
    availability = _validate_data_for_quarter(year, quarter)
    
    # Format results - use simple strings for better ADK compatibility
    complete_count = sum(1 for status in availability.values() if status['complete'])
    complete_companies = [ticker for ticker, status in availability.items() if status['complete']]
    missing_data = []
    
    for ticker, status in availability.items():
        if not status['complete']:
            missing = []
            if not status['sec_filing']:
                missing.append("SEC filing")
            if not status['earnings_call'] and status.get('requires_earnings_call', True):
                missing.append("earnings call")
            if missing:
                missing_data.append(f"{ticker}: {', '.join(missing)}")
    
    # Return simple types for ADK automatic function calling
    return {
        "year": year,
        "quarter": quarter,
        "total_companies": 7,
        "complete_companies": complete_count,
        "complete_list": ", ".join(complete_companies),
        "missing_count": len(missing_data),
        "missing_summary": "; ".join(missing_data) if missing_data else "None",
        "all_complete": complete_count == 7,
        "status": "complete" if complete_count == 7 else f"{complete_count}/7 companies ready"
    }


async def extract_financial_metrics(year: int, quarter: int) -> dict[str, Any]:
    """
    Extract 13 key financial metrics for COMMERCIAL INSURANCE SEGMENT ONLY.
    
    **CRITICAL: Extract Commercial Lines metrics only, exclude Personal Lines.**
    
    Metrics include (Commercial segment only):
    - Combined Ratio (loss ratio + expense ratio) - COMMERCIAL ONLY
    - Net Written Premiums - COMMERCIAL ONLY
    - Net Earned Premiums - COMMERCIAL ONLY
    - Underwriting Income - COMMERCIAL ONLY
    - Net Investment Income (allocated to Commercial)
    - Net Income (Commercial segment)
    - Book Value Per Share (if segmented)
    - Return on Equity (ROE) - COMMERCIAL ONLY
    - Reserve Development - COMMERCIAL ONLY
    - Catastrophe Losses - COMMERCIAL ONLY
    - Prior Year Development - COMMERCIAL ONLY
    
    Note: Companies often report combined results. Extract Commercial segment data
    from segmented financial disclosures in 10-K/10-Q filings.
    
    Args:
        year: Year of analysis (e.g., 2024)
        quarter: Quarter 1-4
    
    Returns:
        Dictionary containing COMMERCIAL SEGMENT metrics for all companies plus
        comparative analysis highlighting leaders/laggards in Commercial Lines.
    """
    print(f"\\n📊 Extracting financial metrics for Q{quarter} {year}...")
    all_metrics = await _financial_agent.extract_all_companies_async(year, quarter)
    
    return {
        "year": year,
        "quarter": quarter,
        "metrics_by_company": all_metrics,
        "status": "complete",
        "companies_analyzed": len(all_metrics)
    }


async def analyze_competitive_positioning(year: int, quarter: int) -> dict[str, Any]:
    """
    Analyze competitive positioning in COMMERCIAL INSURANCE MARKET ONLY.
    
    **FOCUS: Commercial Lines market analysis - exclude Personal Lines.**
    
    Analysis includes (Commercial segment only):
    - Commercial Lines market share trends
    - Commercial premium growth vs peers
    - Commercial pricing power indicators (rate changes)
    - Commercial product mix (GL, WC, Property, Professional, Specialty)
    - Geographic distribution of Commercial business
    - Commercial Lines performance rankings
    - The Hartford's Commercial Lines position vs competitors
    
    Args:
        year: Year of analysis
        quarter: Quarter 1-4
    
    Returns:
        Dictionary with Commercial market overview, company rankings in Commercial,
        and Hartford's Commercial Lines specific insights.
    """
    print(f"\\n🏆 Analyzing competitive positioning for Q{quarter} {year}...")
    analysis = await _competitive_agent._analyze_positioning_async(year, quarter, None)
    
    return {
        "year": year,
        "quarter": quarter,
        "analysis": analysis,
        "status": "complete"
    }


async def identify_strategic_initiatives(year: int, quarter: int) -> dict[str, Any]:
    """
    Identify strategic initiatives affecting COMMERCIAL INSURANCE BUSINESS.
    
    **FOCUS: Commercial Lines initiatives only - exclude Personal Lines moves.**
    
    Categories tracked (Commercial segment focus):
    - M&A and Partnerships affecting Commercial Lines
    - Commercial Product Innovation (new coverages, specialty lines)
    - Technology and Digital for Commercial customers (portals, underwriting AI)
    - Organizational Changes in Commercial divisions
    - Capital Allocation to Commercial vs other segments
    
    Args:
        year: Year of analysis
        quarter: Quarter 1-4
    
    Returns:
        Dictionary with COMMERCIAL initiatives by company, Commercial industry themes,
        and most active companies in Commercial Lines innovation.
    """
    print(f"\n🎯 Identifying strategic initiatives for Q{quarter} {year}...")
    analysis = await _strategic_agent._analyze_initiatives_async(year, quarter)
    
    return {
        "year": year,
        "quarter": quarter,
        "initiatives": analysis,
        "status": "complete"
    }


async def assess_risk_outlook(year: int, quarter: int) -> dict[str, Any]:
    """
    Assess risk exposure for COMMERCIAL INSURANCE SEGMENT.
    
    **FOCUS: Commercial Lines risk - exclude Personal Lines exposures.**
    
    Risk categories (Commercial segment):
    - Catastrophe Risk for Commercial (property, BI exposure)
    - Reserve Risk in Commercial Lines (long-tail casualty)
    - Economic Risk affecting Commercial (recession impact, E&O claims)
    - Operational Risk in Commercial (underwriting cycle, social inflation)
    - Regulatory and Legal Risk for Commercial (class actions, D&O)
    
    Also captures management's forward-looking guidance for Commercial segment.
    
    Args:
        year: Year of analysis
        quarter: Quarter 1-4
    
    Returns:
        Dictionary with COMMERCIAL risk assessments by company and Commercial
        industry-wide risk summary.
    """
    print(f"\\n⚠️  Assessing risk and outlook for Q{quarter} {year}...")
    analysis = await _risk_agent._analyze_risk_outlook_async(year, quarter, None)
    
    return {
        "year": year,
        "quarter": quarter,
        "risk_analysis": analysis,
        "status": "complete"
    }


# Create ADK FunctionTools from the functions above
FindLatestQuarterTool = FunctionTool(func=find_latest_quarter)
ValidateDataTool = FunctionTool(func=validate_data_availability)
FinancialMetricsTool = FunctionTool(func=extract_financial_metrics)
CompetitivePositioningTool = FunctionTool(func=analyze_competitive_positioning)
StrategicInitiativesTool = FunctionTool(func=identify_strategic_initiatives)
RiskOutlookTool = FunctionTool(func=assess_risk_outlook)


# Export all tools
__all__ = [
    'FindLatestQuarterTool',
    'ValidateDataTool',
    'FinancialMetricsTool',
    'CompetitivePositioningTool',
    'StrategicInitiativesTool',
    'RiskOutlookTool'
]
