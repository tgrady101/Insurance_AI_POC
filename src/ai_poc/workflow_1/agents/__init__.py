"""
ADK-based Multi-Agent System for Competitive Intelligence

This package contains the Google ADK-based implementation of the competitive
intelligence report system with COMMERCIAL INSURANCE segment focus.
"""

from .root_agent import CompetitiveIntelligenceRootAgent, create_agent
from .tools import (
    FindLatestQuarterTool,
    ValidateDataTool,
    FinancialMetricsTool,
    CompetitivePositioningTool,
    StrategicInitiativesTool,
    RiskOutlookTool
)
from .financial_metrics_agent import FinancialMetricsAgent
from .competitive_positioning_agent import CompetitivePositioningAgent
from .strategic_initiatives_agent import StrategicInitiativesAgent
from .risk_outlook_agent import RiskOutlookAgent

__all__ = [
    'CompetitiveIntelligenceRootAgent',
    'create_agent',
    'FindLatestQuarterTool',
    'ValidateDataTool',
    'FinancialMetricsTool',
    'CompetitivePositioningTool',
    'StrategicInitiativesTool',
    'RiskOutlookTool',
    'FinancialMetricsAgent',
    'CompetitivePositioningAgent',
    'StrategicInitiativesAgent',
    'RiskOutlookAgent'
]
