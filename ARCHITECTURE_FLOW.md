# Insurance AI POC - System Architecture & Flow Diagram

## High-Level Architecture

```mermaid
graph TB
    User[User Request] --> RootAgent[Root Agent<br/>CompetitiveIntelligenceRootAgent]
    RootAgent --> Tools[6 ADK Function Tools]
    
    Tools --> T1[FindLatestQuarterTool]
    Tools --> T2[ValidateDataTool]
    Tools --> T3[FinancialMetricsTool]
    Tools --> T4[CompetitivePositioningTool]
    Tools --> T5[StrategicInitiativesTool]
    Tools --> T6[RiskOutlookTool]
    
    T1 --> UtilityAgent[Utility Agent]
    T2 --> UtilityAgent
    T3 --> FinAgent[Financial Metrics Agent]
    T4 --> CompAgent[Competitive Positioning Agent]
    T5 --> StratAgent[Strategic Initiatives Agent]
    T6 --> RiskAgent[Risk Outlook Agent]
    
    FinAgent --> VSearch[Vertex AI Search<br/>SEC Filings & Earnings Calls]
    CompAgent --> VSearch
    StratAgent --> VSearch
    RiskAgent --> VSearch
    
    VSearch --> Data[(Data Store<br/>10-K/10-Q Filings<br/>Earnings Call Transcripts)]
    
    RootAgent --> Report[Comprehensive Report<br/>Markdown Format]
    Report --> Output[Generated Reports Directory]
    
    style RootAgent fill:#4285f4,color:#fff
    style VSearch fill:#34a853,color:#fff
    style Data fill:#fbbc04,color:#000
    style Report fill:#ea4335,color:#fff
```

## Data Ingestion Pipeline

```mermaid
graph TB
    subgraph "Data Sources"
        SEC[SEC EDGAR API<br/>10-K/10-Q Filings]
        EARN[Earnings Transcripts<br/>API Ninjas API]
        CSV[Company List<br/>commercial_lines.csv]
    end
    
    subgraph "Ingestion Scripts"
        Script1[financial_report_ingestion.py]
        Script2[earnings_call_ingestion.py]
    end
    
    subgraph "Processing Pipeline"
        Fetch1[Fetch SEC Filings<br/>Last 3 years]
        Fetch2[Fetch Earnings Calls<br/>Last 12 quarters]
        Parse1[Parse HTML<br/>Extract by Item sections]
        Parse2[Parse Transcripts<br/>Speaker-aware chunking]
        Chunk1[Create Chunks<br/>8000 chars + 200 overlap]
        Chunk2[Create Chunks<br/>8000 chars + 200 overlap]
        Embed1[Generate Embeddings<br/>text-embedding-004]
        Embed2[Generate Embeddings<br/>text-embedding-004]
        Save1[Save to JSON<br/>chunked_reports/]
        Save2[Save to JSON<br/>chunked_earnings_calls/]
    end
    
    subgraph "Google Cloud Storage"
        GCS[GCS Bucket<br/>Document Storage]
    end
    
    subgraph "Vertex AI Search"
        DS[Data Store<br/>insurance-filings]
        Index[Vector Index<br/>Semantic Search]
    end
    
    CSV --> Script1 & Script2
    
    Script1 --> Fetch1
    SEC --> Fetch1
    Fetch1 --> Parse1
    Parse1 --> Chunk1
    Chunk1 --> Embed1
    Embed1 --> Save1
    Save1 --> DS
    
    Script2 --> Fetch2
    EARN --> Fetch2
    Fetch2 --> Parse2
    Parse2 --> Chunk2
    Chunk2 --> Embed2
    Embed2 --> Save2
    Save2 --> DS
    
    DS --> Index
    DS --> GCS
    
    style Script1 fill:#4285f4,color:#fff
    style Script2 fill:#4285f4,color:#fff
    style DS fill:#34a853,color:#fff
    style Index fill:#fbbc04,color:#000
```

## Ingestion Workflow Details

