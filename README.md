# Commercial Insurance Competitive Intelligence System

> **AI-Powered Quarterly Analysis of US Commercial Insurance Markets**

Automated competitive intelligence platform using Google Cloud's Agent Development Kit (ADK) and Vertex AI to analyze SEC filings and earnings calls for 7 major US commercial insurers.

## 📊 Overview

This system generates comprehensive quarterly competitive intelligence reports for **The Hartford's Commercial Lines business** by analyzing public financial documents from major US commercial insurance carriers.

### Target Company
- **Primary Focus**: The Hartford (HIG) - Commercial Lines segment

### Analyzed Competitors
- **Travelers (TRV)** - Business Insurance segment
- **Chubb (CB)** - North America Commercial
- **AIG** - North America Commercial
- **CNA Financial (CNA)** - Commercial segment
- **W.R. Berkley (WRB)** - Insurance segment
- **Berkshire Hathaway (BRK.B)** - BH Primary segment

### Data Sources
- **SEC Filings**: 10-K (annual), 10-Q (quarterly) - 177 documents
- **Earnings Call Transcripts**: Quarterly calls (6 companies, excluding BRK.B)
- **Coverage Period**: Q1 2023 - Q3 2025

---

## 🏗️ Architecture

### Multi-Agent System (Google ADK)

The system uses a **Root Orchestrator** with 5 specialized agents:

```
┌─────────────────────────────────────────────────┐
│         Root Agent (Orchestrator)               │
│  - Report generation & synthesis                │
│  - Citation consolidation                       │
└───────────────┬─────────────────────────────────┘
                │
        ┌───────┴────────┐
        │  FunctionTools  │
        └───────┬────────┘
                │
    ┌───────────┼───────────┬───────────┬──────────┐
    ▼           ▼           ▼           ▼          ▼
┌─────────┐ ┌──────┐ ┌──────────┐ ┌─────────┐ ┌─────┐
│Utility  │ │Finan-│ │Competi-  │ │Strategic│ │Risk │
│Agent    │ │cial  │ │tive      │ │Initia-  │ │Out- │
│         │ │Metrics│ │Position- │ │tives    │ │look │
│-Find    │ │Agent │ │ing Agent │ │Agent    │ │Agent│
│ quarter │ │      │ │          │ │         │ │     │
│-Validate│ │-Extract│ │-Market  │ │-M&A     │ │-Risks│
│ data    │ │ metrics│ │ share   │ │-Digital │ │-Expo-│
│         │ │-Company│ │-Strengths│ │-Product │ │ sures│
│         │ │ compare│ │ & gaps  │ │-Org     │ │     │
└─────────┘ └──────┘ └──────────┘ └─────────┘ └─────┘
```

### Data Pipeline

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│SEC EDGAR API │────▶│  Download   │────▶│ HTML to MD   │
│  10-K/10-Q   │     │  & Clean    │     │ Conversion   │
└──────────────┘     └─────────────┘     └──────┬───────┘
                                                │
┌──────────────┐     ┌─────────────┐           │
│API Ninjas    │────▶│  Download   │───────────┤
│Earnings Calls│     │ Transcripts │           │
└──────────────┘     └─────────────┘           │
                                                ▼
                                      ┌──────────────────┐
                                      │   Chunking       │
                                      │ - 8KB chunks     │
                                      │ - 200 char overlap│
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │ GCS Upload       │
                                      │ JSON w/metadata  │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │Vertex AI Search  │
                                      │  Data Store      │
                                      │ (RAG/Grounding)  │
                                      └──────────────────┘
```

### Report Generation Flow

```
1. Root Agent receives request (ticker, quarter, year)
   │
2. Call utility_agent.find_latest_quarter()
   │
3. Call utility_agent.validate_data_availability()
   │
4. Call financial_metrics.extract_all_companies()
   │  └─▶ Extract 7 key metrics from 10-Q segment tables
   │      (Prioritize SEC filings > earnings calls)
   │
5. Call competitive_positioning.analyze_positioning()
   │  └─▶ Analyze Hartford vs peers using earnings calls
   │
6. Call strategic_initiatives.analyze_initiatives()
   │  └─▶ Extract M&A, digital, product initiatives
   │
7. Call risk_outlook.assess_risks()
   │  └─▶ Identify commercial segment risks
   │
8. Root Agent synthesizes all outputs
   │
9. Generate Markdown report with citations
   └─▶ Save to generated_reports/
