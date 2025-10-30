"""Tests for document tools."""

import base64
from unittest.mock import Mock, patch

import pytest

from mcp_server_docusign.docusign_client import DocuSignClient
from mcp_server_docusign.tools.documents import register_document_tools


class MockDocument:
    """Mock document object."""

    def __init__(self):
        self.document_id = "1"
        self.name = "contract.pdf"
        self.type = "content"
        self.uri = "/documents/1"
        self.order = "1"
        self.pages = "5"


class MockDocumentsListResult:
    """Mock documents list result."""

    def __init__(self):
        self.envelope_documents = [MockDocument()]


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
    registered_funcs = {}

    def tool_decorator():
        def wrapper(func):
            registered_funcs[func.__name__] = func
            return func

        return wrapper

    mcp.tool = tool_decorator
    mcp._registered_funcs = registered_funcs
    return mcp


def test_list_envelope_documents(mock_mcp, mock_ds_client):
    """Test listing envelope documents."""
    with patch("mcp_server_docusign.tools.documents.EnvelopesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.list_documents.return_value = MockDocumentsListResult()
        mock_api_class.return_value = mock_api

        # Register tools
        register_document_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["list_envelope_documents"]

        # Call it
        result = func(envelope_id="env123")

        # Verify result
        assert result["envelopeId"] == "env123"
        assert len(result["documents"]) == 1
        assert result["documents"][0]["documentId"] == "1"
        assert result["documents"][0]["name"] == "contract.pdf"

        # Verify API was called
        mock_api.list_documents.assert_called_once_with("acct-123", "env123")


def test_download_envelope_document(mock_mcp, mock_ds_client):
    """Test downloading an envelope document."""
    test_content = b"PDF content here"

    with patch("mcp_server_docusign.tools.documents.EnvelopesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.get_document.return_value = test_content
        mock_api_class.return_value = mock_api

        # Register tools
        register_document_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["download_envelope_document"]

        # Call it
        result = func(envelope_id="env123", document_id="1")

        # Verify result
        assert result["envelopeId"] == "env123"
        assert result["documentId"] == "1"
        assert result["sizeBytes"] == len(test_content)

        # Verify base64 encoding
        decoded = base64.b64decode(result["contentBase64"])
        assert decoded == test_content

        # Verify API was called
        mock_api.get_document.assert_called_once_with("acct-123", "1", "env123")