```mermaid
sequenceDiagram
    participant Admin as Admin/Scheduler
    participant FRScript as financial_report_ingestion.py
    participant ECScript as earnings_call_ingestion.py
    participant SECAPI as SEC EDGAR API
    participant EARNAPI as API Ninjas
    participant Parser as Document Parser
    participant Chunker as Chunking Engine
    participant Embedder as Vertex AI Embeddings
    participant Storage as Local JSON Storage
    participant VAIS as Vertex AI Search

    Note over Admin,VAIS: PHASE 1: SEC FILINGS INGESTION
    
    Admin->>FRScript: Run ingestion
    FRScript->>FRScript: Load commercial_lines.csv
    FRScript->>FRScript: Truncate existing data
    
    loop For each company (7 total)
        FRScript->>SECAPI: Fetch 10-K/10-Q (last 3 years)
        SECAPI-->>FRScript: HTML documents
        FRScript->>Parser: Parse HTML by Item sections
        Parser->>Parser: Extract Items 1, 1A, 2, 7, 8
        Parser->>Parser: Convert tables to Markdown
        Parser-->>FRScript: Structured sections
        
        FRScript->>Chunker: Chunk by section (max 8000 chars)
        Chunker->>Chunker: Apply 200 char overlap
        Chunker->>Chunker: Add metadata (ticker, form, year, quarter)
        Chunker-->>FRScript: Document chunks
        
        FRScript->>Embedder: Generate embeddings (batches of 5)
        Embedder-->>FRScript: Vector embeddings (768-dim)
        
        FRScript->>Storage: Save chunks + embeddings to JSON
    end
    
    FRScript->>VAIS: Import documents (batches of 100)
    VAIS-->>FRScript: Import operation IDs
    FRScript-->>Admin: ✓ SEC filings ingested
    
    Note over Admin,VAIS: PHASE 2: EARNINGS CALLS INGESTION
    
    Admin->>ECScript: Run ingestion
    ECScript->>ECScript: Load commercial_lines.csv
    
    loop For each company (6 total - excl BRK.B)
        ECScript->>EARNAPI: Fetch transcripts (last 12 quarters)
        EARNAPI-->>ECScript: Speaker-split transcripts
        ECScript->>Parser: Parse by speaker segments
        Parser->>Parser: Identify speakers & roles
        Parser-->>ECScript: Speaker-aware sections
        
        ECScript->>Chunker: Chunk by speaker (max 8000 chars)
        Chunker->>Chunker: Preserve speaker context
        Chunker->>Chunker: Add metadata (ticker, quarter, speaker)
        Chunker-->>ECScript: Document chunks
        
        ECScript->>Embedder: Generate embeddings (batches of 5)
        Embedder-->>ECScript: Vector embeddings (768-dim)
        
        ECScript->>Storage: Save chunks + embeddings to JSON
    end
    
    ECScript->>VAIS: Import documents (batches of 100)
    VAIS-->>ECScript: Import operation IDs
    ECScript-->>Admin: ✓ Earnings calls ingested
    
    Note over VAIS: Data ready for AI agents!
```

## Detailed Workflow Sequence