```

---

## 📈 Key Features

### Commercial Segment Focus
- **Filters out**: Personal Lines, Life Insurance, Group Benefits
- **Extracts only**: Commercial Lines / Business Insurance / Commercial P&C metrics
- Company-specific segment mapping (e.g., TRV "Business Insurance", AIG dual segments)

### Financial Metrics Extraction
**8 Key Metrics** (from 10-Q/10-K segment tables):
1. Net Written Premiums (absolute $M)
2. Net Written Premiums Growth (%)
3. Net Earned Premiums (absolute $M)
4. Combined Ratio (%)
5. Loss Ratio (%)  
6. Expense Ratio (%)
7. Underwriting Income ($M)
8. Catastrophe Losses ($M)

**Data Source Priority** (for metrics table only):
1. **Primary**: 10-Q/10-K SEC filings (auditable)
2. **Fallback**: Earnings calls (if not in SEC filing)

### Company-Specific Extraction Rules

| Company | Segment Name | Special Notes |
|---------|--------------|---------------|
| **TRV** | Business Insurance | Combined ratio in "Results of Business Insurance" table |
| **HIG** | Business Insurance | **CRITICAL**: Use "Underwriting Ratios" table (bottom of section) for Combined Ratio from "Three Months Ended" column; DO NOT use "Underlying combined ratio" or calculate manually |
| **AIG** | North America Commercial | Focus on NA Commercial segment only |
| **CB** | North America Commercial | Standard segment table |
| **CNA** | Commercial column | Use "Core income (loss)" as underwriting income |
| **WRB** | Insurance segment | Note 22 Business Segments |
| **BRK.B** | BH Primary | Exclude GEICO (personal) and BHRG (reinsurance) |

### Competitive Intelligence
- Market share analysis (commercial lines only)
- Strengths & gaps assessment
- Strategic initiatives tracking (M&A, digital, products)
- Risk exposure analysis
- 2-3 actionable recommendations for Hartford

### Metadata-Driven Search
- **Year/Quarter Filtering**: All Vertex AI Search queries include year (number) and quarter (string "Q3") metadata
- **Query Pattern**: `"{TICKER} {year} Q{quarter} {topic}"` ensures retrieval from correct reporting period
- **Example**: `"HIG 2025 Q3 business insurance underwriting ratios"` filters to Q3 2025 documents only

### Batched Parallel Processing
- **Financial Metrics**: Processes companies in batches of 2 using `asyncio.gather()`
- **Error Isolation**: Each company extraction independent; partial failures don't block others
- **Timeout**: 10 minutes per company (handles complex multi-search extractions)
- **Performance**: ~3-5 minutes for 7 companies vs ~15-20 minutes sequential

### Citation System
- **Every metric cited**: `[Source: TRV 10-Q Q3 2025, Segment Results - Business Insurance, Page 45]`
- **Earnings calls**: `[Source: HIG Q3 2025 Earnings Call, CEO commentary]`
- **Consolidated references** section at end of report

---

## 🛠️ Technology Stack

### Core AI/ML
- **Google ADK 1.18.0**: Agent Development Kit for multi-agent orchestration
- **Vertex AI Gemini 3.0 Pro (Preview)**: LLM for analysis and generation (1M token context)
- **Vertex AI Search**: RAG/grounding with semantic + hybrid search
- **Vertex AI Search**: Automatic embedding generation during import

### Google Cloud Platform
- **Vertex AI Agent Builder**: Agent runtime environment
- **Discovery Engine**: Document search and retrieval
- **Cloud Storage**: Raw document and chunk storage
- **Secret Manager**: API key management

### Data Processing
- **requests**: SEC EDGAR API, API Ninjas earnings calls
- **BeautifulSoup4**: HTML parsing
- **markdownify**: HTML to Markdown conversion
- **google-cloud-storage**: GCS operations
- **google-cloud-discoveryengine**: Datastore management

### Observability (Optional)
- **Arize DX**: Tracing and observability
- **OpenTelemetry**: Instrumentation
- **openinference-instrumentation-google-adk**: ADK tracing

### Testing
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-timeout**: Test timeouts (600s for full reports)

---

## 📁 Project Structure

```
Insurance_AI_POC/
├── src/ai_poc/workflow_1/
│   ├── agents/
│   │   ├── root_agent.py              # Orchestrator
│   │   ├── utility_agent.py           # Data validation
│   │   ├── financial_metrics_agent.py # Metrics extraction
│   │   ├── competitive_positioning_agent.py
│   │   ├── strategic_initiatives_agent.py
│   │   ├── risk_outlook_agent.py
│   │   ├── tools.py                   # FunctionTools wrapper
│   │   └── config.py                  # GCP config
│   ├── scripts/
│   │   ├── financial_report_ingestion.py  # 10-K/10-Q pipeline
│   │   ├── earnings_call_ingestion.py     # Earnings call pipeline
│   │   └── upload_raw_files.py            # GCS upload utility
│   └── arize_tracing/
│       └── arize_config.py            # Observability setup
├── tests/
│   ├── test_adk_integration.py        # Agent tests (30 tests)
│   └── pytest.ini                     # Test configuration
├── downloaded_reports/                # Raw 10-K/10-Q HTML files
├── downloaded_earnings_calls/         # Raw earnings transcripts (TXT)
├── chunked_reports/                   # Chunked 10-K/10-Q JSON
├── chunked_earnings_calls/            # Chunked earnings JSON
├── generated_reports/                 # Final markdown reports
├── ARCHITECTURE_FLOW.md              # Detailed architecture diagrams
├── .env                              # GCP credentials (not in repo)
├── pyproject.toml                    # Dependencies
└── README.md                         # This file
```

---

## 🚀 Getting Started

### Prerequisites
1. **Python 3.8+** (tested on 3.12.5)
2. **Google Cloud Project** with:
   - Vertex AI API enabled
   - Discovery Engine API enabled
   - Service account with appropriate permissions
3. **API Keys**:
   - SEC EDGAR (optional - uses public endpoint)
   - API Ninjas (for earnings calls)

### Installation

```bash
# Clone repository
git clone https://github.com/tgrady101/Insurance_AI_POC.git
cd Insurance_AI_POC

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .

