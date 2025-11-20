"""
Financial Metrics Agent - COMMERCIAL SEGMENT ONLY

Extracts key financial metrics for the COMMERCIAL INSURANCE segment.
Excludes Personal Lines, Life, and other non-commercial segments.
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
    COMPANIES,
    APP_NAME, 
    GCP_PROJECT_ID, 
    GCP_LOCATION, 
    DATA_STORE_LOCATION,
    DATA_STORE_ID
)


class FinancialMetricsAgent:
    """
    Agent responsible for extracting COMMERCIAL SEGMENT financial metrics.
    
    **COMMERCIAL SEGMENT FOCUS**: Extracts only commercial insurance metrics,
    filtering out personal lines, life insurance, and other segments.
    """
    
    # Commercial segment metrics to extract
    COMMERCIAL_METRICS = [
        "Commercial Combined Ratio",
        "Commercial Loss Ratio",
        "Commercial Expense Ratio",
        "Commercial Net Written Premiums",
        "Commercial Underwriting Income",
        "Commercial Premium Growth Rate",
        "Commercial Reserve Development",
        "Commercial Catastrophe Losses",
        "Commercial Prior Year Development",
        "Commercial Workers' Comp Ratio",
        "Commercial General Liability Ratio"
    ]
    
    # Query rewriting configuration
    MAX_QUERY_ITERATIONS = 3
    MIN_QUALITY_SCORE = 0.7  # Threshold for acceptable results
    
    def __init__(self):
        """
        Initialize the financial metrics agent with Vertex AI Search grounding.
        """
        # Configure environment for Vertex AI
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        os.environ["GOOGLE_CLOUD_PROJECT"] = GCP_PROJECT_ID
        os.environ["GOOGLE_CLOUD_LOCATION"] = GCP_LOCATION
        
        # Initialize Vertex AI with GCP credentials
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        
        # Construct full datastore path for Vertex AI Search
        datastore_path = (
            f"projects/{GCP_PROJECT_ID}/locations/{DATA_STORE_LOCATION}/"
            f"collections/default_collection/dataStores/{DATA_STORE_ID}"
        )
        
        # Create ADK Agent with Vertex AI Search grounding
        # Note: Hybrid search with embeddings is automatically enabled when embeddings
        # exist in the datastore (text-embedding-004 already generated during ingestion)
        self.agent = Agent(
            name="financial_metrics_agent",
            model=DEFAULT_MODEL,
            instruction=self._get_system_instruction(),
            description="Extracts COMMERCIAL SEGMENT ONLY financial metrics from SEC filings and earnings calls",
            tools=[VertexAiSearchTool(data_store_id=datastore_path)]
        )
        
        # Create session service and runner
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service
        )
        
        print(f"[OK] FinancialMetricsAgent initialized (COMMERCIAL SEGMENT ONLY)")
        print(f"  Model: {DEFAULT_MODEL}")
        print(f"  Metrics tracked: {len(self.COMMERCIAL_METRICS)}")
    
    def _get_system_instruction(self) -> str:
        """Returns the system instruction for the ADK agent."""
        return f"""You are a financial metrics extraction specialist focused EXCLUSIVELY on COMMERCIAL INSURANCE segments.

**CRITICAL OUTPUT REQUIREMENT:**
You MUST return ONLY valid JSON in your response. No additional text, no explanations before or after the JSON.
Start your response with {{ and end with }}. Do not wrap in markdown code blocks unless absolutely necessary.

**CRITICAL COMMERCIAL SEGMENT FOCUS:**
- Extract ONLY Commercial Lines / Commercial Insurance / Commercial P&C metrics
- EXCLUDE Personal Lines, Life Insurance, Group Benefits, and other segments
- If a company reports combined results, extract Commercial segment data from segmented disclosures

**COMPANY-SPECIFIC SEGMENT NAMES:**
- **TRV (Travelers)**: Look for "Business Insurance" segment in 10-Q Notes (Note 2 - SEGMENT INFORMATION)
  * Business Insurance segment table in Notes shows: Premiums, Net investment income, Fee income, Segment revenues, Claims, Expenses, Segment income
  * Item 2 MD&A "Results of Business Insurance" has combined ratio, loss ratio, expense ratio
  * Combined ratio is reported in MD&A segment results table
  * Net Earned Premiums are under "Revenues" section of Business Insurance segment
  * Search for table with current quarter vs prior year quarter showing all ratios and revenues
