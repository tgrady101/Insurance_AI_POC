"""
ADK Tools for Competitive Intelligence Analysis

These tools wrap the specialized analysis agents as ADK FunctionTools,
allowing the root LlmAgent to use them.

Observability:
- Integrated with Arize AX for automatic tracing of all tool executions
"""

from typing import Any
import json
import os
from google.adk.tools.function_tool import FunctionTool

# Initialize Arize AX tracing if credentials are available
try:
    from ..arize_tracing.arize_config import setup_arize_tracing
    if os.getenv("ARIZE_SPACE_ID") and os.getenv("ARIZE_API_KEY"):
        _tracer = setup_arize_tracing()
except ImportError:
    _tracer = None
    pass  # Tracing is optional

# Import the specialized agents
from .utility_agent import UtilityAgent
from .financial_metrics_agent import FinancialMetricsAgent
from .competitive_positioning_agent import CompetitivePositioningAgent
from .strategic_initiatives_agent import StrategicInitiativesAgent
from .risk_outlook_agent import RiskOutlookAgent


# Initialize the specialized agents globally (shared across tool calls)
# Note: UtilityAgent is only used for utility functions (quarter detection, validation)
# Document retrieval is handled by Vertex AI Search grounding in each agent's LLM
_data_agent = UtilityAgent()
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
    year, quarter = _data_agent.find_latest_complete_quarter()
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
    
    availability = _data_agent.validate_data_availability(year, quarter)
    
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
