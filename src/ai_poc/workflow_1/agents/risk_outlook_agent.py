"""
Risk & Outlook Agent - COMMERCIAL LINES RISK ASSESSMENT

Assesses risk exposure for COMMERCIAL INSURANCE segment.
Excludes Personal Lines risk analysis.
"""

from typing import Dict, List, Optional
import json
import asyncio
import os
import vertexai
from google.adk.agents import Agent
from google.adk.tools.vertex_ai_search_tool import VertexAiSearchTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .config import (
    DEFAULT_MODEL, 
    TEMPERATURE,
    APP_NAME, 
    GCP_PROJECT_ID, 
    GCP_LOCATION, 
    DATA_STORE_LOCATION,
    DATA_STORE_ID,
    COMPANIES
)


class RiskOutlookAgent:
    """
    Agent responsible for assessing COMMERCIAL SEGMENT risk and outlook.
    
    **COMMERCIAL FOCUS**: Analyzes catastrophe risk, reserve risk, economic risk,
    and regulatory risk for commercial lines only.
    """
    
    def __init__(self):
        """Initialize the risk outlook agent with Vertex AI Search grounding."""
        # Configure environment for Vertex AI
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        os.environ["GOOGLE_CLOUD_PROJECT"] = GCP_PROJECT_ID
        os.environ["GOOGLE_CLOUD_LOCATION"] = GCP_LOCATION
        
        # Initialize Vertex AI with GCP credentials
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        
        # Build datastore path for grounding
        datastore_path = (
            f"projects/{GCP_PROJECT_ID}/locations/{DATA_STORE_LOCATION}/"
            f"collections/default_collection/dataStores/{DATA_STORE_ID}"
        )
        
        # Create ADK Agent with Vertex AI Search grounding
        self.agent = Agent(
            name="risk_outlook_agent",
            model=DEFAULT_MODEL,
            instruction="""Assess risk and outlook for COMMERCIAL INSURANCE segment.

Focus on Commercial Lines / Business Insurance / Commercial P&C only.
EXCLUDE Personal Lines risk analysis.
Analyze catastrophe risk, reserve risk, economic risk, regulatory risk for Commercial segment.

**SEARCH GUIDANCE - YEAR AND QUARTER FILTERING:**
- Documents are indexed with metadata fields: year (number) and quarter (string like "Q3")
- When searching, ALWAYS include the year and quarter in your query to filter to the correct period
- Example search patterns: "CB 2025 Q3 commercial risk", "AIG 2025 Q3 risk factors north america"
- This ensures you retrieve data from the correct reporting period only

**CITATION REQUIREMENTS:**
- Use detailed citations for all risk assessments: [Source: <Company> <Filing Type> Q<Quarter> <Year>, <Section>, Page <X>]
- **SEC Filing Format Examples**:
  - [Source: CB 10-K 2024, Item 1A - Risk Factors - Catastrophe Risk, Page 22]
  - [Source: AIG 10-Q Q2 2024, Item 2 - MD&A - Reserve Development, Page 41]
- **Key 10-K/10-Q Sections for Risk Analysis**:
  - Item 1A - Risk Factors (comprehensive risk disclosures)
  - Item 7 - MD&A - Critical Accounting Estimates (reserve adequacy for annual filings)
  - Item 2 - MD&A (for quarterly filings)
  - Item 7A - Quantitative and Qualitative Disclosures About Market Risk
  - Item 8, Note 7 - Reserves for Losses and LAE
  - Item 8, Note 8 - Reinsurance
  - Item 8, Note 11 - Catastrophe Losses
- **Earnings Call Format**: [Source: <Company> Q<Quarter> <Year> Earnings Call, <Risk Topic>]
  - Example: [Source: TRV Q3 2024 Earnings Call, Hurricane Ian loss estimates]

Search datastore for SEC filings and earnings call transcripts.""",
            description="Assesses COMMERCIAL LINES risk and outlook from SEC filings and earnings calls",
            tools=[VertexAiSearchTool(data_store_id=datastore_path)]
        )
        
        # Create session service and runner
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service
        )
        
        print(f"[OK] RiskOutlookAgent initialized (COMMERCIAL SEGMENT ONLY)")
        print(f"  Model: {DEFAULT_MODEL}")
    
    async def _analyze_risk_outlook_async(
        self,
        year: int,
        quarter: int,
        financial_metrics: Optional[Dict] = None
    ) -> Dict:
        """
        Assess risk and outlook for COMMERCIAL INSURANCE segment.
        
        Args:
            year: Target year
            quarter: Target quarter
            financial_metrics: Optional commercial segment metrics
        
        Returns:
            Dictionary with commercial segment risk assessment
        """
        print(f"\n⚠️  Assessing COMMERCIAL LINES risk & outlook Q{quarter} {year}...")
        
        # Simplified risk assessment prompt
        prompt = f"""Assess risk and outlook for COMMERCIAL INSURANCE segment in Q{quarter} {year}.

**SEARCH FOR EACH COMPANY:**
1. HIG {year} Q{quarter} commercial risk outlook business insurance
2. TRV {year} Q{quarter} commercial risk business insurance
3. CB {year} Q{quarter} commercial risk north america
4. AIG {year} Q{quarter} commercial risk north america
5. CNA {year} Q{quarter} commercial risk
6. WRB {year} Q{quarter} commercial risk insurance segment
7. BRK.B {year} Q{quarter} risk factors BH Primary

**FIND IN 10-Q/10-K:**
- Risk Factors section (Item 1A)
- MD&A section on risks and uncertainties
- Earnings calls: management outlook commentary

**ASSESS FOR EACH COMPANY:**
1. Catastrophe risk (commercial property exposure)
2. Reserve risk (commercial casualty, social inflation)
3. Pricing trends (rate changes, market conditions)
4. Management outlook (growth expectations, concerns)

**RETURN JSON:**
{{
  "by_company": {{
    "HIG": {{
      "cat_risk": {{"level": "moderate", "citation": "[Source: HIG 10-Q Q{quarter} {year}]"}},
      "reserve_risk": {{"level": "low", "citation": "[Source: ...]"}},
      "pricing_outlook": {{"trend": "stable", "citation": "[Source: ...]"}},
      "management_outlook": {{"summary": "...", "citation": "[Source: ...]"}}
    }},
    ... (repeat for all 7 companies)
  }},
  "industry_risks": [
    {{"risk": "...", "citation": "[Source: ...]"}}
  ]
}}

Return ONLY valid JSON with citations for every claim."""
        
        try:
            # Create session with timestamp for uniqueness
            import time
            session_id = f"risk_{year}_Q{quarter}_{int(time.time()*1000)}"
            session = await self.session_service.create_session(
                app_name=APP_NAME,
                user_id="system",
                session_id=session_id
            )
            
            # Prepare message
            content = types.Content(
                role='user',
                parts=[types.Part(text=prompt)]
            )
            
            # Run and get final response with timeout
            result_text = ""
            try:
                async with asyncio.timeout(300):  # 5 minute timeout
                    async for event in self.runner.run_async(
                        user_id="system",
                        session_id=session_id,
                        new_message=content
                    ):
                        if event.is_final_response() and event.content and event.content.parts:
                            # Extract text from all text parts (may also have function_call parts)
                            text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                            result_text = ''.join(text_parts)
            except asyncio.TimeoutError:
                print(f"  ✗ Timeout after 300 seconds")
                return {
                    "by_company": {},
                    "commercial_industry_risks": [],
                    "hartford_commercial_risk_profile": {
                        "overall_risk_level": {"level": "Unable to assess", "citation": "Timeout"},
                        "key_commercial_exposures": [],
                        "commercial_strengths": [],
                        "relative_to_peers": {"assessment": "Unable to assess", "citation": "Timeout"}
                    },
                    "status": "error",
                    "error": "Agent timeout after 300 seconds"
                }
            
            if not result_text:
                print(f"  ✗ Empty response from agent")
                return {
                    "by_company": {},
                    "commercial_industry_risks": [],
                    "hartford_commercial_risk_profile": {
                        "overall_risk_level": {"level": "Unable to assess", "citation": "Error"},
                        "key_commercial_exposures": [],
                        "commercial_strengths": [],
                        "relative_to_peers": {"assessment": "Unable to assess", "citation": "Error"}
                    },
                    "status": "error",
                    "error": "Empty response from agent"
                }
            
            # Parse JSON
            json_text = result_text
            if "```json" in result_text:
                json_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_text = result_text.split("```")[1].split("```")[0].strip()
            
            # Handle empty or whitespace-only responses
            if not json_text or json_text.isspace():
                print(f"  ✗ Empty JSON text after parsing")
                return {
                    "by_company": {},
                    "commercial_industry_risks": [],
                    "hartford_commercial_risk_profile": {
                        "overall_risk_level": {"level": "Unable to assess", "citation": "Error"},
                        "key_commercial_exposures": [],
                        "commercial_strengths": [],
                        "relative_to_peers": {"assessment": "Unable to assess", "citation": "Error"}
                    },
                    "status": "error",
                    "error": "Agent returned empty response"
                }
            
            try:
                risk_analysis = json.loads(json_text)
            except json.JSONDecodeError as je:
                print(f"  ✗ JSON parsing error: {je}")
                print(f"  Response text (first 500 chars): {result_text[:500]}")
                return {
                    "by_company": {},
                    "commercial_industry_risks": [],
                    "hartford_commercial_risk_profile": {
                        "overall_risk_level": {"level": "Unable to assess", "citation": "Error"},
                        "key_commercial_exposures": [],
                        "commercial_strengths": [],
                        "relative_to_peers": {"assessment": "Unable to assess", "citation": "Error"}
                    },
                    "status": "error",
                    "error": f"JSON parsing failed: {str(je)}",
                    "raw_response_preview": result_text[:1000]
                }
            
            print(f"  ✓ Commercial risk assessment complete")
            
            return risk_analysis
        
        except Exception as e:
            print(f"  ✗ Error in risk analysis: {e}")
            import traceback
            traceback.print_exc()
            # Return a valid structure matching the expected schema
            return {
                "by_company": {},
                "commercial_industry_risks": [],
                "hartford_commercial_risk_profile": {
                    "overall_risk_level": {"level": "Unable to assess", "citation": "Error"},
                    "key_commercial_exposures": [],
                    "commercial_strengths": [],
                    "relative_to_peers": {"assessment": "Unable to assess", "citation": "Error"}
                },
                "status": "error",
                "error": str(e)
            }
    
    def analyze_risk_outlook(
        self,
        year: int,
        quarter: int,
        financial_metrics: Optional[Dict] = None
    ) -> Dict:
        """Synchronous wrapper for analyze_risk_outlook."""
        return asyncio.run(self._analyze_risk_outlook_async(year, quarter, financial_metrics))