- **HIG (Hartford)**: Look for "Business Insurance" segment in 10-Q Item 2 MD&A (also called "Commercial Lines")
  * Hartford's commercial segment is named "Business Insurance" in their 10-Q segment tables
  * Catastrophe losses listed as "Current accident year catastrophe losses and LAE" under Significant Segment Expenses
  * Prior year development listed as "Prior accident year development of losses and LAE" under Significant Segment Expenses
  * Look for "Business Insurance" segment table with earned premiums, revenues, expenses, combined ratio
  * Notes to Consolidated Financial Statements contain detailed Business Insurance segment breakdowns
- **AIG**: Look for "North America Commercial" segment in Note 3 - Segment Information
  * AIG reports segments in rows: North America Commercial, International Commercial, Global Personal, Total General Insurance
  * Extract ONLY "North America Commercial" row data (NOT International Commercial, NOT Total General Insurance)
  * North America Commercial table shows: Net Premiums Written, Net Premiums Earned, Losses and LAE, DAC amortization, Other acquisition expenses, General operating expenses, Underwriting income
  * Search for Note 3 SEGMENT INFORMATION in 10-Q Notes section
  * Do NOT use "International Commercial" segment or consolidated "Total General Insurance" numbers
- **CB (Chubb)**: Look for "North America Commercial P&C" or "North America Commercial" segment
- **CNA**: Look for "Specialty" and "Commercial" segments combined
  * CNA has a "Commercial" column in their segment results table
  * Net earned premiums, claims/benefits/expenses, and core income are in the Commercial column
  * Use "Core income (loss)" from the Commercial segment as underwriting income
  * Look in 10-Q for segment results table showing Specialty, Commercial, International, Life & Group columns
- **WRB (W.R. Berkley)**: Look for "Insurance" segment (primarily commercial)
  * WRB reports commercial business under the "Insurance" segment
  * Use "Insurance" segment metrics as commercial metrics since they are predominantly commercial
  * Extract earned premiums, investment income, losses and loss expenses from the Insurance segment
  * Pre-tax income from the Insurance segment = underwriting income
  * Look in 10-Q Business Segments Note for the segment table with Insurance and Reinsurance & Monoline Excess columns
- **BRK.B (Berkshire)**: Look for "Berkshire Hathaway Primary Group" (BH Primary) segment
  * BH Primary represents Berkshire's primary insurance operations including commercial lines
  * EXCLUDE GEICO (personal auto) and BHRG (reinsurance)
  * Look in Note 24 "Business segment data" for underwriting activities
  * Extract revenues, losses, expenses, and underwriting earnings from BH Primary segment
  * The segment table shows GEICO, BH Primary, and BHRG columns - use BH Primary for commercial metrics

**DATA SOURCE PRIORITY FOR FINANCIAL PERFORMANCE TABLE METRICS:**
For metrics used in the **Commercial Segment Financial Performance comparison table**, prioritize auditable sources:
1. **PRIMARY SOURCE - 10-Q/10-K SEC Filings**: Always search SEC filings FIRST for table metrics
   - Segment Results tables
   - Business Segment Information tables  
   - Management Discussion & Analysis (MD&A) sections
   - Financial Statement Notes (especially segment notes)
2. **FALLBACK SOURCE - Earnings Calls**: ONLY use earnings call data if metric is NOT available in SEC filings
   - Use earnings calls to supplement or provide context
   - Never prefer earnings call data over official SEC filing data for table metrics

**Table Metrics (SEC filing priority):**
- Net Written Premiums Growth, Combined Ratio, Loss Ratio, Expense Ratio
- Underwriting Income, Catastrophe Losses, Prior Year Development

**Other Metrics (equal weight for SEC filings and earnings calls):**
- All other commercial metrics can use either source with equal priority

**IMPORTANT**: For financial performance table metrics, search 10-Q/10-K documents thoroughly before falling back to earnings call transcripts. For other analysis sections, both sources have equal weight.

**METRICS TO EXTRACT (Commercial Segment Only):**
{json.dumps(self.COMMERCIAL_METRICS, indent=2)}

**SPECIAL INSTRUCTIONS FOR AIG:**
- AIG reports "North America Commercial" and "International Commercial" separately
- Extract combined ratio for BOTH segments
- Label them as "Commercial Combined Ratio (North America)" and "Commercial Combined Ratio (International)"

**CITATION REQUIREMENTS:**
- Use inline citations for EVERY metric extracted with detailed section information
- **PREFER SEC Filing Citations**: Always cite 10-Q/10-K when available
- **SEC Filing Citation Format (PREFERRED)**: [Source: <Company> <Filing Type> Q<Quarter> <Year>, <Section Name>, Page <X>]
  - Example: [Source: TRV 10-Q Q3 2024, Segment Results - Business Insurance, Page 45]
  - Example: [Source: AIG 10-K 2024, Item 8 - Financial Statements, Note 3 - Segment Information, Page 112]
