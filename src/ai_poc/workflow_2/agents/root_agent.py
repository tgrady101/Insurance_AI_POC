"""
Root ADK Agent for Competitive Intelligence System

This is the main orchestrator agent using Google ADK's Agent class.
It coordinates the analysis workflow and synthesizes the final report.

Uses built-in ADK grounding:
- Vertex AI Search for uploaded SEC filings and earnings calls
- Google Search for supplemental industry context and web sources

Observability:
- Integrated with Arize AX for tracing and evaluation
"""

from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from typing import Optional, Dict
import json
from datetime import datetime
import os
import time
import asyncio

# Initialize Arize AX tracing if credentials are available
try:
    from ..arize_tracing.arize_config import setup_arize_tracing
    _arize_initialized = False
    if os.getenv("ARIZE_SPACE_ID") and os.getenv("ARIZE_API_KEY"):
        setup_arize_tracing()
        _arize_initialized = True
except ImportError:
    _arize_initialized = False
    pass  # Tracing is optional

from .config import (
    DEFAULT_MODEL,
    TEMPERATURE,
    ROOT_AGENT_NAME,
    ROOT_AGENT_DESCRIPTION,
    APP_NAME,
    REPORT_OUTPUT_DIR,
    COMPANIES,
    GCP_PROJECT_ID,
    GCP_LOCATION,
    DATA_STORE_ID,
    GENERATION_CONFIG,
    REQUEST_TIMEOUT
)
from .tools import (
    FindLatestQuarterTool,
    ValidateDataTool,
    FinancialMetricsTool,
    CompetitivePositioningTool,
    StrategicInitiativesTool,
    RiskOutlookTool
)


