"""
Pytest configuration and shared fixtures for all tests.

This file is automatically loaded by pytest and provides:
- Session-level Arize AX tracing setup
- Environment configuration
- Shared fixtures
- Custom pytest hooks
"""

import pytest
import sys
import os
import logging
import warnings
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in project root (parent of tests directory)
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded environment variables from {env_path}")
    else:
        print(f"[WARNING] .env file not found at {env_path}")
except ImportError:
    print("[WARNING] python-dotenv not installed, environment variables must be set manually")

# Suppress verbose warnings
logging.getLogger("google.genai").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*non-text parts in the response.*")

# Configure Vertex AI environment
os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv(
    "GOOGLE_CLOUD_PROJECT", 
    "project-4b3d3288-7603-4755-899"
)
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv(
    "GOOGLE_CLOUD_LOCATION",
    "global"
)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================================
# Session-level Fixtures
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_arize_tracing():
    """
    Initialize Arize AX tracing for the entire test session.
    
    This fixture runs automatically before any tests execute.
    Tracing is enabled if ARIZE_SPACE_ID and ARIZE_API_KEY are set.
    
    Returns:
        dict: {"enabled": bool, "tracer": TracerProvider or None}
    """
    print("\n" + "="*80)
    print("PYTEST TEST SESSION STARTING")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"GCP Project: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
    print(f"GCP Location: {os.getenv('GOOGLE_CLOUD_LOCATION')}")
    
    # Try to set up Arize tracing
    try:
        from ai_poc.workflow_1.arize_tracing.arize_config import setup_arize_tracing
        
        space_id = os.getenv("ARIZE_SPACE_ID")
        api_key = os.getenv("ARIZE_API_KEY")
        
        if space_id and api_key:
            print("\n[INFO] Setting up Arize AX tracing...")
            tracer = setup_arize_tracing()
            print("[OK] Arize AX tracing ENABLED for test session")
            print("   View traces at: https://app.arize.com")
            print("   Project: insurance-competitive-intelligence")
            result = {"enabled": True, "tracer": tracer}
        else:
            print("\n[WARNING] Arize AX credentials not set - tracing DISABLED")
            print("   Set ARIZE_SPACE_ID and ARIZE_API_KEY to enable")
            result = {"enabled": False, "tracer": None}
    
    except ImportError as e:
        print(f"\n[WARNING] Arize tracing not available: {e}")
        result = {"enabled": False, "tracer": None}
    
    except Exception as e:
        print(f"\n[WARNING] Arize tracing setup failed: {e}")
        result = {"enabled": False, "tracer": None}
    
    print("="*80 + "\n")
    
    # Yield to run tests
    yield result
    
    # Teardown
    print("\n" + "="*80)
    print("PYTEST TEST SESSION COMPLETE")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if result["enabled"]:
        print("[OK] Traces sent to Arize AX")
        print("   View at: https://app.arize.com")
    print("="*80 + "\n")


@pytest.fixture(scope="session")
def test_config():
    """
    Provide test configuration dictionary.
    
    Returns:
        dict: Test configuration including project settings, timeouts, etc.
    """
    return {
        "gcp_project": os.getenv("GOOGLE_CLOUD_PROJECT"),
        "gcp_location": os.getenv("GOOGLE_CLOUD_LOCATION"),
        "timeout_default": 300,  # 5 minutes
        "timeout_integration": 600,  # 10 minutes
        "timeout_tool": 120,  # 2 minutes
        "expected_companies": 7,
        "expected_tools": 6,
    }


# ============================================================================
# Pytest Hooks
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers and configure tests.
    
    This hook runs after test collection and can modify test items.
    """
    # Add asyncio marker to all async tests automatically
    for item in items:
        if "asyncio" in item.keywords:
            item.add_marker(pytest.mark.asyncio)


def pytest_configure(config):
    """
    Configure pytest with custom settings.
    
    This runs before test collection.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", 
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", 
        "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", 
        "tracing: marks tests related to Arize AX tracing"
    )


def pytest_runtest_setup(item):
    """
    Hook called before each test runs.
    
    Can be used to skip tests based on conditions.
    """
    # Skip integration tests if environment variable is set
    if "integration" in item.keywords and os.getenv("SKIP_INTEGRATION"):
        pytest.skip("Skipping integration tests (SKIP_INTEGRATION=1)")
    
    # Skip tracing tests if Arize not configured
    if "tracing" in item.keywords:
        if not (os.getenv("ARIZE_SPACE_ID") and os.getenv("ARIZE_API_KEY")):
            pytest.skip("Skipping tracing test (Arize credentials not set)")


def pytest_runtest_makereport(item, call):
    """
    Hook called after each test phase (setup, call, teardown).
    
    Can be used to add custom reporting or logging.
    """
    # Add custom reporting here if needed
    pass


# ============================================================================
# Test Utilities
# ============================================================================

def skip_if_no_credentials():
    """
    Decorator to skip tests if GCP credentials are not available.
    
    Usage:
        @skip_if_no_credentials()
        def test_requires_gcp():
            ...
    """
    def decorator(func):
        return pytest.mark.skipif(
            not os.getenv("GOOGLE_CLOUD_PROJECT"),
            reason="GCP credentials not configured"
        )(func)
    return decorator


def skip_if_no_arize():
    """
    Decorator to skip tests if Arize credentials are not available.
    
    Usage:
        @skip_if_no_arize()
        def test_requires_arize():
            ...
    """
    def decorator(func):
        return pytest.mark.skipif(
            not (os.getenv("ARIZE_SPACE_ID") and os.getenv("ARIZE_API_KEY")),
            reason="Arize credentials not configured"
        )(func)
    return decorator
