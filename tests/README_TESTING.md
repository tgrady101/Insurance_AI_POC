# ADK Evaluation and Testing Framework

This directory contains comprehensive testing and evaluation tools for the Competitive Intelligence ADK system, based on Google ADK evaluation best practices.

## Overview

The testing framework includes:

1. **Advanced Evaluation Script** - Comprehensive trajectory and quality testing
2. **ADK Test Cases** - Structured test cases following ADK patterns
3. **Pytest Integration Tests** - Unit and integration tests using pytest
4. **Evaluation Configuration** - Custom evaluation criteria
5. **Arize AX Tracing Integration** - Observability and trace analysis

## Quick Start

### Setup Environment

```bash
# 1. Configure environment variables in .env file
# Copy .env.example to .env and set your credentials:
#
# Required: GCP credentials
# GOOGLE_CLOUD_PROJECT=your-project-id
# GOOGLE_CLOUD_LOCATION=global
# GOOGLE_GENAI_USE_VERTEXAI=true
#
# Optional: Arize AX tracing (get from https://app.arize.com → Space Settings)
# ARIZE_SPACE_ID=your-space-id
# ARIZE_API_KEY=your-api-key

# 2. Install test dependencies
pip install pytest pytest-asyncio pytest-timeout

# 3. Run tests (environment variables loaded automatically from .env)
pytest tests/test_adk_integration.py -v
```

### Run Basic Tests (Fast)
```bash
# Run all pytest tests (skip slow ones)
pytest tests/test_adk_integration.py -m "not slow" -v

# Run only fast unit tests
pytest tests/test_adk_integration.py::TestToolTrajectory -v
pytest tests/test_adk_integration.py::TestGroundingConfiguration -v

# Run tracing tests (if Arize configured)
pytest tests/test_adk_integration.py::TestArizeTracing -v
```

### Run Comprehensive Evaluation
```bash
# Full evaluation with trajectory testing (2-3 minutes)
# Environment variables loaded from .env file automatically
python test_advanced_evaluation.py

# Arize tracing is automatically enabled if ARIZE_SPACE_ID 
# and ARIZE_API_KEY are set in your .env file
```

### Run Integration Tests (Slow)
```bash
# Full integration test suite (5-10 minutes)
pytest tests/test_adk_integration.py -v

# Only integration tests
pytest tests/test_adk_integration.py -m integration -v

# Integration tests with tracing
pytest tests/test_adk_integration.py -m integration -v  # Auto-enables if credentials set
```

## Test Files

### 1. `test_advanced_evaluation.py`
**Purpose**: Comprehensive ADK-style evaluation script

**Features**:
- Tool trajectory evaluation (expected vs actual tool calls)
- Intermediate agent response validation
- Grounding verification
- Citation checking
- Final report quality assessment
- GCS upload testing

**Run**:
```bash
python test_advanced_evaluation.py
```

**Output**:
- Console summary with pass/fail/warning counts
- Detailed JSON results file: `eval_results_YYYYMMDD_HHMMSS.json`
- Generated report saved locally and to GCS

**Evaluation Metrics**:
- Tool Trajectory Average Score (ADK metric, 0.0-1.0)
- Tool call sequence verification
- Response quality assessment
- Grounding effectiveness

### 2. `tests/test_adk_integration.py`
**Purpose**: Pytest-based integration tests

**Test Classes**:
- `TestToolTrajectory` - Verify tool call patterns
- `TestGroundingConfiguration` - Verify VertexAiSearchTool setup
- `TestToolFunctions` - Test individual tool behavior
- `TestRootAgentIntegration` - Test root agent coordination
- `TestFullReportGeneration` - End-to-end report generation
- `TestCommercialSegmentFocus` - Verify commercial focus
- `TestArizeTracing` - Arize AX tracing validation
- `TestErrorHandling` - Edge case and error handling
- `TestPerformance` - Timeout and performance benchmarks

**Run Specific Test Classes**:
```bash
# Test only tool trajectories
pytest tests/test_adk_integration.py::TestToolTrajectory -v

# Test only grounding configuration
pytest tests/test_adk_integration.py::TestGroundingConfiguration -v

# Test full report generation
pytest tests/test_adk_integration.py::TestFullReportGeneration -v
```