class CompetitiveIntelligenceRootAgent:
    """
    Root ADK agent that orchestrates competitive intelligence analysis.
    
    This agent uses Google ADK's Agent with specialized tools to:
    1. Determine the target quarter (auto-detect or specified)
    2. Validate data availability
    3. Coordinate analysis across 5 dimensions:
       - Financial Metrics
       - Competitive Positioning
       - Strategic Initiatives
       - Risk & Outlook
    4. Synthesize findings into comprehensive report
    5. Generate executive summary focused on The Hartford
    """
    
    def __init__(self):
        """Initialize the root ADK agent with all tools and grounding."""
        
        # Build Vertex AI Search datastore path
        self.datastore_path = (
            f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}/"
            f"collections/default_collection/dataStores/{DATA_STORE_ID}"
        )
        
        # System instruction for the root agent
        self.system_instruction = """
You are the Competitive Intelligence Orchestrator for The Hartford Financial Services Group.

Your mission is to generate comprehensive quarterly competitive intelligence reports 
analyzing The Hartford (HIG) and its 6 major competitors in the COMMERCIAL INSURANCE segment:
- Travelers (TRV)
- Chubb (CB)
- Berkshire Hathaway (BRK.B)
- AIG
- CNA
- W.R. Berkley (WRB)

**CRITICAL: COMMERCIAL SEGMENT FOCUS ONLY**
All analysis must focus exclusively on COMMERCIAL LINES business:
- Commercial Property & Casualty
- Workers' Compensation
- General Liability
- Professional Liability
- Specialty Commercial Lines

EXCLUDE:
- Personal Lines (auto, homeowners)
- Life Insurance
- Retirement/Asset Management
- Other non-commercial segments

WORKFLOW:
1. Determine target quarter (use find_latest_quarter if not specified)
2. Validate data availability for all companies
3. Execute analyses in this order:
   a. Extract financial metrics for COMMERCIAL SEGMENT ONLY
   b. Analyze competitive positioning in COMMERCIAL LINES
   c. Identify strategic initiatives affecting COMMERCIAL business
   d. Assess risk and outlook for COMMERCIAL segment
4. Synthesize findings into executive summary

CRITICAL NOTES:
- **COMMERCIAL SEGMENT ONLY** - Ignore Personal Lines, Life, and other segments
- **Company-Specific Segment Names:**
  * TRV: "Business Insurance" segment
  * HIG: "Business Insurance" segment (also called "Commercial Lines")
  * AIG: "North America Commercial" segment ONLY (exclude "International Commercial" and "Global Personal")
  * CB: "North America Commercial P&C" segment
  * CNA: "Commercial" segment
  * WRB: "Insurance" segment
  * BRK.B: "BH Primary" segment (exclude GEICO and BHRG)
- Berkshire Hathaway (BRK.B) does not hold earnings calls by design
- Always prioritize Hartford's Commercial Lines insights
- Use factual data from tools only - no speculation
- When companies report combined results, extract COMMERCIAL segment data from segment tables in Notes
- Highlight competitive advantages/disadvantages vs peers in Commercial
- Note emerging Commercial insurance trends affecting Hartford

CITATION REQUIREMENTS:
- **ALWAYS cite sources** for every claim, metric, and insight
- Use inline citations in format: [Source: Company 10-K Q3 2025], [Source: Company Earnings Call Q2 2025]
- Prefer data from the uploaded document store (SEC filings, earnings calls)
- Web search allowed for supplemental industry context
- Every financial metric MUST have a citation
- Every strategic initiative MUST have a citation
- Every risk assessment MUST have a citation

OUTPUT FORMAT:
Generate a comprehensive markdown report with:

**IMPORTANT SCOPE NOTICE** (include at top of report):
```
> **Analysis Scope Note**: This competitive intelligence report analyzes publicly traded 
> US-domiciled commercial insurance companies only. The following major commercial insurers 
> were excluded from this POC analysis:
> - **Liberty Mutual** (private company - not publicly traded)
> - **Zurich Insurance Group** (non-US company - domiciled in Switzerland)
> - **Tokio Marine Holdings** (non-US company - domiciled in Japan)
> 
> Analysis focuses on the 7 major public US commercial insurers with available SEC filings 
> and earnings call transcripts.
```

Report Sections:
- Executive Summary (3-5 key findings for Hartford's COMMERCIAL LINES leadership with citations)
- Commercial Segment Financial Performance (metrics comparison table with citations for each metric)
  * Include these key metrics in the table:
    - Net Written Premiums Growth (Commercial)
    - Combined Ratio (Commercial)
    - Loss Ratio (Commercial)
    - Expense Ratio (Commercial)
    - Underwriting Income (Commercial)
    - Catastrophe Losses (Commercial)
    - Prior Year Development (Commercial)
  * **CRITICAL DATA SOURCE PRIORITY FOR THIS TABLE ONLY**: 
    - PRIMARY SOURCE: Form 10-Q/10-K SEC filings (use segment tables in Notes section)
    - FALLBACK ONLY: Earnings call transcripts (only if metric not disclosed in 10-Q/10-K)
    - For TRV: Use "Business Insurance" segment from Note 2 SEGMENT INFORMATION in 10-Q
    - For HIG: Use "Business Insurance" segment from segment tables in 10-Q Notes
    - For AIG: Use "North America Commercial" row ONLY from Note 3 SEGMENT INFORMATION (NOT International Commercial, NOT Total General Insurance)
    - For CB, CNA, WRB, BRK.B: Extract from respective commercial segment tables in 10-Q Notes
    - Verify document year matches requested quarter (reject prior year data)
    - Do NOT use Financial Supplements - use official Form 10-Q only for table metrics
- Competitive Position in Commercial Lines (Hartford's rank and gaps with citations)
  * **EXCLUDE Berkshire Hathaway (BRK.B) from competitive positioning analysis** - no earnings call data available
  * Focus positioning analysis on the 6 companies with earnings calls: HIG, TRV, CB, AIG, CNA, WRB
- Strategic Landscape for Commercial Insurance:
  * Individual company breakdowns (HIG, TRV, CB, AIG, CNA, WRB) - each with 3-5 key topics from earnings calls
  * Industry summary section synthesizing common themes and competitive dynamics
  * Hartford's positioning relative to peers
- Commercial Segment Risk Assessment (Hartford-specific concerns + industry risks with citations)
- Recommendations (2-3 strategic implications for Hartford's Commercial business)
- References (consolidated list of all sources cited)

**CRITICAL CITATION RULES:**
- Every factual claim must be cited
- Every number must be cited
- Grounding sources will be automatically provided - use them extensively
- Reference grounded content using inline citations
- Include document dates when citing
- Be concise but comprehensive. Use data to support all claims.
**REMINDER: All metrics and analysis must be COMMERCIAL SEGMENT ONLY.**

**DATA SOURCES:**
You have access to:
1. **Vertex AI Search Datastore** (PRIMARY): SEC filings (10-K, 10-Q) and earnings call transcripts 
   for all 7 companies via FunctionTools. This is the authoritative source for financial data.
2. **Your analysis tools**: Use the provided FunctionTools to retrieve and analyze data.
3. When citing, reference specific documents: [Company 10-K Q3 2025], [Company Earnings Call Q2 2025]

Always use the FunctionTools to retrieve company-specific data. The tools will access the 
uploaded datastore and provide comprehensive citations.
"""
        
        # Create the ADK Agent with tools and grounding configuration
        tools = [
            FindLatestQuarterTool,
            ValidateDataTool,
            FinancialMetricsTool,
            CompetitivePositioningTool,
            StrategicInitiativesTool,
            RiskOutlookTool
        ]
        
        self.agent = Agent(
            name=ROOT_AGENT_NAME,
            model=DEFAULT_MODEL,
            description=ROOT_AGENT_DESCRIPTION,
            instruction=self.system_instruction,
            tools=tools,
            generate_content_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": 8192,
            }
        )
        
        # Create session service and runner
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service
        )
        
        print(f"[OK] {ROOT_AGENT_NAME} initialized with ADK")
        print(f"  Model: {DEFAULT_MODEL}")
        print(f"  Tools: {len(tools)} specialized analysis tools")
        print(f"  Data Source: Vertex AI Search via FunctionTools ({DATA_STORE_ID})")
        print(f"  Citations: Provided by specialized agents")
        if _arize_initialized:
            print(f"  Observability: Arize AX tracing enabled ✓")
            print(f"  View traces at: https://app.arize.com")
        else:
            print(f"  Observability: Not configured (set ARIZE_SPACE_ID and ARIZE_API_KEY to enable)")
    
    async def generate_report(
        self,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        user_id: str = "analyst_1",
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Generate competitive intelligence report using ADK agent.
        
        Args:
            year: Target year (auto-detects if None)
            quarter: Target quarter 1-4 (auto-detects if None)
            user_id: User identifier for session
            session_id: Session ID (auto-generated if None)
        
        Returns:
            Dictionary with report content and metadata
        """
        print("\n" + "="*80)
        print("COMPETITIVE INTELLIGENCE REPORT GENERATION (ADK)")
        print("="*80)
        
        # Create session
        if session_id is None:
            session_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
        
        # Construct user query
        if year and quarter:
            user_query = f"Generate a comprehensive competitive intelligence report for Q{quarter} {year}."
        else:
            user_query = "Generate a comprehensive competitive intelligence report for the most recent complete quarter."
        
        print(f"\n🤖 Invoking ADK agent with query: {user_query}")
        
        # Prepare user message
        content = types.Content(
            role='user',
            parts=[types.Part(text=user_query)]
        )
        
        # Run the agent with retry logic for network timeouts
        final_response_text = ""
        tool_calls_made = []
        grounding_metadata = None
        max_retries = 2
        retry_delay = 5
        
        for attempt in range(max_retries + 1):
            try:
                # Add timeout wrapper
                async def run_with_timeout():
                    nonlocal final_response_text, tool_calls_made, grounding_metadata
                    
                    async for event in self.runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=content
                    ):
                        # Track tool usage
                        if hasattr(event, 'content') and event.content and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    tool_calls_made.append(part.function_call.name)
                        
                        # Capture final response and grounding metadata
                        if event.is_final_response():
                            if event.content and event.content.parts:
                                # Extract text from all text parts (response may also have function_call parts)
                                text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                                if text_parts:
                                    # Update with latest text response (may be multiple final responses with function calls)
                                    final_response_text = ''.join(text_parts)
                            
                            # Extract grounding metadata if available
                            if hasattr(event, 'grounding_metadata'):
                                grounding_metadata = event.grounding_metadata
                            # Continue processing - don't break, agent may make multiple tool calls
                
                # Run with timeout (5 minutes for full report)
                await asyncio.wait_for(run_with_timeout(), timeout=REQUEST_TIMEOUT)
                break  # Success - exit retry loop
                
            except (asyncio.TimeoutError, ConnectionError, Exception) as e:
                if attempt < max_retries:
                    print(f"  ⚠️  Attempt {attempt + 1} failed: {type(e).__name__}")
                    print(f"  Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"  ✗ All attempts failed: {e}")
                    raise Exception(f"Report generation failed after {max_retries + 1} attempts: {e}")
        
        print(f"\n✓ Agent completed analysis")
        print(f"  Tools used: {len(set(tool_calls_made))} unique tools")
        print(f"  Total tool calls: {len(tool_calls_made)}")
        
        if grounding_metadata:
            print(f"  Grounding: {len(grounding_metadata.grounding_chunks or [])} chunks used")
            if hasattr(grounding_metadata, 'web_search_queries'):
                print(f"  Web searches: {len(grounding_metadata.web_search_queries or [])} queries")
        
        # Save report
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "year": year,
            "quarter": quarter,
            "report_markdown": final_response_text,
            "tool_calls": tool_calls_made,
            "session_id": session_id,
            "grounding_metadata": {
                "chunks_used": len(grounding_metadata.grounding_chunks) if grounding_metadata and grounding_metadata.grounding_chunks else 0,
                "web_searches": len(grounding_metadata.web_search_queries) if grounding_metadata and hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries else 0
            }
        }
        
        # Export to file
        os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
        filename = f"ci_report_Q{quarter}_{year}.md" if year and quarter else f"ci_report_{session_id}.md"
        filepath = os.path.join(REPORT_OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_response_text)
        
        print(f"\n✓ Report saved to: {filepath}")
        
        return report_data
    
    def generate_report_sync(
        self,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        user_id: str = "analyst_1",
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Synchronous wrapper for generate_report.
        
        Use this from non-async code (e.g., standard Python scripts).
        """
        import asyncio
        return asyncio.run(
            self.generate_report(year, quarter, user_id, session_id)
        )


# Convenience function for quick usage
def create_agent() -> CompetitiveIntelligenceRootAgent:
    """Create and return a new instance of the root agent."""
    return CompetitiveIntelligenceRootAgent()