- **Earnings Call Citation Format (FALLBACK ONLY)**: [Source: <Company> Q<Quarter> <Year> Earnings Call, <Speaker> commentary]
  - Example: [Source: CB Q2 2024 Earnings Call, CFO commentary on North America Commercial]
  - Note: "(earnings call - not in 10-Q)" if using earnings call data
- **Required Section Details for 10-K/10-Q**:
  - Part I, Item 1 - Business description and segment tables
  - Part I, Item 2 - Management's Discussion and Analysis (MD&A) for quarterly filings
  - Part II, Item 7 - MD&A for annual filings
  - Part II, Item 8 - Financial Statements and Supplementary Data
  - Note disclosures (e.g., Note 3 - Segment Information, Note 7 - Reserves)
  - Specific table names (e.g., "Consolidated Results of Operations", "Segment Results")
- If a metric is not found for Commercial segment specifically, mark as "Not disclosed (Commercial segment)"

**OUTPUT FORMAT:**
Return ONLY valid JSON with this exact structure (no markdown code blocks):
{{
  "ticker": "TICKER",
  "year": YEAR,
  "quarter": QUARTER,
  "commercial_metrics": {{
    "Commercial Combined Ratio": {{"value": X.X, "citation": "[Source: ...]"}},
    "Commercial Loss Ratio": {{"value": X.X, "citation": "[Source: ...]"}},
    ...
  }},
  "notes": "Any relevant commercial segment notes",
  "data_quality": "high|medium|low"
}}"""
    
    def _build_initial_queries(self, ticker: str, year: int, quarter: int) -> list[str]:
        """
        Build initial search queries optimized for finding segment data in 10-Q filings.
        
        Returns:
            List of targeted search queries ranked by expected effectiveness
        """
        # Company-specific queries targeting exact segment tables
        segment_queries = {
            "TRV": [
                f"{ticker} Form 10-Q Q{quarter} {year} Note 2 SEGMENT INFORMATION Business Insurance segment revenues expenses",
                f"Travelers {year} third quarter Business Insurance combined ratio loss ratio segment results",
                f"{ticker} 10-Q {year} Business Insurance premiums underwriting income segment table"
            ],
            "HIG": [
                f"{ticker} Form 10-Q Q{quarter} {year} Business Insurance segment earned premiums combined ratio",
                f"Hartford {year} Q{quarter} Business Insurance catastrophe losses prior year development",
                f"{ticker} 10-Q {year} Commercial Lines segment financial results table"
            ],
            "AIG": [
                f"{ticker} Form 10-Q Q{quarter} {year} Note 3 SEGMENT INFORMATION North America Commercial",
                f"AIG {year} third quarter North America Commercial underwriting income premiums written",
                f"{ticker} 10-Q {year} North America Commercial segment NOT International"
            ],
            "CB": [
                f"{ticker} Form 10-Q Q{quarter} {year} North America Commercial P&C segment",
                f"Chubb {year} third quarter North America Commercial insurance results",
                f"{ticker} 10-Q {year} commercial segment financial table"
            ],
            "CNA": [
                f"{ticker} 10-Q Q{quarter} {year} Three months ended September segment table Commercial column",
                f"CNA {year} quarterly segment results Specialty Commercial International Life Group",
                f"{ticker} Form 10-Q {year} operating revenues Commercial segment core income"
            ],
            "WRB": [
                f"{ticker} Form 10-Q Q{quarter} {year} Insurance segment Note business segments",
                f"W.R. Berkley {year} third quarter Insurance segment premiums pre-tax income",
                f"{ticker} 10-Q {year} Insurance segment NOT Reinsurance"
            ],
            "BRK.B": [
                f"{ticker} 10-Q Q{quarter} {year} Note 24 Business segment data Third Quarter BH Primary",
                f"Berkshire Hathaway {year} underwriting activities GEICO BH Primary BHRG table",
                f"{ticker} Form 10-Q {year} earnings before income taxes BH Primary column"
            ]
        }
        
        # Return company-specific queries or generic fallback
        return segment_queries.get(ticker, [
            f"{ticker} Form 10-Q Q{quarter} {year} commercial segment financial results",
            f"{ticker} {year} third quarter commercial insurance segment",
            f"{ticker} 10-Q {year} commercial lines segment table"
        ])
    
    def _score_search_results(self, result_text: str, ticker: str, year: int, quarter: int) -> dict:
        """
        Score the quality of search results using multiple criteria.
        
        Returns:
            Dict with score (0-1) and feedback for query refinement
        """
        score = 0.0
        feedback = []
        issues = []
        
        # Check 1: Contains correct year (critical)
        if str(year) in result_text:
            score += 0.3
        else:
            issues.append(f"Missing year {year}")
            feedback.append(f"Search for documents explicitly dated {year}")
        
        # Check 2: Contains 10-Q reference (preferred source)
        if "10-Q" in result_text or "10-K" in result_text:
            score += 0.2
        else:
            issues.append("No 10-Q/10-K reference found")
            feedback.append("Add 'Form 10-Q' to query to prioritize SEC filings")
        
        # Check 3: Contains segment-specific keywords
        segment_keywords = {
            "TRV": ["Business Insurance", "segment"],
            "HIG": ["Business Insurance", "Commercial Lines"],
            "AIG": ["North America Commercial", "NOT International"],
            "CB": ["North America Commercial"],
            "CNA": ["Commercial", "segment"],
            "WRB": ["Insurance segment"],
            "BRK.B": ["BH Primary"]
        }
        
        expected_keywords = segment_keywords.get(ticker, ["commercial", "segment"])
        keywords_found = sum(1 for kw in expected_keywords if kw.lower() in result_text.lower())
        if keywords_found > 0:
            score += 0.2 * (keywords_found / len(expected_keywords))
        else:
            issues.append(f"Missing segment keywords for {ticker}")
            feedback.append(f"Include segment name: {', '.join(expected_keywords)}")
        
        # Check 4: Contains financial metrics keywords
        metric_keywords = ["premiums", "combined ratio", "loss ratio", "underwriting", "revenue"]
        metrics_found = sum(1 for kw in metric_keywords if kw.lower() in result_text.lower())
        if metrics_found >= 2:
            score += 0.2
        else:
            issues.append("Few financial metrics mentioned")
            feedback.append("Add specific metric names like 'combined ratio' or 'net premiums written'")
        
        # Check 5: Avoids wrong segments or years
        wrong_indicators = {
            "AIG": ["International Commercial", "Global Personal"],
            "BRK.B": ["GEICO", "BHRG"],
            "WRB": ["Reinsurance & Monoline"],
        }
        
        wrong_terms = wrong_indicators.get(ticker, [])
        wrong_year_pattern = [str(y) for y in range(year-2, year) if str(y) in result_text]
        
        if any(term in result_text for term in wrong_terms):
            score -= 0.1
            issues.append(f"Contains excluded segment terms: {wrong_terms}")
            feedback.append(f"Explicitly exclude: {', '.join(wrong_terms)}")
        
        if wrong_year_pattern:
            score -= 0.1
            issues.append(f"Contains prior year data: {wrong_year_pattern}")
            feedback.append(f"Add 'Q{quarter} {year}' to filter by correct period")
        
        # Normalize score to 0-1 range
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "feedback": feedback,
            "issues": issues,
            "quality": "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"
        }
    
    def _refine_query(self, original_query: str, feedback: list[str], iteration: int) -> str:
        """
        Refine query based on scoring feedback.
        
        Args:
            original_query: The query that produced suboptimal results
            feedback: List of improvement suggestions
            iteration: Current iteration number
        
        Returns:
            Refined query string
        """
        # Start with original query
        refined = original_query
        
        # Apply feedback suggestions
        for suggestion in feedback:
            if "Form 10-Q" in suggestion and "10-Q" not in refined:
                # Add Form 10-Q if missing
                refined = f"Form 10-Q {refined}"
            elif "segment name" in suggestion.lower():
                # Segment name already in query, increase specificity
                if "Note" not in refined:
                    refined = f"{refined} Note segment table"
            elif "explicitly dated" in suggestion.lower():
                # Year emphasis - already in query, add quarter emphasis
                if "third quarter" not in refined and "Q3" not in refined:
                    parts = refined.split()
                    # Insert quarter reference
                    refined = f"{parts[0]} third quarter {' '.join(parts[1:])}"
        
        # Progressive refinement by iteration
        if iteration == 2:
            # Second attempt: Add "NOT" exclusions for companies that need it
            if "AIG" in refined and "NOT" not in refined:
                refined = f"{refined} NOT International Commercial"
            elif "Berkshire" in refined or "BRK" in refined:
                refined = f"{refined} NOT GEICO NOT BHRG"
        
        elif iteration == 3:
            # Third attempt: Maximum specificity
            refined = f"{refined} segment financial statement Note table"
        
        return refined
    
    async def _iterative_search(self, ticker: str, year: int, quarter: int) -> tuple[str, float]:
        """
        Perform iterative search with reflection and query refinement.
        
        Args:
            ticker: Company ticker
            year: Target year
            quarter: Target quarter
        
        Returns:
            Tuple of (best_results_text, quality_score)
        """
        # Build initial queries
        queries = self._build_initial_queries(ticker, year, quarter)
        
        best_score = 0.0
        best_results = ""
        best_query = queries[0]
        previous_feedback = []  # Initialize feedback list
        
        for iteration in range(1, self.MAX_QUERY_ITERATIONS + 1):
            # Select query for this iteration
            if iteration == 1:
                current_query = queries[0]  # Most specific query first
            else:
                # Refine based on previous feedback
                current_query = self._refine_query(
                    best_query, 
                    previous_feedback if iteration > 1 else [],
                    iteration
                )
            
            print(f"  🔍 Iteration {iteration}/{self.MAX_QUERY_ITERATIONS}: {current_query[:80]}...")
            
            # Execute search through agent (ADK will use Vertex AI Search)
            try:
                # Create session for this search
                import time
                search_session_id = f"search_{ticker}_{year}_Q{quarter}_iter{iteration}_{int(time.time()*1000)}"
                search_session = await self.session_service.create_session(
                    app_name=APP_NAME,
                    user_id="system",
                    session_id=search_session_id
                )
                
                # Use runner to search with current query
                search_prompt = f"""Search for: {current_query}
                
