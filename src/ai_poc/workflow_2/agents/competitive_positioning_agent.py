"""
Competitive Positioning Agent - COMMERCIAL LINES ONLY

Analyzes competitive positioning in COMMERCIAL INSURANCE markets.
Excludes Personal Lines analysis.
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


class CompetitivePositioningAgent:
    """
    Agent responsible for analyzing competitive positioning in COMMERCIAL LINES.
    
    **COMMERCIAL FOCUS**: Analyzes market share, pricing power, and positioning
    in commercial insurance only. Excludes personal lines.
    """
    
    def __init__(self):
        """Initialize the competitive positioning agent with Vertex AI Search grounding."""
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
            name="competitive_positioning_agent",
            model=DEFAULT_MODEL,
            instruction="""Analyze competitive positioning in COMMERCIAL INSURANCE markets only.

Focus exclusively on Commercial Lines / Business Insurance / Commercial P&C.
EXCLUDE Personal Lines, Life Insurance, Group Benefits.
Analyze market share, pricing power, competitive advantages in Commercial segment.

**CITATION REQUIREMENTS:**
- Use detailed citations for every claim: [Source: <Company> <Filing Type> Q<Quarter> <Year>, <Section>, Page <X>]
- **SEC Filing Format Examples**:
  - [Source: TRV 10-Q Q3 2024, Item 2 - MD&A - Commercial Insurance Markets, Page 32]
  - [Source: CB 10-K 2024, Item 1 - Business Strategy, Page 8]
- **Key 10-K/10-Q Sections for Competitive Analysis**:
  - Item 1 - Business (market position, competitive advantages)
  - Item 1A - Risk Factors (competitive risks)
  - Item 7 - MD&A (competitive environment discussion for annual filings)
  - Item 2 - MD&A (for quarterly filings)
  - Item 8, Note 3 - Segment Information (segment market share)
- **Earnings Call Format**: [Source: <Company> Q<Quarter> <Year> Earnings Call, <Topic>]
  - Example: [Source: AIG Q2 2024 Earnings Call, Market share discussion]

Search datastore for SEC filings and earnings call transcripts.""",
            description="Analyzes COMMERCIAL LINES competitive positioning from SEC filings and earnings calls",
            tools=[VertexAiSearchTool(data_store_id=datastore_path)]
        )
        
        # Create session service and runner
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service
        )
        
        print(f"[OK] CompetitivePositioningAgent initialized (COMMERCIAL SEGMENT ONLY)")
        print(f"  Model: {DEFAULT_MODEL}")
    
    async def _analyze_positioning_async(
        self,
        year: int,
        quarter: int,
        financial_metrics: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze competitive positioning in COMMERCIAL INSURANCE markets.
        
        Args:
            year: Target year
            quarter: Target quarter
            financial_metrics: Optional pre-computed commercial metrics
        
        Returns:
            Dictionary with commercial market positioning analysis
        """
        print(f"\n🏆 Analyzing COMMERCIAL LINES competitive positioning Q{quarter} {year}...")
        
        # Simplified competitive analysis prompt
        prompt = f"""Analyze competitive positioning for COMMERCIAL INSURANCE segment in Q{quarter} {year}.

**SEARCH FOR EACH COMPANY:**
1. HIG {year} Q{quarter} commercial insurance business insurance market position growth
2. TRV {year} Q{quarter} commercial insurance business insurance
3. CB {year} Q{quarter} commercial north america market share
4. AIG {year} Q{quarter} commercial north america growth
5. CNA {year} Q{quarter} commercial segment market
6. WRB {year} Q{quarter} insurance segment market
7. BRK.B {year} Q{quarter} BH Primary commercial

**FIND IN EARNINGS CALLS & 10-Q:**
- Premium growth rates (commercial segment)
- Market commentary (market share, competitive position)
- Rate change trends (pricing power)
- Strategic priorities (growth areas)

**ANALYZE:**
1. Who's growing fastest in commercial?
2. Who has best combined ratios in commercial?
3. What's Hartford's position vs peers?
4. Key commercial market trends?

**RETURN JSON:**
{{
  "company_rankings": {{
    "by_growth": {{"ranking": ["Company1", "Company2", ...], "citation": "[Source: ...]"}},
    "by_profitability": {{"ranking": ["Company1", ...], "citation": "[Source: ...]"}}
  }},
  "hartford_position": {{
    "rank": "...",
    "strengths": [{{"strength": "...", "citation": "[Source: ...]"}}],
    "gaps": [{{"gap": "...", "citation": "[Source: ...]"}}]
  }},
  "trends": [
    {{"trend": "...", "citation": "[Source: ...]"}}
  ]
}}

Return ONLY valid JSON with citations."""
        
        try:
            # Create session with timestamp for uniqueness
            import time
            session_id = f"competitive_{year}_Q{quarter}_{int(time.time()*1000)}"
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
                    "status": "error",
                    "error": "Agent timeout after 300 seconds"
                }
            
            if not result_text:
                print(f"  ✗ Empty response from agent")
                return {
                    "status": "error",
                    "error": "Empty response from agent"
                }
            
            # Parse JSON
            json_text = result_text
            if "```json" in result_text:
                json_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_text = result_text.split("```")[1].split("```")[0].strip()
            
            try:
                analysis = json.loads(json_text)
            except json.JSONDecodeError as je:
                print(f"  ✗ JSON parse error: {je}")
                print(f"  Response preview (first 500 chars): {result_text[:500]}")
                return {
                    "status": "error",
                    "error": f"JSON parse error: {str(je)}",
                    "raw_response_preview": result_text[:1000]
                }
            
            print(f"  ✓ Commercial positioning analysis complete")
            
            return analysis
        
        except Exception as e:
            print(f"  ✗ Error in positioning analysis: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }
    
    def analyze_positioning(
        self,
        year: int,
        quarter: int,
        financial_metrics: Optional[Dict] = None
    ) -> Dict:
        """Synchronous wrapper for analyze_positioning."""
        return asyncio.run(self._analyze_positioning_async(year, quarter, financial_metrics))
    
    def _format_market_data(self, market_data: List[Dict]) -> str:
        """Format market data for LLM context."""
        formatted = []
        
        for company_data in market_data:
            ticker = company_data["ticker"]
            docs = company_data["documents"]
            
            formatted.append(f"\n--- {ticker} Commercial Market Data ---")
            
            for i, doc in enumerate(docs[:5], 1):
                doc_info = doc.get("document", {})
                snippets = doc_info.get("snippets", [])
                
                if snippets:
                    for snippet in snippets[:2]:
                        formatted.append(snippet.get("snippet", ""))
        
        return "\n".join(formatted)