```mermaid
sequenceDiagram
    participant User
    participant RootAgent as Root Agent<br/>(Orchestrator)
    participant Tools as ADK Tools
    participant Util as Utility Agent
    participant Fin as Financial Agent
    participant Comp as Competitive Agent
    participant Strat as Strategic Agent
    participant Risk as Risk Agent
    participant VS as Vertex AI Search
    participant Data as Data Store

    User->>RootAgent: Generate Report for Q3 2025
    
    Note over RootAgent: PHASE 1: Data Discovery & Validation
    RootAgent->>Tools: Call FindLatestQuarterTool()
    Tools->>Util: find_latest_quarter()
    Util->>Data: Check latest complete data
    Data-->>Util: Q3 2025 available
    Util-->>Tools: {year: 2025, quarter: 3}
    Tools-->>RootAgent: Latest quarter info
    
    RootAgent->>Tools: Call ValidateDataTool(2025, 3)
    Tools->>Util: validate_data_availability()
    Util->>Data: Check 7 companies × 2 sources
    Data-->>Util: All companies complete
    Util-->>Tools: {all_complete: true}
    Tools-->>RootAgent: Data validation complete
    
    Note over RootAgent: PHASE 2: Multi-Agent Analysis
    
    par Financial Analysis
        RootAgent->>Tools: Call FinancialMetricsTool(2025, 3)
        Tools->>Fin: extract_financial_metrics()
        Fin->>VS: Query 10-Q filings for commercial metrics
        VS->>Data: Search SEC filings
        Data-->>VS: Commercial segment financials
        VS-->>Fin: Grounded response with citations
        Fin-->>Tools: 15 metrics × 7 companies
        Tools-->>RootAgent: Financial analysis complete
    and Competitive Analysis
        RootAgent->>Tools: Call CompetitivePositioningTool(2025, 3)
        Tools->>Comp: analyze_competitive_positioning()
        Comp->>VS: Query market share, pricing, segments
        VS->>Data: Search 10-K/10-Q MD&A sections
        Data-->>VS: Competitive positioning data
        VS-->>Comp: Grounded analysis
        Comp-->>Tools: Positioning by company
        Tools-->>RootAgent: Competitive analysis complete
    and Strategic Analysis
        RootAgent->>Tools: Call StrategicInitiativesTool(2025, 3)
        Tools->>Strat: identify_strategic_initiatives()
        Strat->>VS: Query earnings calls for initiatives
        VS->>Data: Search transcripts (6 companies)
        Data-->>VS: Strategic topics & discussions
        VS-->>Strat: Company-by-company initiatives
        Strat-->>Tools: Strategic landscape
        Tools-->>RootAgent: Strategic analysis complete
    and Risk Analysis
        RootAgent->>Tools: Call RiskOutlookTool(2025, 3)
        Tools->>Risk: assess_risk_outlook()
        Risk->>VS: Query risk factors, outlook
        VS->>Data: Search risk disclosures
        Data-->>VS: Risk & forward-looking info
        VS-->>Risk: Risk assessment by company
        Risk-->>Tools: Risk analysis
        Tools-->>RootAgent: Risk analysis complete
    end
    
    Note over RootAgent: PHASE 3: Report Synthesis
    RootAgent->>RootAgent: Synthesize all analyses
    RootAgent->>RootAgent: Generate markdown report
    RootAgent->>User: Comprehensive Intelligence Report
    
    Note over User: Report includes:<br/>- Executive Summary<br/>- Financial Performance<br/>- Competitive Positioning<br/>- Strategic Landscape<br/>- Risk & Outlook
```

## Agent Architecture Details

```mermaid
graph LR
    subgraph "Root Agent Layer"
        Root[Root Agent<br/>Gemini 1.5 Pro]
    end
    
    subgraph "Tool Layer (ADK FunctionTools)"
        T1[Find Latest<br/>Quarter]
        T2[Validate<br/>Data]
        T3[Financial<br/>Metrics]
        T4[Competitive<br/>Positioning]
        T5[Strategic<br/>Initiatives]
        T6[Risk<br/>Outlook]
    end
    
    subgraph "Specialized Agent Layer"
        U[Utility Agent<br/>Data Validation]
        F[Financial Agent<br/>Gemini 1.5 Pro<br/>+ Vertex AI Search]
        C[Competitive Agent<br/>Gemini 1.5 Pro<br/>+ Vertex AI Search]
        S[Strategic Agent<br/>Gemini 1.5 Pro<br/>+ Vertex AI Search]
        R[Risk Agent<br/>Gemini 1.5 Pro<br/>+ Vertex AI Search]
    end
    
    subgraph "Data Layer"
        DS[Vertex AI Search<br/>Datastore]
        SEC[SEC Filings<br/>10-K/10-Q]
        EC[Earnings Call<br/>Transcripts]
    end
    
    Root --> T1 & T2 & T3 & T4 & T5 & T6
    T1 & T2 --> U
    T3 --> F
    T4 --> C
    T5 --> S
    T6 --> R
    F & C & S & R --> DS
    DS --> SEC & EC
    
    style Root fill:#4285f4,color:#fff
    style F fill:#34a853,color:#fff
    style C fill:#34a853,color:#fff
    style S fill:#34a853,color:#fff
    style R fill:#34a853,color:#fff
    style DS fill:#fbbc04,color:#000
```

## Data Flow by Analysis Type