**Markers**:
- `@pytest.mark.slow` - Tests that take >10 seconds
- `@pytest.mark.integration` - Full integration tests
- `@pytest.mark.tracing` - Arize AX tracing tests
- `@pytest.mark.asyncio` - Async tests

**Skip Slow Tests**:
```bash
pytest tests/test_adk_integration.py -m "not slow" -v
```

### 3. ADK Test Case Files

#### `tests/competitive_intelligence_basic.test.json`
**Purpose**: Unit test cases for basic workflows

**Test Cases**:
- `test_find_latest_quarter` - Latest quarter detection
- `test_data_validation` - Data availability checking
- `test_financial_metrics_extraction` - Financial metrics extraction

**ADK Format**: Individual test file for simple session testing

#### `tests/competitive_intelligence_full_report.evalset.json`
**Purpose**: Integration test cases for full reports

**Test Cases**:
- `full_quarterly_report` - Complete report generation workflow
- `specific_competitor_analysis` - Targeted competitor comparison

**ADK Format**: Evalset file for complex multi-turn sessions

### 4. `tests/test_config.json`
**Purpose**: Evaluation criteria configuration

**Criteria Configured**:
- `tool_trajectory_avg_score: 1.0` - Exact tool sequence match required
- `response_match_score: 0.8` - 80% text similarity threshold
- `final_response_match_v2` - LLM-judged semantic matching
- `rubric_based_tool_use_quality_v1` - Custom tool use rubrics:
  - Correct tool sequence
  - Complete analysis (all 4 specialized agents)
  - No redundant calls
- `rubric_based_final_response_quality_v1` - Response quality rubrics:
  - Commercial segment focus
  - Citation quality
  - Comprehensive coverage (5+ companies)
  - Structured format
  - Actionable insights
- `hallucinations_v1` - Grounding verification
- `safety_v1` - Safety checking

## ADK Evaluation Framework Integration

### Using ADK Web UI (Recommended for Interactive Testing)

```bash
# Start ADK web server
adk web src/ai_poc/workflow_1/agents

# In browser:
# 1. Navigate to http://localhost:8000
# 2. Select CompetitiveIntelligenceRootAgent
# 3. Test queries interactively
# 4. Go to Eval tab
# 5. Add session to eval set
# 6. Run evaluation with custom metrics
```

### Using ADK CLI

```bash
# Run evaluation on evalset file
adk eval \
    src/ai_poc/workflow_1/agents \
    tests/competitive_intelligence_full_report.evalset.json \
    --config_file_path=tests/test_config.json \
    --print_detailed_results
```

### Using AgentEvaluator (Programmatic)

```python
from google.adk.evaluation.agent_evaluator import AgentEvaluator
import pytest

@pytest.mark.asyncio
async def test_basic_workflow():
    """Test basic workflow with ADK evaluator."""
    await AgentEvaluator.evaluate(
        agent_module="ai_poc.workflow_1.agents",
        eval_dataset_file_path_or_dir="tests/competitive_intelligence_basic.test.json",
    )
```

## Test Scenarios Covered

### 1. Tool Trajectory Testing
Verifies agents call tools in the correct sequence:

**Expected Full Report Trajectory**:
1. `find_latest_quarter`
2. `validate_data_availability`
3. `extract_financial_metrics`
4. `analyze_competitive_positioning`
5. `track_strategic_initiatives`
6. `assess_risk_outlook`

**Scoring**:
- 1.0 = Perfect match
- 0.5 = Correct tools, wrong sequence
- 0.5 = Half of required tools called

### 2. Grounding Verification
Ensures all specialized agents use VertexAiSearchTool:

**Checks**:
- FinancialMetricsAgent has VertexAiSearchTool ✓
- CompetitivePositioningAgent has VertexAiSearchTool ✓
- StrategicInitiativesAgent has VertexAiSearchTool ✓
- RiskOutlookAgent has VertexAiSearchTool ✓

### 3. Commercial Segment Focus
Verifies focus on Commercial Lines insurance:

**Positive Indicators**:
- Mentions: Commercial, Workers Compensation, General Liability
- Analyzes: Commercial P&C metrics only

**Negative Indicators** (should be excluded):
- Personal Lines, Auto Insurance, Homeowners
- Life Insurance, Health Insurance

