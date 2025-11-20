"""
Arize AX Tracing Configuration

Sets up OpenTelemetry tracing for Google ADK agents with Arize AX observability.
"""

import os
from arize.otel import register
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

# Configuration - Set these environment variables or modify here
ARIZE_SPACE_ID = os.getenv("ARIZE_SPACE_ID")  # Get from Arize AX space settings
ARIZE_API_KEY = os.getenv("ARIZE_API_KEY")  # Get from Arize AX space settings
PROJECT_NAME = "insurance-competitive-intelligence"


def setup_arize_tracing():
    """
    Initialize Arize AX tracing for the competitive intelligence system.
    
    This will trace:
    - All ADK agent executions
    - Tool calls (financial metrics, competitive analysis, etc.)
    - Vertex AI Search grounding
    - Agent-to-agent interactions
    - Complete report generation workflow
    
    Returns:
        tracer_provider: The configured OpenTelemetry tracer provider
    """
    print("\n" + "="*80)
    print("INITIALIZING ARIZE AX TRACING")
    print("="*80)
    
    # Check for required configuration
    if not ARIZE_API_KEY:
        print("⚠️  WARNING: ARIZE_API_KEY not set!")
        print("   Set environment variable: ARIZE_API_KEY=your-api-key")
        print("   Get from: https://app.arize.com (Space Settings > API Keys)")
        print("   Tracing will not be sent to Arize AX")
        return None
    
    if not ARIZE_SPACE_ID:
        print("⚠️  WARNING: ARIZE_SPACE_ID not set!")
        print("   Set environment variable: ARIZE_SPACE_ID=your-space-id")
        print("   Get from: https://app.arize.com (Space Settings)")
        print("   Tracing will not be sent to Arize AX")
        return None
    
    try:
        # Register Arize AX tracer with auto-instrumentation
        tracer_provider = register(
            space_id=ARIZE_SPACE_ID,
            api_key=ARIZE_API_KEY,
            project_name=PROJECT_NAME,
        )
        
        # Instrument Google ADK specifically
        GoogleADKInstrumentor().instrument(tracer_provider=tracer_provider)
        
        print(f"✅ Arize AX tracing initialized successfully!")
        print(f"   Space ID: {ARIZE_SPACE_ID}")
        print(f"   Project: {PROJECT_NAME}")
        print(f"   Auto-instrumentation: ENABLED")
        print(f"\n   Tracing will capture:")
        print(f"   - ADK agent executions")
        print(f"   - Tool function calls")
        print(f"   - Vertex AI Search queries")
        print(f"   - Agent workflow orchestration")
        print(f"\n   View traces at: https://app.arize.com")
        print("="*80 + "\n")
        
        return tracer_provider
    
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize Arize AX tracing: {e}")
        print("   System will continue without tracing")
        return None


# Arize AX is cloud-only, no local option needed
# All tracing goes to app.arize.com


# Optional: Add custom attributes to all traces
def add_custom_trace_attributes():
    """
    Add custom attributes to traces for better filtering and analysis.
    """
    from opentelemetry import trace
    
    # Get the current span
    span = trace.get_current_span()
    
    if span:
        # Add custom attributes
        span.set_attribute("environment", os.getenv("ENVIRONMENT", "development"))
        span.set_attribute("gcp_project", os.getenv("GOOGLE_CLOUD_PROJECT"))
        span.set_attribute("model", "gemini-2.5-flash")
        span.set_attribute("datastore", "insurance-filings-full")