```mermaid
graph TD
    subgraph "1. Financial Metrics Analysis"
        FM1[Extract Financial Metrics Tool] --> FM2[Financial Metrics Agent]
        FM2 --> FM3[Query Vertex AI Search:<br/>Commercial segment P&L]
        FM3 --> FM4[SEC 10-Q/10-K filings:<br/>Item 8 Financial Statements<br/>Item 2/7 MD&A]
        FM4 --> FM5[Return 15 metrics × 7 companies:<br/>Written Premiums, Loss Ratio,<br/>Combined Ratio, etc.]
    end
    
    subgraph "2. Competitive Positioning Analysis"
        CP1[Competitive Positioning Tool] --> CP2[Competitive Positioning Agent]
        CP2 --> CP3[Query Vertex AI Search:<br/>Market share, pricing, segments]
        CP3 --> CP4[SEC 10-K/10-Q MD&A:<br/>Item 1 Business Description<br/>Item 7 MD&A Competition]
        CP4 --> CP5[Return positioning analysis:<br/>By company, by product line,<br/>strengths/weaknesses]
    end
    
    subgraph "3. Strategic Initiatives Analysis"
        SI1[Strategic Initiatives Tool] --> SI2[Strategic Initiatives Agent]
        SI2 --> SI3[Query Vertex AI Search:<br/>Earnings call discussions]
        SI3 --> SI4[Earnings Call Transcripts:<br/>6 companies Q&A sessions<br/>Management commentary]
        SI4 --> SI5[Return strategic landscape:<br/>Individual company initiatives<br/>Industry summary]
    end
    
    subgraph "4. Risk & Outlook Analysis"
        RO1[Risk Outlook Tool] --> RO2[Risk Outlook Agent]
        RO2 --> RO3[Query Vertex AI Search:<br/>Risk factors, forward guidance]
        RO3 --> RO4[SEC 10-K Item 1A Risk Factors<br/>10-Q MD&A forward-looking<br/>Earnings call guidance]
        RO4 --> RO5[Return risk assessment:<br/>By company, industry risks,<br/>Hartford risk profile]
    end
    
    style FM1 fill:#e8f4f8
    style CP1 fill:#e8f4f8
    style SI1 fill:#e8f4f8
    style RO1 fill:#e8f4f8
    
    style FM5 fill:#d4edda
    style CP5 fill:#d4edda
    style SI5 fill:#d4edda
    style RO5 fill:#d4edda
```

## Document Processing & Chunking Strategy

```mermaid
graph LR
    subgraph "SEC Filing Processing"
        SEC1[10-K/10-Q HTML] --> SEC2[Parse by Item sections]
        SEC2 --> SEC3[Item 1: Business<br/>Item 1A: Risk Factors<br/>Item 2/7: MD&A<br/>Item 8: Financials]
        SEC3 --> SEC4[Convert tables to Markdown]
        SEC4 --> SEC5[Split into 8KB chunks<br/>200 char overlap]
        SEC5 --> SEC6[Add metadata:<br/>ticker, form, year, quarter, section]
    end
    
    subgraph "Earnings Call Processing"
        EARN1[Transcript TXT] --> EARN2[Parse by speaker]
        EARN2 --> EARN3[Identify speakers:<br/>CEO, CFO, Analysts<br/>Role & Company]
        EARN3 --> EARN4[Preserve speaker context]
        EARN4 --> EARN5[Split into 8KB chunks<br/>200 char overlap]
        EARN5 --> EARN6[Add metadata:<br/>ticker, quarter, year, speaker]
    end
    
    SEC6 --> EMB1[Generate Embeddings<br/>text-embedding-004<br/>768 dimensions]
    EARN6 --> EMB1
    
    EMB1 --> STORE[Save to JSON<br/>+ Upload to Vertex AI Search]
    
    style SEC2 fill:#e8f4f8
    style EARN2 fill:#e8f4f8
    style EMB1 fill:#d4edda
```

## Companies & Data Sources Matrix

```mermaid
graph TB
    subgraph "7 Target Companies"
        HIG[The Hartford - HIG<br/>TARGET COMPANY]
        TRV[Travelers - TRV]
        CB[Chubb - CB]
        AIG[AIG]
        CNA[CNA Financial - CNA]
        WRB[W.R. Berkley - WRB]
        BRK[Berkshire Hathaway - BRK.B<br/>SEC filings only - no earnings calls]
    end
    
    subgraph "Data Sources"
        SEC[SEC Filings<br/>10-K Annual<br/>10-Q Quarterly]
        EARN[Earnings Call Transcripts<br/>Quarterly]
    end
    
    HIG & TRV & CB & AIG & CNA & WRB & BRK --> SEC
    HIG & TRV & CB & AIG & CNA & WRB --> EARN
    
    style HIG fill:#ea4335,color:#fff
    style BRK fill:#fbbc04,color:#000
```

## Report Output Structure