### 4. Citation Quality
Checks for proper source attribution:

**Expected Citation Patterns**:
- References to 10-K, 10-Q filings
- Earnings call citations
- Specific date/quarter references
- Source markers: [source], according to, based on

### 5. Company Coverage
Ensures comprehensive competitive analysis:

**Target Companies** (7):
- HIG (The Hartford)
- TRV (Travelers)
- CB (Chubb)
- AIG (American International Group)
- PGR (Progressive)
- CNA (CNA Financial)
- BRK.B (Berkshire Hathaway)

**Threshold**: Minimum 5/7 companies mentioned

### 6. Data Quality
Validates data structure and completeness:

**Checks**:
- Latest quarter detection (1-4 range, 2023-2026 range)
- Data availability for all companies
- BRK.B special handling (no earnings calls)
- Proper JSON structure in tool responses
- Required fields present in all responses

## Evaluation Results

### Output Files

**Advanced Evaluation**:
- `eval_results_YYYYMMDD_HHMMSS.json` - Detailed evaluation results
- `eval_report_Q{quarter}_{year}_YYYYMMDD_HHMMSS.md` - Generated report

**Pytest**:
- Console output with pass/fail/skip counts
- Detailed test logs with `-v` flag
- HTML reports with `--html=report.html` flag

### Key Metrics

**Tool Trajectory Average Score**:
- ADK standard metric
- 1.0 = Perfect trajectory match
- 0.8+ recommended for production
- < 0.5 indicates significant issues

**Response Match Score**:
- ROUGE-1 similarity to reference
- 0.8+ recommended (allows minor wording variations)
- < 0.5 indicates content divergence

**Grounding Score**:
- Binary: All 4 agents must have VertexAiSearchTool
- Critical for citation quality
- 100% required for production

## Continuous Integration

### Add to CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: ADK Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio
      
      - name: Run fast tests
        run: pytest tests/test_adk_integration.py -m "not slow" -v
      
      - name: Run evaluation (on main branch only)
        if: github.ref == 'refs/heads/main'
        run: python test_advanced_evaluation.py
```

## Troubleshooting

### Common Issues

**Issue**: Tests fail with "Missing key inputs argument"
**Solution**: Ensure all specialized agents have:
```python
Agent(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=GCP_LOCATION
)
```

**Issue**: Grounding tests fail
**Solution**: Verify VertexAiSearchTool is imported:
```python
from google.adk.tools import VertexAiSearchTool
```

**Issue**: Report generation times out
**Solution**: Increase pytest timeout or use `@pytest.mark.slow`:
```bash
pytest --timeout=300 tests/test_adk_integration.py
```

**Issue**: Tool trajectory scores low
**Solution**: Check tool call order in logs. Expected sequence:
1. find_latest_quarter (always first)
2. validate_data_availability (optional but recommended)
3. Analysis tools (order flexible)

## Best Practices

### 1. Run Tests Frequently
- Fast tests (< 1 min): After every code change
- Full evaluation (2-3 min): Before commits
- Integration tests (5-10 min): Before PR merge

### 2. Use Appropriate Test Markers
```python
@pytest.mark.slow  # For tests > 10 seconds
@pytest.mark.integration  # For end-to-end tests
@pytest.mark.asyncio  # For async tests
```

### 3. Monitor Key Metrics
- Tool trajectory score should be 1.0
- All 4 agents must have grounding
- Commercial focus verified in all outputs
- Citations present in final reports

### 4. Update Test Cases
When adding new features:
1. Add unit test in `test_adk_integration.py`
2. Add trajectory test in `test_advanced_evaluation.py`
3. Update expected tool sequences
4. Update evaluation rubrics in `test_config.json`

### 5. Document Failures
When tests fail:
1. Capture full error output
2. Check trajectory in ADK trace view
3. Verify grounding is working
4. Review LLM responses for issues

## Arize AX Tracing Integration

### Overview

All tests automatically support Arize AX tracing when credentials are configured. This provides:

- **Complete execution traces** for every test run
- **Performance metrics** for agent and tool executions
- **Debugging capabilities** via trace inspection
- **Quality analysis** using Arize's Alyx AI copilot

### Setup Tracing for Tests

```bash
# 1. Add credentials to .env file (get from https://app.arize.com → Space Settings)
# ARIZE_SPACE_ID=your-space-id
# ARIZE_API_KEY=your-api-key

