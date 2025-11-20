"""
Configuration for ADK Multi-Agent System (Workflow 2 - Test Environment)

This workflow uses:
- Datastore: insurance-filings-test (Vertex AI automated processing only)
- Reports: generated_reports_test folder
- Document Processing: Vertex AI automatic chunking and metadata extraction (no manual preprocessing)
"""

# GCP Configuration
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
GCP_LOCATION = "global"

# Vertex AI Search Configuration
DATA_STORE_ID = "insurance-filings-test"
DATA_STORE_LOCATION = "global"
SEARCH_ENGINE_ID = "insurance-poc_1763083298659"

# Model Configuration
DEFAULT_MODEL = "gemini-3-pro-preview"  # 1M token context for comprehensive analysis
FAST_MODEL = "gemini-2.5-flash"   # Faster for simple queries
TEMPERATURE = 0.1  # Low temperature for factual accuracy

# Request Configuration
REQUEST_TIMEOUT = 600  # 10 minutes timeout for full report generation (includes all specialized agents)
MAX_RETRIES = 3  # Retry failed requests up to 3 times
RETRY_DELAY = 2  # Wait 2 seconds between retries

# Parallel Processing Configuration
MAX_CONCURRENT_EXTRACTIONS = 3  # Process max 3 companies at a time to avoid API rate limits

# Generation Configuration
GENERATION_CONFIG = {
    "temperature": TEMPERATURE,
    "max_output_tokens": 8192,  # Limit output to prevent timeouts
    "timeout": REQUEST_TIMEOUT
}

# Company List
COMPANIES = [
    {"ticker": "TRV", "name": "Travelers Companies, Inc.", "has_earnings_calls": True},
    {"ticker": "CB", "name": "Chubb Ltd.", "has_earnings_calls": True},
    {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "has_earnings_calls": False},  # No earnings calls by design
    {"ticker": "AIG", "name": "American International Group", "has_earnings_calls": True},
    {"ticker": "HIG", "name": "The Hartford Financial Services Group", "has_earnings_calls": True},
    {"ticker": "CNA", "name": "CNA Financial Corp.", "has_earnings_calls": True},
    {"ticker": "WRB", "name": "W. R. Berkley Corporation", "has_earnings_calls": True},
]

# Report Configuration
REPORT_OUTPUT_DIR = "generated_reports_test"
REPORT_FORMAT = "markdown"  # Options: markdown, html, json

# Agent System Configuration
ROOT_AGENT_NAME = "CompetitiveIntelligenceOrchestrator"
ROOT_AGENT_DESCRIPTION = "Orchestrates competitive intelligence analysis for The Hartford across 7 major commercial insurers"

# Session Configuration
APP_NAME = "competitive_intelligence_system"
