"""Integration tests for DocuSign authentication (requires real credentials).

These tests are SKIPPED by default unless you:
1. Create a .env file in the project root with real DocuSign credentials
2. Run pytest with: pytest tests/test_integration.py

To set up:
1. Copy .env.example to .env
2. Fill in your DocuSign credentials
3. Run: pytest tests/test_integration.py -v
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from mcp_server_docusign.config import DocuSignConfig
from mcp_server_docusign.docusign_client import DocuSignClient

# Load .env file if it exists
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path)

# Check if integration tests should run
# Require either DS_PRIVATE_KEY or DS_PRIVATE_KEY_PATH
INTEGRATION_TESTS_ENABLED = all(
    [
        os.getenv("DS_INTEGRATION_KEY"),
        os.getenv("DS_USER_ID"),
        os.getenv("DS_PRIVATE_KEY") or os.getenv("DS_PRIVATE_KEY_PATH"),
    ]
)

pytestmark = pytest.mark.skipif(
    not INTEGRATION_TESTS_ENABLED,
    reason="Integration tests disabled. Create .env file with credentials to enable.",
)


@pytest.fixture(scope="module")
def ds_client():
    """Create a DocuSign client with real credentials from environment."""
    config = DocuSignConfig.from_env()
    client = DocuSignClient(config)
    return client


def test_jwt_authentication(ds_client):
    """Test that JWT authentication works and can obtain a valid token."""
    # This will trigger authentication
    api_client = ds_client.get_api_client()

    assert api_client is not None
    assert ds_client._token is not None
    assert len(ds_client._token) > 0
    print("✓ Successfully obtained JWT token")


def test_get_account_id(ds_client):
    """Test that we can retrieve the account ID."""
    account_id = ds_client.get_account_id()

    assert account_id is not None
    assert len(account_id) > 0
    print(f"✓ Successfully retrieved account ID: {account_id}")


def test_base_uri_discovery(ds_client):
    """Test that base URI is discovered correctly."""
    # Trigger authentication which discovers base URI
    ds_client.get_api_client()

    base_uri = ds_client.config.base_uri
    assert base_uri is not None
    assert "docusign" in base_uri.lower() or "restapi" in base_uri.lower()
    print(f"✓ Successfully discovered base URI: {base_uri}")


def test_list_templates(ds_client):
    """Test that we can list templates (verifies full API connectivity)."""
    from docusign_esign import ApiException, TemplatesApi

    api_client = ds_client.get_api_client()
    account_id = ds_client.get_account_id()

    templates_api = TemplatesApi(api_client)
    try:
        result = templates_api.list_templates(account_id)

        assert result is not None
        # Note: result might have 0 templates, which is okay
        print("✓ Successfully called list_templates API")
        if result.envelope_templates:
            print(f"  Found {len(result.envelope_templates)} templates")
        else:
            print("  No templates found (this is okay for testing)")
    except ApiException as e:
        if e.status == 401:
            print("⚠ Templates API returned 401 - account may not have template permissions")
            print("  This is okay for basic integration testing")
            pytest.skip("Templates API not accessible (401) - skipping test")
        else:
            raise


def test_token_refresh(ds_client):
    """Test that tokens can be refreshed."""
    # Get initial token
    ds_client.get_api_client()
    first_token = ds_client._token
    first_expiry = ds_client._token_expiry

    # Force token to be considered expired
    ds_client._token_expiry = 0

    # Get new token
    ds_client.get_api_client()
    second_token = ds_client._token

    # Tokens should be different (new token issued)
    assert second_token != first_token
    assert ds_client._token_expiry > first_expiry
    print("✓ Successfully refreshed JWT token")