# 2. Run tests - tracing happens automatically
pytest tests/test_adk_integration.py -v
```

### What Gets Traced

**Session-level Setup** (conftest.py):
- Tracing initialized once before all tests
- Automatic instrumentation of all ADK agents
- Project name: `insurance-competitive-intelligence`

**Per-test Tracing**:
- ✅ All agent executions (root + specialized)
- ✅ Tool calls (financial, competitive, strategic, risk)
- ✅ Vertex AI Search queries
- ✅ LLM prompts and responses
- ✅ Token usage and latency

### Viewing Test Traces

1. **Go to Arize AX**: https://app.arize.com
2. **Select project**: `insurance-competitive-intelligence`
3. **Navigate to**: Observe → Traces
4. **Filter by**:
   - Time range: Recent
   - Environment: `test`
   - Search for specific test names

### Test Trace Organization

Traces include metadata:
- **Test name**: Full pytest test path
- **Test session**: Unique session ID per run
- **Environment**: `test` (vs `development`, `production`)
- **Tool sequence**: Complete execution hierarchy
- **Timing**: Per-agent and per-tool latency

### Tracing Test Class

`TestArizeTracing` validates the tracing setup:

```bash
# Run only tracing validation tests
pytest tests/test_adk_integration.py::TestArizeTracing -v
```

**Tests include**:
- ✅ Arize config module exists
- ✅ Credentials configured correctly
- ✅ OpenTelemetry packages installed
- ✅ Tracing initializes without errors
- ✅ Agent executions are traced

### Disabling Tracing

Tests run normally without tracing if credentials aren't set:

```bash
# Option 1: Comment out in .env file
# #ARIZE_SPACE_ID=your-space-id
# #ARIZE_API_KEY=your-api-key

# Option 2: Temporarily unset (PowerShell)
$env:ARIZE_SPACE_ID = $null
$env:ARIZE_API_KEY = $null

# Option 3: Temporarily unset (Bash)
# unset ARIZE_SPACE_ID
# unset ARIZE_API_KEY

# Run tests without tracing
pytest tests/test_adk_integration.py -v
```

**Note**: Tests marked with `@pytest.mark.tracing` will be skipped if credentials aren't configured.

### Benefits for Testing

1. **Debugging Test Failures**
   - View exact LLM prompts and responses
   - See tool call sequences that led to errors
   - Identify performance bottlenecks

2. **Performance Benchmarking**
   - Track test execution time trends
   - Identify slow agents or tools
   - Monitor token usage

3. **Quality Analysis**
   - Use Alyx AI to analyze test traces
   - Compare successful vs failed test patterns
   - Identify common failure modes

4. **Regression Detection**
   - Compare trace patterns across test runs
   - Detect changes in tool call sequences
   - Monitor response quality over time

### Example: Analyzing Failed Test

```bash
# 1. Ensure Arize credentials are set in .env file
# 2. Run test (tracing enabled automatically)
pytest tests/test_adk_integration.py::TestFullReportGeneration::test_generate_full_report -v

# If test fails:
# 1. Note the test session ID from console output
# 2. Go to https://app.arize.com → Traces
# 3. Search for session ID or test name
# 4. Inspect the trace to see:
#    - Which tool call failed
#    - What the LLM prompt was
#    - What the response contained
#    - Where the assertion failed
```

### Trace Retention

- **Traces stored**: 30 days (Arize default)
- **Searchable by**: Test name, session ID, timestamp
- **Exportable**: Yes (via Arize UI or API)

## References

- [ADK Evaluation Documentation](https://google.github.io/adk-docs/evaluate/)
- [ADK Evaluation Criteria](https://google.github.io/adk-docs/evaluate/criteria/)
- [ADK Tools Documentation](https://google.github.io/adk-docs/tools/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Arize AX Documentation](https://arize.com/docs/ax)
- [OpenInference Instrumentation](https://github.com/Arize-ai/openinference)

## Support

For issues or questions:
1. Check test output for specific error messages
2. Review ADK documentation for evaluation patterns
3. Examine trajectory in ADK web UI trace view
4. Verify grounding configuration in specialized agents