```mermaid
graph TD
    Report[Comprehensive Intelligence Report]
    
    Report --> Exec[Executive Summary<br/>Hartford-focused insights]
    Report --> Fin[Financial Performance<br/>Commercial segment metrics<br/>7 companies comparison]
    Report --> Comp[Competitive Positioning<br/>Market share & strengths<br/>Product line analysis]
    Report --> Strat[Strategic Landscape<br/>Individual company initiatives<br/>Industry trends summary]
    Report --> Risk[Risk & Outlook<br/>Company-specific risks<br/>Industry-wide risks<br/>Hartford risk profile]
    
    Exec --> Citations1[Citations: 10-K/10-Q, Earnings Calls]
    Fin --> Citations2[Citations: 10-Q Item 8, MD&A]
    Comp --> Citations3[Citations: 10-K Item 1, Item 7 MD&A]
    Strat --> Citations4[Citations: Earnings Call Transcripts]
    Risk --> Citations5[Citations: 10-K Item 1A, Earnings Guidance]
    
    style Report fill:#4285f4,color:#fff
    style Citations1 fill:#e8f4f8
    style Citations2 fill:#e8f4f8
    style Citations3 fill:#e8f4f8
    style Citations4 fill:#e8f4f8
    style Citations5 fill:#e8f4f8
```

## Technology Stack

```mermaid
graph LR
    subgraph "AI/ML Layer"
        Gemini[Google Gemini 1.5 Pro<br/>LLM]
        ADK[Google ADK<br/>Agent Framework]
        VASearch[Vertex AI Search<br/>RAG/Grounding]
    end
    
    subgraph "Observability"
        Arize[Arize AX<br/>Tracing & Evaluation]
        OTel[OpenTelemetry<br/>Instrumentation]
    end
    
    subgraph "Data Storage"
        GCS[Google Cloud Storage<br/>Document Storage]
        DataStore[Vertex AI Datastore<br/>Indexed Documents]
    end
    
    subgraph "Development"
        Python[Python 3.12]
        Pytest[Pytest<br/>Testing Framework]
        ADKLib[google-adk library]
    end
    
    ADK --> Gemini
    ADK --> VASearch
    VASearch --> DataStore
    DataStore --> GCS
    
    ADK --> OTel
    OTel --> Arize
    
    Python --> ADKLib
    Python --> Pytest
    
    style Gemini fill:#4285f4,color:#fff
    style VASearch fill:#34a853,color:#fff
    style Arize fill:#ea4335,color:#fff
```

## Execution Flow States

```mermaid
stateDiagram-v2
    [*] --> Initialization
    Initialization --> QuarterDetection: Root Agent starts
    
    QuarterDetection --> DataValidation: Latest quarter found
    QuarterDetection --> Error: No data available
    
    DataValidation --> ParallelAnalysis: All companies complete
    DataValidation --> PartialAnalysis: Some missing data
    DataValidation --> Error: Critical data missing
    
    state ParallelAnalysis {
        [*] --> FinancialMetrics
        [*] --> CompetitivePositioning
        [*] --> StrategicInitiatives
        [*] --> RiskOutlook
        
        FinancialMetrics --> AnalysisComplete
        CompetitivePositioning --> AnalysisComplete
        StrategicInitiatives --> AnalysisComplete
        RiskOutlook --> AnalysisComplete
    }
    
    ParallelAnalysis --> ReportSynthesis: All analyses complete
    PartialAnalysis --> ReportSynthesis: Continue with available data
    
    ReportSynthesis --> ReportGeneration
    ReportGeneration --> SaveReport
    SaveReport --> [*]: Report saved to file
    
    Error --> [*]: Exit with error message
```

## Ingestion Pipeline Details

### Data Collection
- **SEC Filings Source**: SEC EDGAR API (free, public data)
- **Earnings Calls Source**: API Ninjas API (paid: $39/month for 100K requests)
- **Historical Depth**: Last 3 years of data
- **Update Frequency**: Quarterly (post earnings releases)

### Chunking Strategy
- **Chunk Size**: 8,000 characters (optimal for LLM context window)
- **Overlap**: 200 characters (maintains context continuity)
- **SEC Filings**: Chunked by Item sections (preserves document structure)
- **Earnings Calls**: Chunked by speaker segments (preserves speaker context)

### Metadata Enrichment
Each chunk includes:
- **Company Info**: Ticker, name, industry
- **Document Type**: 10-K, 10-Q, or Earnings Call
- **Time Period**: Year, quarter, filing date
- **Structure**: Section/Item number, speaker name/role
- **Content Summary**: Brief description for improved retrieval
- **Source URL**: Link back to original SEC filing