# Install development dependencies
pip install pytest pytest-asyncio pytest-timeout
```

### Configuration

Create `.env` file in project root:

```bash
# GCP Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=TRUE

# Vertex AI Search
DATA_STORE_ID=insurance-filings
DATA_STORE_LOCATION=global

# API Keys
API_NINJAS_KEY=your-api-ninjas-key

# Optional: Arize Tracing
ARIZE_SPACE_ID=your-space-id
ARIZE_API_KEY=your-api-key
```

### Data Ingestion

**Step 1: Download & Process SEC Filings**
```bash
python src/ai_poc/workflow_1/scripts/financial_report_ingestion.py
```
- Downloads 10-K/10-Q from SEC EDGAR
- Converts HTML → Markdown
- Chunks into 8KB segments with 200 char overlap
- Uploads to Vertex AI Search (embeddings generated automatically)

**Step 2: Download & Process Earnings Calls**
```bash
python src/ai_poc/workflow_1/scripts/earnings_call_ingestion.py
```
- Downloads transcripts from API Ninjas
- Chunks transcripts (8KB, 200 overlap)
- Uploads to Vertex AI Search (embeddings generated automatically)

**Expected Output**:
- 177 SEC documents → ~3,000-5,000 chunks
- ~88 earnings call transcripts → ~2,000 chunks
- Total: ~5,000-7,000 searchable document chunks

### Generate Report

```python
from src.ai_poc.workflow_1.agents import create_agent

# Create root agent
agent = create_agent()

# Generate Q3 2025 report for Hartford
report = agent.generate_report(
    ticker="HIG",
    year=2025,
    quarter=3
)

# Report saved to: generated_reports/
```

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_adk_integration.py::TestFullReportGeneration -v

# Skip slow tests (report generation)
pytest tests/ -m "not slow" -v

# Run with timeout (600s for full reports)
pytest tests/ -v --timeout=600
```

### Demo Parallel Processing

See the performance improvement from parallel company analysis:

```bash
python demo_parallel_processing.py
```

This demo shows:
- Real-time parallel execution of 7 company analyses
- Performance comparison vs sequential processing
- Error handling and partial results
- Typical speedup: 5-7x faster (2-5 minutes vs 14-35 minutes)

---

## 📊 Sample Output

Generated reports include:

### Executive Summary
- 3-5 key findings for Hartford's commercial lines leadership
- Citations for every claim

### Commercial Segment Financial Performance Table
| Metric | HIG | TRV | CB | BRK.B | AIG | CNA | WRB |
|--------|-----|-----|-------|-------|-----|-----|-----|
| Net Written Premiums ($M) | $3,040 | $5,675 | $5,663 | $5,273 | $2,435 | N/A | $2,810 |
| Net Written Premiums Growth | 9% | 2.9% | 3.0% | 3.9% | 7.0% | 12% | 5.1% |
| Net Earned Premiums ($M) | $3,010 | $5,658 | $5,500 | N/A | $2,400 | N/A | $2,750 |
| Combined Ratio | 88.8% | 92.9% | 81.5% | 89.3% | 82.6% | 90.9% | 92.3% |
| Loss Ratio | 56.9% | 63.3% | 60.7% | 60.3% | 59.3% | 64.8% | 63.9% |
| Expense Ratio | 31.9% | 29.6% | 20.8% | 29.0% | 23.3% | N/A | 28.4% |
| Underwriting Income ($M) | $366 | $402 | $941 | $506 | $384 | N/A | $213.5 |
| Catastrophe Losses ($M) | $39 | $139 | N/A | N/A | $68 | $57 | $70 |