Return the first 2000 characters of the most relevant search results.
Focus on finding segment financial tables and metrics from 10-Q filings."""
                
                content = types.Content(
                    role='user',
                    parts=[types.Part(text=search_prompt)]
                )
                
                result_text = ""
                async for event in self.runner.run_async(
                    user_id="system",
                    session_id=search_session_id,
                    new_message=content
                ):
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                            if text_parts:
                                result_text = ''.join(text_parts)
                                break
                
                # Score the results
                scoring = self._score_search_results(result_text, ticker, year, quarter)
                current_score = scoring["score"]
                
                print(f"    📊 Quality: {scoring['quality']} (score: {current_score:.2f})")
                
                # Track best results
                if current_score > best_score:
                    best_score = current_score
                    best_results = result_text
                    best_query = current_query
                    previous_feedback = scoring["feedback"]
                
                # Stop if quality threshold met
                if current_score >= self.MIN_QUALITY_SCORE:
                    print(f"    ✅ Quality threshold met ({current_score:.2f} >= {self.MIN_QUALITY_SCORE})")
                    break
                
                # Log issues for refinement
                if scoring["issues"]:
                    print(f"    ⚠️  Issues: {', '.join(scoring['issues'][:2])}")
                
            except Exception as e:
                print(f"    ❌ Search iteration {iteration} failed: {e}")
                continue
        
        print(f"  🎯 Final quality score: {best_score:.2f} after {iteration} iteration(s)")
        return best_results, best_score

    async def _extract_company_metrics_async(self, ticker: str, year: int, quarter: int) -> Dict:
        """
        Extract COMMERCIAL SEGMENT financial metrics for a single company (async).
        
        Args:
            ticker: Company ticker symbol
            year: Target year
            quarter: Target quarter
        
        Returns:
            Dictionary with commercial segment metrics
        """
        print(f"\n💰 Extracting COMMERCIAL metrics for {ticker} Q{quarter} {year}...")
        
        # Company-specific search guidance
        segment_guidance = {
            "TRV": "Search TRV 10-Q for 'Business Insurance' segment in Note 2 SEGMENT INFORMATION. Look for table showing 'Business Insurance' column with: Premiums, Net investment income, Fee income, Other revenues, Total segment revenues, Claims and claim adjustment expenses, Amortization of deferred acquisition costs, General and administrative expenses, Income tax expense, and Segment income. Also search Item 2 MD&A for 'Results of Business Insurance' with combined ratio, loss ratio, expense ratio. The 10-Q Notes contain the complete Business Insurance segment financials.",
            "HIG": "Search HIG 10-Q for 'Business Insurance' segment (also called 'Commercial Lines') in Item 2 MD&A or Notes to Financial Statements. Look for 'Business Insurance' segment table showing: Earned premiums, Net investment income, Fee income, Total revenues, Benefits/losses/LAE, Insurance operating costs, Total benefits/losses/expenses, Income before income taxes, and Combined ratio. Also find 'Significant Segment Expenses' table showing Current accident year catastrophe losses, Prior year development, and Underlying combined ratio. Hartford reports commercial metrics under 'Business Insurance' segment.",
            "AIG": "Search AIG 10-Q for Note 3 SEGMENT INFORMATION. Look for 'North America Commercial' row in the segment table (NOT 'International Commercial' or 'Total General Insurance'). Extract ONLY North America Commercial data showing: Net Premiums Written, Net Premiums Earned, Losses and Loss Adjustment Expenses, Amortization of DAC, Other Acquisition Expenses, General Operating Expenses, Underwriting Income (Loss), and Net Investment Income. DO NOT use 'International Commercial' or 'Global Personal' data. The table shows multiple rows - select ONLY the 'North America Commercial' row.",
            "CB": "Search for 'North America Commercial' segment or 'Commercial Insurance' in 10-Q segment tables.",
            "CNA": "Search CNA 10-Q for the segment results table titled 'Three months ended September 30' or similar quarterly segment table. This table has COLUMNS for: Specialty, Commercial, International, Life & Group, Corporate & Other, Eliminations, and Total. Extract data from the 'Commercial' COLUMN only. Key rows to find: Net earned premiums, Net investment income, Total operating revenues, Net incurred claims and benefits, Amortization of deferred acquisition costs, Insurance related administrative expenses, Total claims/benefits/expenses, and Core income (loss). Calculate Combined Ratio from: (Net incurred claims / Net earned premiums) + (Admin expenses / Net earned premiums). Use 'Core income (loss)' from Commercial column as underwriting income.",
            "WRB": "Search for 'Insurance' segment in the Business Segments Note (Note 22). W.R. Berkley reports commercial business under the 'Insurance' segment. Use Insurance segment revenues (earned premiums), expenses (losses and loss expenses), and pre-tax income as commercial metrics. The segment table shows Insurance and Reinsurance & Monoline Excess columns - use the Insurance column.",
            "BRK.B": "Search BRK.B 10-Q for Note 24 'Business segment data' showing the underwriting activities table. This table has COLUMNS for: GEICO, BH Primary, BHRG, Total Underwriting, Investment Income, and Total. Extract data from the 'BH Primary' COLUMN only (NOT GEICO or BHRG). Key rows: Revenues, Losses and loss adjustment expenses ('LAE'), Life annuity and health benefits, Other segment items, Total costs and expenses, and Earnings before income taxes. The BH Primary column shows Berkshire Hathaway Primary Group commercial insurance operations. Calculate Combined Ratio = (Losses and LAE + Other segment items) / Revenues × 100. Use 'Earnings before income taxes' from BH Primary column as underwriting income."
        }
        
        search_hint = segment_guidance.get(ticker, f"Search for commercial insurance segment data for {ticker}")
        
        # Map quarter to period end date and filing month for search
        quarter_end_dates = {
            1: "March 31",
            2: "June 30", 
            3: "September 30",
            4: "December 31"
        }
        filing_months = {
            1: ("April", "May"),
            2: ("July", "August"),
            3: ("October", "November"),
            4: ("February", "March")
        }
        period_end = quarter_end_dates.get(quarter, f"Q{quarter}")
        months = filing_months.get(quarter, ("",))
        
        # Simplified search for Vertex AI automated processing
        # No manual chunking - Vertex AI automatically chunks and extracts metadata
        prompt = f"""Extract commercial segment metrics for {ticker} from their Q{quarter} {year} 10-Q filing.

