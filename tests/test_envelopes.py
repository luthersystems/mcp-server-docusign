"""Tests for envelope tools."""

from unittest.mock import Mock, patch

import pytest

from mcp_server_docusign.docusign_client import DocuSignClient
from mcp_server_docusign.tools.envelopes import register_envelope_tools


class MockEnvelopeResult:
    """Mock envelope result."""

    def __init__(self, envelope_id="env123", status="sent"):
        self.envelope_id = envelope_id
        self.status = status
        self.status_date_time = "2024-01-01T10:00:00Z"


class MockEnvelope:
    """Mock envelope object."""

    def __init__(self):
        self.envelope_id = "env123"
        self.status = "sent"
        self.email_subject = "Test Subject"
        self.email_blurb = "Test Blurb"
        self.created_date_time = "2024-01-01T09:00:00Z"
        self.sent_date_time = "2024-01-01T10:00:00Z"
        self.delivered_date_time = None
        self.signed_date_time = None
        self.completed_date_time = None
        self.declined_date_time = None
        self.voided_date_time = None


class MockEnvelopesListResult:
    """Mock envelopes list result."""

    def __init__(self):
        self.result_set_size = "1"
        self.total_set_size = "1"
        self.envelopes = [MockEnvelope()]


@pytest.fixture
def mock_ds_client():
    """Create a mock DocuSign client."""
    client = Mock(spec=DocuSignClient)
    client.get_account_id.return_value = "acct-123"
    client.get_api_client.return_value = Mock()
    return client


@pytest.fixture
def mock_mcp():
    """Create a mock FastMCP instance."""
    mcp = Mock()
    # Store registered functions
    registered_funcs = {}

    def tool_decorator():
        def wrapper(func):
            registered_funcs[func.__name__] = func
            return func

        return wrapper

    mcp.tool = tool_decorator
    mcp._registered_funcs = registered_funcs
    return mcp


def test_create_envelope_from_template(mock_mcp, mock_ds_client):
    """Test creating an envelope from a template."""
    with patch("mcp_server_docusign.tools.envelopes.EnvelopesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.create_envelope.return_value = MockEnvelopeResult()
        mock_api_class.return_value = mock_api

        # Register tools
        register_envelope_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["create_envelope_from_template"]

        # Call it
        result = func(
            template_id="tmpl-123",
            email_subject="Please sign",
            role_assignments=[
                {"roleName": "Signer1", "name": "John Doe", "email": "john@example.com"}
            ],
            status="sent",
        )

        # Verify result
        assert result["envelopeId"] == "env123"
        assert result["status"] == "sent"

        # Verify API was called correctly
        mock_api.create_envelope.assert_called_once()
        call_args = mock_api.create_envelope.call_args
        assert call_args[0][0] == "acct-123"  # account_id


def test_get_envelope_status(mock_mcp, mock_ds_client):
    """Test getting envelope status."""
    with patch("mcp_server_docusign.tools.envelopes.EnvelopesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.get_envelope.return_value = MockEnvelope()
        mock_api_class.return_value = mock_api

        # Register tools
        register_envelope_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["get_envelope_status"]

        # Call it
        result = func(envelope_id="env123")

        # Verify result
        assert result["envelopeId"] == "env123"
        assert result["status"] == "sent"
        assert result["emailSubject"] == "Test Subject"

        # Verify API was called
        mock_api.get_envelope.assert_called_once_with("acct-123", "env123")


def test_list_envelopes(mock_mcp, mock_ds_client):
    """Test listing envelopes."""
    with patch("mcp_server_docusign.tools.envelopes.EnvelopesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.list_status_changes.return_value = MockEnvelopesListResult()
        mock_api_class.return_value = mock_api

        # Register tools
        register_envelope_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["list_envelopes"]

        # Call it
        result = func(status="sent")

        # Verify result
        assert len(result["envelopes"]) == 1
        assert result["envelopes"][0]["envelopeId"] == "env123"
        assert result["resultSetSize"] == "1"

        # Verify API was called
        mock_api.list_status_changes.assert_called_once()