### Embedding Generation
- **Model**: Vertex AI `text-embedding-004`
- **Dimensions**: 768 (high-quality semantic understanding)
- **Batch Size**: 5 chunks per API call (API limit)
- **Purpose**: Enable semantic search & hybrid retrieval

### Storage & Indexing
- **Local Storage**: JSON files with chunks + embeddings
- **Cloud Storage**: GCS bucket for document persistence
- **Vector Index**: Vertex AI Search with hybrid retrieval
- **Reconciliation**: Incremental mode (upsert new, keep existing)

### Ingestion Scripts

#### `financial_report_ingestion.py`
- Fetches 10-K/10-Q filings from SEC EDGAR
- Parses HTML and extracts Item sections
- Converts tables to Markdown for better comprehension
- Chunks by section with metadata
- Generates embeddings
- Imports to Vertex AI Search

#### `earnings_call_ingestion.py`
- Fetches transcripts from API Ninjas
- Parses speaker-split format
- Preserves speaker context (CEO, CFO, Analysts)
- Chunks by speaker segments
- Generates embeddings
- Imports to Vertex AI Search

### Data Volume
- **7 Companies** × **3 Years** × **5 Filings/Year** = ~105 SEC documents
- **6 Companies** × **12 Quarters** = ~72 Earnings call transcripts
- **Total Documents**: ~177 source documents
- **Total Chunks**: ~3,000-5,000 searchable chunks
- **Storage**: ~50-100 MB compressed

## Key Features

### 🎯 Commercial Insurance Focus
- **Exclusively analyzes Commercial Lines/Business Insurance segment**
- Excludes Personal Lines, Life Insurance, Health Insurance
- Key product lines: Workers Compensation, General Liability, Commercial Property, Commercial Auto, Professional Liability

### 🏢 Company Coverage
- **Primary Target**: The Hartford (HIG)
- **Competitors**: Travelers, Chubb, AIG, CNA, W.R. Berkley, Berkshire Hathaway
- **Total**: 7 major commercial insurance companies

### 📊 Data Sources
- **SEC Filings**: 10-K annual reports, 10-Q quarterly reports
- **Earnings Calls**: Quarterly earnings call transcripts (6 companies - BRK.B excluded)
- **Grounding**: Vertex AI Search ensures all claims are cited

### 🔍 Analysis Dimensions
1. **Financial Metrics**: 15+ commercial segment metrics per company
2. **Competitive Positioning**: Market share, strengths, product lines
3. **Strategic Initiatives**: Company-by-company strategic moves + industry trends
4. **Risk & Outlook**: Company-specific and industry-wide risk assessment

### 📝 Citations
- **Detailed SEC Filing Citations**: Part I Item 1, Item 2 MD&A, Item 7, Item 8 Notes
- **Earnings Call Citations**: Specific topics and speakers
- **Page-level references** for all claims

### 🔬 Observability
- **Arize AX Integration**: Full tracing of all agent executions
- **OpenTelemetry**: Instrumentation for Google ADK
- **Performance Metrics**: Token usage, latency, success rates

### ✅ Testing
- **30 Integration Tests**: Comprehensive pytest suite
- **Test Coverage**: Tool trajectories, grounding, full report generation
- **Timeout Handling**: 10-minute timeout for full reports
- **Commercial Focus Validation**: Ensures no personal lines leakage

## Performance Characteristics

- **Full Report Generation**: 4-10 minutes
- **Individual Agent Execution**: 30-120 seconds each
- **Parallel Analysis**: Financial, Competitive, Strategic, Risk agents run independently
- **Token Usage**: ~78,000 tokens for successful full report
- **Report Size**: ~5,000-15,000 characters (comprehensive analysis)

## Error Handling

- **Missing Data**: Graceful degradation with partial reports
- **JSON Parsing Errors**: Fallback schemas ensure continued execution
- **Timeout Management**: Individual agent and full report timeouts
- **Retry Logic**: Automatic retry with exponential backoff
- **Validation**: Pre-flight data availability checks

---

**Last Updated**: November 18, 2025  
**Project**: Insurance AI POC - Commercial Insurance Competitive Intelligence  
**Framework**: Google ADK (Agent Development Kit)
