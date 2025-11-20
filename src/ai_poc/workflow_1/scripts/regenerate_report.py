"""
Regenerate Q3 2025 competitive intelligence report with Arize observability.
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST before importing any modules that need them
# Script is at: src/ai_poc/workflow_1/scripts/regenerate_report.py
# .env is at: .env (project root)
# Need to go up 4 levels: scripts -> workflow_1 -> ai_poc -> src -> root
env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# NOW import the agent (after env vars are loaded)
from src.ai_poc.workflow_1.agents.root_agent import CompetitiveIntelligenceRootAgent

async def main():
    print("=" * 80)
    print("REGENERATING Q3 2025 COMPETITIVE INTELLIGENCE REPORT")
    print("=" * 80)
    
    # Check Arize configuration
    arize_space_id = os.getenv("ARIZE_SPACE_ID")
    arize_api_key = os.getenv("ARIZE_API_KEY")
    
    if arize_space_id and arize_api_key:
        print("\n✅ Arize observability ENABLED")
        print(f"   Space ID: {arize_space_id}")
        print("   Traces will be logged to Arize Phoenix")
    else:
        print("\n⚠️  Arize observability NOT configured")
        print("   Set ARIZE_SPACE_ID and ARIZE_API_KEY environment variables to enable")
    
    print("\nAll agents now have Vertex AI authentication configured.")
    print("This report should complete successfully with all sections populated.\n")
    
    # Create root agent (will automatically enable Arize if env vars are set)
    root_agent = CompetitiveIntelligenceRootAgent()
    
    # Generate report for Q3 2025
    print("Generating report for Q3 2025...")
    print("This will take several minutes as all agents process data...\n")
    
    report_data = await root_agent.generate_report(year=2025, quarter=3)
    
    print("\n" + "=" * 80)
    print("REPORT GENERATION COMPLETE")
    print("=" * 80)
    
    # Check report data structure
    if report_data.get("report_markdown"):
        report_length = len(report_data["report_markdown"])
        print(f"\n✅ Report Generated: {report_length:,} characters")
        
        # Check if key sections are in the markdown
        report_text = report_data["report_markdown"]
        sections_found = []
        
        if "Risk Assessment" in report_text or "Risk and Outlook" in report_text:
            sections_found.append("Risk Assessment")
        if "Financial" in report_text or "Combined Ratio" in report_text:
            sections_found.append("Financial Metrics")
        if "Competitive Position" in report_text or "Market Position" in report_text:
            sections_found.append("Competitive Positioning")
        if "Strategic Initiative" in report_text or "Strategy" in report_text:
            sections_found.append("Strategic Initiatives")
        
        print(f"✅ Sections Found: {', '.join(sections_found)}")
        
        # Tool usage summary
        tool_count = len(report_data.get("tool_calls", []))
        print(f"✅ Tools Used: {tool_count} total calls")
        
        # Grounding metadata
        grounding = report_data.get("grounding_metadata", {})
        chunks = grounding.get("chunks_used", 0)
        print(f"✅ Grounding: {chunks} document chunks used")
        
        # Arize trace info
        if arize_space_id and arize_api_key:
            print(f"\n📊 Arize Trace: View execution details in Arize Phoenix dashboard")
            print(f"   URL: https://app.arize.com/organizations/{arize_space_id}/projects")
    else:
        print("\n❌ Report Generation: FAILED - No markdown content")
    
    # Show file location
    filename = f"generated_reports/ci_report_Q{report_data.get('quarter', '?')}_{report_data.get('year', '????')}.md"
    print(f"\n📄 Report saved to: {filename}")

if __name__ == "__main__":
    asyncio.run(main())