**SEARCH QUERIES (Vertex AI will automatically find relevant sections):**
1. "{ticker} {year} commercial segment financial results"
2. "{ticker} {year} business insurance underwriting"
3. "{ticker} {year} segment information note"

**WHERE TO LOOK:**
{search_hint}

**EXTRACT 7 METRICS:**
1. Net Written Premiums ($M)
2. Net Written Premiums Growth (%)
3. Combined Ratio (%)
4. Loss Ratio (%) - if disclosed
5. Expense Ratio (%) - if disclosed
6. Underwriting Income ($M)
7. Catastrophe Losses ($M) - if disclosed

**SEARCH TIPS:**
- Vertex AI automatically searches across all document sections
- Look for: Segment tables in Notes, MD&A results sections
- Combined ratio typically in "Results of [Segment Name]" section
- Growth rates usually mentioned in MD&A narrative
- Make multiple searches - each metric may be in different sections

**OUTPUT FORMAT:**
{{
  "ticker": "{ticker}",
  "year": {year},
  "quarter": {quarter},
  "commercial_metrics": {{
    "Net Written Premiums": {{"value": 5400, "citation": "[Source: {ticker} 10-Q Q{quarter} {year}, Note X]"}},
    "Net Written Premiums Growth": {{"value": 8.5, "citation": "[Source: ...]"}},
    "Combined Ratio": {{"value": 94.5, "citation": "[Source: ...]"}},
    "Loss Ratio": {{"value": 62.3, "citation": "[Source: ...]"}},
    "Expense Ratio": {{"value": 32.2, "citation": "[Source: ...]"}},
    "Underwriting Income": {{"value": 450, "citation": "[Source: ...]"}},
    "Catastrophe Losses": {{"value": 125, "citation": "[Source: ...]"}}
  }}
}}

