# Copilot Instructions for Insurance AI POC

## Project Overview

This is a **Google ADK (Agent Development Kit)** project that generates competitive intelligence reports for The Hartford's Commercial Insurance segment. It analyzes SEC filings (10-K/10-Q) and earnings call transcripts from 7 major commercial insurers using Vertex AI Search for RAG/grounding.

## Technology Stack

- **Framework**: Google ADK (`google-adk>=1.18.0`)
- **Model**: `gemini-3-pro-preview` (1M token context)
- **Search/RAG**: Vertex AI Search (Discovery Engine)
- **Tracing**: Arize AX (OpenTelemetry instrumentation)
- **Python**: 3.12+
- **Testing**: pytest with `pytest-asyncio`

## Key Architecture Patterns

### Agent Structure

The system uses a **single root agent with 6 FunctionTools** pattern (NOT a multi-agent delegation pattern):

```
CompetitiveIntelligenceRootAgent
├── FindLatestQuarterTool      → calls _find_latest_complete_quarter() in tools.py
├── ValidateDataTool           → calls _validate_data_for_quarter() in tools.py
├── FinancialMetricsTool       → delegates to FinancialMetricsAgent
├── CompetitivePositioningTool → delegates to CompetitivePositioningAgent
├── StrategicInitiativesTool   → delegates to StrategicInitiativesAgent
└── RiskOutlookTool            → delegates to RiskOutlookAgent
```

### ADK Imports

Always use these correct import paths:

```python
# Agent, Runner, Sessions
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Tools - use FunctionTool from this path
from google.adk.tools.function_tool import FunctionTool

# NOT google.adk.tools (causes ModuleNotFoundError)
```

### Creating FunctionTools

Wrap Python functions as ADK tools:

```python
from google.adk.tools.function_tool import FunctionTool

def my_tool_function(param1: str, param2: int) -> dict[str, Any]:
    """Docstring becomes the tool description for the LLM."""
    return {"result": "..."}

MyTool = FunctionTool(func=my_tool_function)
```

### Agent Configuration

```python
from .config import DEFAULT_MODEL, TEMPERATURE

agent = Agent(
    name="AgentName",
    model=DEFAULT_MODEL,  # "gemini-3-pro-preview"
    description="Agent description",
    instruction="System prompt...",
    tools=[Tool1, Tool2],
    generate_content_config={
        "temperature": TEMPERATURE,  # 1.0 for Gemini 3
        "max_output_tokens": 8192,
    }
)
```

### Temperature Setting

- **Gemini 3**: Use `1.0` (default, optimized for reasoning)
- Lower temperatures cause degraded outputs in Gemini 3
- Configured in `config.py` as `TEMPERATURE = 1.0`

## Project Structure

```
src/ai_poc/workflow_1/
├── agents/
│   ├── config.py                    # All configuration (model, GCP, companies)
│   ├── tools.py                     # FunctionTools + utility functions
│   ├── root_agent.py                # Main orchestrator (CompetitiveIntelligenceRootAgent)
│   ├── financial_metrics_agent.py   # Extracts financial metrics
│   ├── competitive_positioning_agent.py  # Market positioning analysis
│   ├── strategic_initiatives_agent.py    # Strategic moves from earnings calls
│   └── risk_outlook_agent.py        # Risk assessment
├── arize_tracing/
│   └── arize_config.py              # OpenTelemetry tracing setup
└── scripts/
    ├── financial_report_ingestion.py   # SEC filings → Vertex AI Search
    ├── earnings_call_ingestion.py      # Transcripts → Vertex AI Search
    └── regenerate_report.py            # Report generation script
```

## Configuration Location

All configuration is centralized in `config.py`:

```python
# GCP
GCP_PROJECT_ID = "project-4b3d3288-7603-4755-899"
DATA_STORE_ID = "insurance-filings-full"

# Model
DEFAULT_MODEL = "gemini-3-pro-preview"
TEMPERATURE = 1.0

# Companies analyzed
COMPANIES = [...]  # 7 insurers including HIG
```

## Session Management

The project uses `InMemorySessionService` (development/testing):

```python
from google.adk.sessions import InMemorySessionService

session_service = InMemorySessionService()
runner = Runner(agent=agent, app_name="app_name", session_service=session_service)

# Create session
session = await session_service.create_session(
    app_name="app_name",
    user_id="user_1",
    session_id="session_1"
)
```

**Note**: InMemorySessionService is NOT persistent. State is lost on process restart.

## Vertex AI Search Integration

Specialized agents query the datastore using Discovery Engine:

```python
from google.cloud import discoveryengine_v1 as discoveryengine

client = discoveryengine.SearchServiceClient()
serving_config = f"projects/{GCP_PROJECT_ID}/locations/{LOCATION}/collections/default_collection/dataStores/{DATA_STORE_ID}/servingConfigs/default_config"

request = discoveryengine.SearchRequest(
    serving_config=serving_config,
    query="search query",
    page_size=10,
)
response = client.search(request)
```

## Testing Patterns

Tests are in `tests/test_adk_integration.py`:

```python
import pytest
from ai_poc.workflow_1.agents import (
    CompetitiveIntelligenceRootAgent,
    FinancialMetricsAgent,
    CompetitivePositioningAgent,
)
from ai_poc.workflow_1.agents.tools import find_latest_quarter

@pytest.fixture(scope="module")
def financial_agent():
    return FinancialMetricsAgent()

@pytest.mark.asyncio
async def test_financial_analysis(financial_agent, latest_quarter_info):
    result = await financial_agent.extract_all_companies_async(
        year=latest_quarter_info['year'],
        quarter=latest_quarter_info['quarter']
    )
    assert 'HIG' in result
```

### Test Markers

- `@pytest.mark.slow` - Long-running tests (>60s)
- `@pytest.mark.integration` - Requires GCP credentials
- `@pytest.mark.tracing` - Tests Arize AX integration

Run tests: `pytest tests/ -v`
Skip slow: `pytest -m "not slow"`

## Domain Knowledge

### Commercial Insurance Focus

**CRITICAL**: This system analyzes **Commercial Lines/Business Insurance ONLY**:

- Workers Compensation
- General Liability  
- Commercial Property
- Commercial Auto
- Professional Liability

**EXCLUDE** from analysis:
- Personal Lines (auto, homeowners)
- Life Insurance
- Retirement/Asset Management

### Company Segment Names

Different companies use different names for their commercial segment:

| Company | Commercial Segment Name |
|---------|------------------------|
| TRV | "Business Insurance" |
| HIG | "Business Insurance" / "Commercial Lines" |
| AIG | "North America Commercial" (exclude International) |
| CB | "North America Commercial P&C" |
| CNA | "Commercial" |
| WRB | "Insurance" |
| BRK.B | "BH Primary" (exclude GEICO, BHRG) |

### Special Cases

- **BRK.B (Berkshire Hathaway)**: No earnings calls by design. SEC filings only.
- **AIG**: Extract "North America Commercial" only, exclude "International Commercial"

## Code Style Guidelines

1. **Type hints**: Always use type hints for function parameters and returns
2. **Docstrings**: Use Google-style docstrings with Args/Returns sections
3. **Async**: Analysis functions should be async (`async def`, `await`)
4. **Error handling**: Use try/except with informative error messages
5. **Print statements**: Use emoji prefixes for status (✓ ✗ ⚠️ 📊 🎯)

## Common Patterns

### Adding a New Agent

1. Create `new_agent.py` in `agents/`
2. Implement class with `_analyze_*_async()` methods
3. Add wrapper function in `tools.py`
4. Create FunctionTool: `NewTool = FunctionTool(func=new_function)`
5. Add to root agent's tools list
6. Export in `__init__.py`

### Adding a New Tool

```python
# In tools.py
async def new_analysis(year: int, quarter: int) -> dict[str, Any]:
    """Tool description for LLM."""
    # Implementation
    return {"result": "..."}

NewAnalysisTool = FunctionTool(func=new_analysis)

# In root_agent.py, add to tools list
tools = [..., NewAnalysisTool]
```

## Environment Variables

Required for full functionality:

```bash
# GCP Authentication
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Arize AX Tracing (optional)
ARIZE_SPACE_ID=your_space_id
ARIZE_API_KEY=your_api_key
```

## Common Issues

### ModuleNotFoundError for google.adk.tools

**Wrong**: `from google.adk.tools import FunctionTool`
**Correct**: `from google.adk.tools.function_tool import FunctionTool`

### Temperature Issues with Gemini 3

Don't lower temperature below 1.0 for Gemini 3 - it causes degraded reasoning.

### Async/Await Errors

Always use `pytest-asyncio` and `@pytest.mark.asyncio` for async test functions.

## File Modification Checklist

When modifying the codebase:

- [ ] Update `config.py` for any new configuration
- [ ] Update `tools.py` for new FunctionTools
- [ ] Update `__init__.py` exports if adding agents/tools
- [ ] Update tests in `test_adk_integration.py`
- [ ] Update `README.md` if architecture changes
- [ ] Update `ARCHITECTURE_FLOW.md` for diagram changes