### Competitive Position Analysis
- Hartford's rank among peers
- Strengths (e.g., Small Commercial leadership)
- Gaps (e.g., Global Specialty growth)
- Opportunities

### Strategic Landscape
- Industry themes (pricing, digital, specialty lines)
- Company-specific initiatives
- Hartford's positioning vs peers

### Risk Assessment
- Hartford-specific risks
- Industry-wide risks (social inflation, cat losses)

### Recommendations
- 2-3 actionable strategic implications

### References
- Consolidated citation list

---

## 🧪 Testing

**Test Suite**: 30 tests across 6 test classes

### Test Categories
1. **Tool Trajectory**: Latest quarter detection, data validation
2. **Grounding Configuration**: Vertex AI Search connectivity
3. **Individual Tools**: Each agent tested independently
4. **Root Agent Integration**: Full workflow with mocked data
5. **Full Report Generation**: End-to-end Q3 2025 report (slow test)
6. **Arize Tracing**: Observability validation

### Test Execution Time
- **Fast tests** (~30 tests): 2-5 minutes
- **Full report generation**: 4-10 minutes
- **Total suite**: ~15 minutes

---

## 🔍 Key Design Decisions

### 1. Commercial Segment Filtering
**Why**: Hartford's primary interest is commercial insurance, not personal lines or life insurance.
- Agents explicitly instructed to exclude non-commercial data
- Company-specific segment mapping (e.g., TRV "Business Insurance")

### 2. SEC Filing Priority (Metrics Table)
**Why**: Auditable, official source for financial metrics.
- 10-Q/10-K searched first
- Earnings calls used only as fallback
- Other sections: both sources have equal weight

### 3. Multi-Agent Architecture
**Why**: Specialization improves accuracy and maintainability.
- Each agent has focused expertise
- Root agent orchestrates and synthesizes
- Easier to debug and enhance individual components

### 4. Vertex AI Search RAG
**Why**: Handles large document corpus with semantic search.
- 5,000-7,000 document chunks
- Automatic grounding reduces hallucination
- Citations provided automatically

### 5. 8KB Chunk Size with 200 Overlap
**Why**: Balance between context and granularity.
- Large enough for segment tables
- Small enough for focused retrieval
- Overlap prevents information loss at boundaries

### 6. Parallel Processing for Company Analysis
**Why**: Significant performance improvement with independent company data.
- Financial metrics extraction uses `asyncio.gather()` for concurrent execution
- **7x speedup**: ~35 minutes sequential → ~5 minutes parallel
- Each company analyzed independently with isolated error handling
- Results merged into single dictionary for easy access

See `PARALLEL_PROCESSING.md` for implementation details and performance benchmarks.

---

## 📝 Known Limitations

1. **BRK.B Competitive Positioning**: Excluded from earnings call analysis (no transcripts available)
2. **Metric Availability**: Some companies don't disclose all 8 metrics (marked as "Not Disclosed")
3. **AIG Complexity**: Dual-segment reporting requires special handling
4. **Historical Data**: Limited to Q1 2023 - Q3 2025 (expandable)
5. **Model Availability**: Gemini 3 Pro preview requires project/region enablement; fallback to Gemini 1.5 Pro if unavailable
6. **JSON Parsing**: Robust extraction finds JSON even when models add preamble text (e.g., "The commercial segment for...")

---

## 🔮 Future Enhancements

- [ ] PDF/HTML report export (Pandoc integration)
- [ ] Automated quarterly refresh pipeline
- [ ] Interactive dashboard (Streamlit/Dash)
- [ ] Trend analysis across multiple quarters
- [ ] Additional metrics (ROE, retention rate, new business growth)
- [ ] More granular specialty line analysis (cyber, D&O, E&O)
- [ ] Integration with internal Hartford data sources
- [ ] Automated alert system for competitive changes

---

## 📚 Resources

- **Architecture Diagrams**: See `ARCHITECTURE_FLOW.md` (13 Mermaid diagrams)
- **Google ADK Docs**: https://google.github.io/adk-docs/
- **Vertex AI Search**: https://cloud.google.com/vertex-ai-search-and-conversation
- **SEC EDGAR**: https://www.sec.gov/edgar/searchedgar/companysearch.html
- **API Ninjas Earnings Calls**: https://api-ninjas.com/api/earningstranscript

---

## 🤝 Contributing

This is a proof-of-concept project. For questions or suggestions:
1. Open an issue on GitHub
2. Submit a pull request with improvements
3. Contact: tgrady101

---

## 📄 License

MIT License - See LICENSE file for details

---

**Built with** ❤️ **using Google Cloud Agent Development Kit and Vertex AI**