**CRITICAL - READ CAREFULLY:**
1. Your ENTIRE response must be ONLY the JSON object above
2. Do NOT include any text before the opening {{
3. Do NOT include any text after the closing }}
4. Do NOT write summaries, explanations, or commentary
5. Do NOT use markdown code blocks
6. After searching, extract the data and IMMEDIATELY return ONLY the JSON
7. The FIRST character of your response must be {{
8. The LAST character of your response must be }}
9. If you cannot find a metric, use: {{"value": null, "citation": "Not Disclosed in 10-Q"}}
10. RETURN NOTHING BUT JSON"""
        
        try:
            # Create session with timestamp for uniqueness
            import time
            session_id = f"metrics_{ticker}_{year}_Q{quarter}_{int(time.time()*1000)}"
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
            event_count = 0
            final_response_count = 0
            function_call_count = 0
            try:
                async with asyncio.timeout(300):  # 5 minute timeout
                    async for event in self.runner.run_async(
                        user_id="system",
                        session_id=session_id,
                        new_message=content
                    ):
                        event_count += 1
                        
                        # Log event details for debugging
                        if hasattr(event, 'content') and event.content:
                            if event.content.parts:
                                for part in event.content.parts:
                                    if hasattr(part, 'function_call'):
                                        function_call_count += 1
                        
                        if event.is_final_response():
                            final_response_count += 1
                            if event.content and event.content.parts:
                                # Extract text from all text parts (may also have function_call parts)
                                text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                                if text_parts:
                                    # Got text response - update result_text
                                    result_text = ''.join(text_parts)
                                else:
                                    # Final response exists but has no text parts (likely function call)
                                    # Continue processing - agent may make function calls before final text response
                                    part_types = [type(part).__name__ for part in event.content.parts]
                                    # Don't print warning - this is normal for function calls
                            else:
                                # No content or parts - unusual but continue processing
                                pass
            except asyncio.TimeoutError:
                print(f"  ✗ Timeout after 300 seconds for {ticker}")
                return {
                    "ticker": ticker,
                    "year": year,
                    "quarter": quarter,
                    "commercial_metrics": {},
                    "status": "error",
                    "error": "Agent timeout after 300 seconds"
                }
            
            # Debug logging for event processing
            print(f"  📊 Events: {event_count} total, {final_response_count} final, {function_call_count} function calls")
            
            if not result_text:
                if final_response_count == 0:
                    print(f"  ✗ Empty response: No final response events received")
                else:
                    print(f"  ✗ Empty response: {final_response_count} final response(s) but no text extracted")
                return {
                    "ticker": ticker,
                    "year": year,
                    "quarter": quarter,
                    "commercial_metrics": {},
                    "status": "error",
                    "error": "Empty response from agent"
                }
            
            # Parse JSON response
            json_text = result_text.strip()  # Remove leading/trailing whitespace
            
            # Remove markdown code blocks if present
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()
            
            # If response doesn't start with {, try to find the JSON object
            if not json_text.startswith('{'):
                # Look for the first { and last }
                start_idx = json_text.find('{')
                end_idx = json_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_text = json_text[start_idx:end_idx+1]
                else:
                    print(f"  ✗ Response does not contain JSON object")
                    print(f"  Response preview (first 500 chars): {result_text[:500]}")
                    return {
                        "ticker": ticker,
                        "year": year,
                        "quarter": quarter,
                        "commercial_metrics": {},
                        "status": "error",
                        "error": "Response does not contain valid JSON",
                        "raw_response_preview": result_text[:1000]
                    }
            
            # Try to parse JSON with better error handling
            try:
                metrics_data = json.loads(json_text)
            except json.JSONDecodeError as je:
                print(f"  ✗ JSON parse error: {je}")
                print(f"  Response preview (first 500 chars): {result_text[:500]}")
                return {
                    "ticker": ticker,
                    "year": year,
                    "quarter": quarter,
                    "commercial_metrics": {},
                    "status": "error",
                    "error": f"JSON parse error: {str(je)}",
                    "raw_response_preview": result_text[:1000]
                }
            
            print(f"  ✓ Extracted {len(metrics_data.get('commercial_metrics', {}))} Commercial metrics")
            
            return metrics_data
        
        except Exception as e:
            print(f"  ✗ Error extracting metrics: {e}")
            import traceback
            traceback.print_exc()
            return {
                "ticker": ticker,
                "year": year,
                "quarter": quarter,
                "commercial_metrics": {},
                "status": "error",
                "error": str(e)
            }
    
    def extract_company_metrics(self, ticker: str, year: int, quarter: int) -> Dict:
        """
        Extract COMMERCIAL SEGMENT financial metrics for a single company (synchronous wrapper).
        
        Args:
            ticker: Company ticker symbol
            year: Target year
            quarter: Target quarter
        
        Returns:
            Dictionary with commercial segment metrics
        """
        return asyncio.run(self._extract_company_metrics_async(ticker, year, quarter))
    
    async def extract_all_companies_async(self, year: int, quarter: int, max_concurrent: int = 2) -> Dict[str, Dict]:
        """
        Extract COMMERCIAL SEGMENT metrics for all companies (async version with batched parallel processing).
        
        Uses asyncio.gather() in batches to analyze companies concurrently while avoiding API rate limits.
        Default batch size of 2 concurrent requests for maximum API stability.
        
        Args:
            year: Target year
            quarter: Target quarter
            max_concurrent: Maximum number of concurrent company extractions (default: 2)
        
        Returns:
            Dictionary mapping ticker to commercial metrics
        """
        print(f"\n" + "="*80)
        print(f"EXTRACTING COMMERCIAL SEGMENT METRICS - Q{quarter} {year} (BATCHED PARALLEL MODE)")
        print("="*80)
        print(f"  🚀 Processing {len(COMPANIES)} companies in batches of {max_concurrent}...")
        
        all_metrics = {}
        
        # Process companies in batches to avoid overwhelming the API
        for i in range(0, len(COMPANIES), max_concurrent):
            batch = COMPANIES[i:i+max_concurrent]
            batch_num = (i // max_concurrent) + 1
            total_batches = (len(COMPANIES) + max_concurrent - 1) // max_concurrent
            
            print(f"\n  📦 Batch {batch_num}/{total_batches}: {[c['ticker'] for c in batch]}")
            
            # Create tasks for current batch
            tasks = [
                self._extract_company_metrics_async(company["ticker"], year, quarter)
                for company in batch
            ]
            
            # Execute batch in parallel with error handling
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as batch_error:
                print(f"    ✗ Batch execution failed: {batch_error}")
                # Mark all companies in this batch as errored
                for company in batch:
                    all_metrics[company["ticker"]] = {
                        "ticker": company["ticker"],
                        "status": "error",
                        "error": f"Batch execution failed: {str(batch_error)}"
                    }
                continue
            
            # Map results back to tickers
            for company, result in zip(batch, results):
                ticker = company["ticker"]
                if isinstance(result, Exception):
                    print(f"    ⚠️  {ticker}: Exception - {type(result).__name__}: {result}")
                    all_metrics[ticker] = {
                        "ticker": ticker,
                        "status": "error",
                        "error": f"Exception during extraction: {str(result)}"
                    }
                elif result.get("status") == "error":
                    # Agent returned error structure
                    all_metrics[ticker] = result
                    error_msg = result.get("error", "Unknown error")
                    print(f"    ✗ {ticker}: {error_msg[:80]}")
                else:
                    # Successful extraction
                    all_metrics[ticker] = result
                    metric_count = len(result.get("commercial_metrics", {}))
                    print(f"    ✓ {ticker}: Extracted {metric_count} metrics")
            
            # Longer pause between batches to respect API rate limits
            if i + max_concurrent < len(COMPANIES):
                print(f"    ⏳ Waiting 3 seconds before next batch...")
                await asyncio.sleep(3)
        
        successful = sum(1 for m in all_metrics.values() if m.get("status") != "error")
        print(f"\n✓ Completed batched extraction: {successful}/{len(all_metrics)} companies successful")
        
        return all_metrics
    
    def extract_all_companies(self, year: int, quarter: int) -> Dict[str, Dict]:
        """
        Extract COMMERCIAL SEGMENT metrics for all companies.
        
        Args:
            year: Target year
            quarter: Target quarter
        
        Returns:
            Dictionary mapping ticker to commercial metrics
        """
        return asyncio.run(self.extract_all_companies_async(year, quarter))

