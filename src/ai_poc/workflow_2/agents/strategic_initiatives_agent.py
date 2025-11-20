"""
Strategic Initiatives Agent - COMMERCIAL INSURANCE FOCUS

Identifies strategic initiatives affecting COMMERCIAL INSURANCE business.
Filters out Personal Lines initiatives.
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


class StrategicInitiativesAgent:
    """
    Agent responsible for identifying COMMERCIAL INSURANCE strategic initiatives.
    
    **COMMERCIAL FOCUS**: Tracks M&A, product innovation, technology, and
    organizational changes affecting commercial lines only.
    """
    
    def __init__(self):
        """Initialize the strategic initiatives agent with Vertex AI Search grounding."""
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
            name="strategic_initiatives_agent",
            model=DEFAULT_MODEL,
            instruction="""Identify strategic initiatives affecting COMMERCIAL INSURANCE business.

Focus on Commercial Lines / Business Insurance / Commercial P&C only.
EXCLUDE Personal Lines initiatives.
Track M&A, product innovation, technology, organizational changes for Commercial segment.

**CRITICAL OUTPUT REQUIREMENT:**
You MUST return ONLY valid JSON in your response. No additional text, no explanations before or after the JSON.
Start your response with { and end with }. Do not wrap in markdown code blocks.

**CITATION REQUIREMENTS:**
- Use detailed citations for all strategic initiatives: [Source: <Company> <Filing Type> Q<Quarter> <Year>, <Section>, Page <X>]
- **SEC Filing Format Examples**:
  - [Source: HIG 10-Q Q3 2024, Item 2 - MD&A - Strategic Initiatives, Page 28]
  - [Source: CNA 10-K 2024, Item 1 - Business - Digital Transformation, Page 12]
- **Key 10-K/10-Q Sections for Strategic Initiatives**:
  - Item 1 - Business (strategy overview, digital initiatives)
  - Item 7 - MD&A (recent developments, strategic priorities for annual filings)
  - Item 2 - MD&A (for quarterly filings)
  - Item 8, Note 2 - Acquisitions and Dispositions
  - CEO/Management letters (if included in filing)
- **Earnings Call Format**: [Source: <Company> Q<Quarter> <Year> Earnings Call, <Initiative Topic>]
  - Example: [Source: TRV Q1 2024 Earnings Call, Digital platform expansion discussion]

Search datastore for SEC filings and earnings call transcripts.""",
            description="Analyzes COMMERCIAL LINES strategic initiatives from SEC filings and earnings calls",
            tools=[VertexAiSearchTool(data_store_id=datastore_path)]
        )
        
        # Create session service and runner
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service
        )
        
        print(f"[OK] StrategicInitiativesAgent initialized (COMMERCIAL SEGMENT ONLY)")
        print(f"  Model: {DEFAULT_MODEL}")
    
    async def _analyze_initiatives_async(self, year: int, quarter: int) -> Dict:
        """
        Identify strategic initiatives affecting COMMERCIAL INSURANCE.
        
        Args:
            year: Target year
            quarter: Target quarter
        
        Returns:
            Dictionary with commercial insurance strategic initiatives
        """
        print(f"\n🎯 Identifying COMMERCIAL INSURANCE strategic initiatives Q{quarter} {year}...")
        
        # Simplified strategic initiatives prompt
        prompt = f"""Identify strategic initiatives for COMMERCIAL INSURANCE segment in Q{quarter} {year}.

**SEARCH EARNINGS CALLS FOR:**
1. HIG {year} Q{quarter} earnings call commercial strategy initiatives
2. TRV {year} Q{quarter} earnings call business insurance strategy
3. CB {year} Q{quarter} earnings call commercial north america strategy
4. AIG {year} Q{quarter} earnings call commercial strategy
5. CNA {year} Q{quarter} earnings call commercial strategy
6. WRB {year} Q{quarter} earnings call insurance segment strategy

**FIND IN EARNINGS CALLS:**
- Strategic priorities (M&A, partnerships, new products)
- Technology investments (AI, digital platforms)
- Growth initiatives (new markets, specialty lines)
- Management commentary on competitive positioning

**ANALYZE FOR EACH COMPANY:**
1. Top 3-5 strategic topics from earnings call
2. Key metrics or targets mentioned
3. Competitive moves (new products, markets)

**RETURN JSON:**
{{
  "company_highlights": {{
    "HIG": {{
      "topics": [
        {{"topic": "...", "summary": "...", "citation": "[Source: HIG Q{quarter} {year} Earnings Call]"}}
      ]
    }},
    ... (repeat for all 6 companies with earnings calls)
  }},
  "industry_themes": [
    {{"theme": "...", "companies": ["HIG", "TRV"], "citation": "[Source: ...]"}}
  ]
}}

Return ONLY valid JSON with citations."""
        
        try:
            # Create session with timestamp for uniqueness
            import time
            session_id = f"strategic_{year}_Q{quarter}_{int(time.time()*1000)}"
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
            
            # Parse JSON - handle multiple formats
            json_text = result_text
            if "```json" in result_text:
                json_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_text = result_text.split("```")[1].split("```")[0].strip()
            
            # Try to parse JSON
            try:
                initiatives = json.loads(json_text)
            except json.JSONDecodeError as je:
                print(f"  ✗ JSON parse error: {je}")
                print(f"  Response preview (first 500 chars): {result_text[:500]}")
                # Return a minimal valid structure instead of failing
                return {
                    "status": "error",
                    "error": f"JSON parse error: {str(je)}",
                    "raw_response_preview": result_text[:1000]
                }
            
            print(f"  ✓ Commercial initiatives analysis complete")
            
            return initiatives
        
        except Exception as e:
            print(f"  ✗ Error in initiatives analysis: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }
    
    def analyze_initiatives(self, year: int, quarter: int) -> Dict:
        """Synchronous wrapper for analyze_initiatives."""
        return asyncio.run(self._analyze_initiatives_async(year, quarter))
