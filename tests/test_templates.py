"""Tests for template tools."""

from unittest.mock import Mock, patch

import pytest

from mcp_server_docusign.docusign_client import DocuSignClient
from mcp_server_docusign.tools.templates import register_template_tools


class MockTemplate:
    """Mock template object."""

    def __init__(self):
        self.template_id = "tmpl-123"
        self.name = "Test Template"
        self.description = "A test template"
        self.shared = "false"
        self.created = "2024-01-01"
        self.last_modified = "2024-01-02"


class MockTemplateDetails(MockTemplate):
    """Mock template with details."""

    def __init__(self):
        super().__init__()
        self.email_subject = "Please sign"
        self.email_blurb = "Important document"
        self.recipients = Mock()
        self.recipients.signers = [
            Mock(
                role_name="Signer1",
                name="John Doe",
                recipient_id="1",
                routing_order="1",
            )
        ]
        self.documents = [
            Mock(document_id="1", name="doc.pdf", file_extension="pdf", order="1")
        ]


class MockTemplatesListResult:
    """Mock templates list result."""

    def __init__(self):
        self.result_set_size = "1"
        self.total_set_size = "1"
        self.envelope_templates = [MockTemplate()]


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


def test_list_templates(mock_mcp, mock_ds_client):
    """Test listing templates."""
    with patch("mcp_server_docusign.tools.templates.TemplatesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.list_templates.return_value = MockTemplatesListResult()
        mock_api_class.return_value = mock_api

        # Register tools
        register_template_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["list_templates"]

        # Call it
        result = func()

        # Verify result
        assert len(result["templates"]) == 1
        assert result["templates"][0]["templateId"] == "tmpl-123"
        assert result["templates"][0]["name"] == "Test Template"

        # Verify API was called
        mock_api.list_templates.assert_called_once_with("acct-123")


def test_get_template_definition(mock_mcp, mock_ds_client):
    """Test getting template definition."""
    with patch("mcp_server_docusign.tools.templates.TemplatesApi") as mock_api_class:
        mock_api = Mock()
        mock_api.get.return_value = MockTemplateDetails()
        mock_api_class.return_value = mock_api

        # Register tools
        register_template_tools(mock_mcp, mock_ds_client)

        # Get the registered function
        func = mock_mcp._registered_funcs["get_template_definition"]

        # Call it
        result = func(template_id="tmpl-123")

        # Verify result
        assert result["templateId"] == "tmpl-123"
        assert result["name"] == "Test Template"
        assert len(result["roles"]) == 1
        assert result["roles"][0]["roleName"] == "Signer1"
        assert len(result["documents"]) == 1

        # Verify API was called
        mock_api.get.assert_called_once_with("acct-123", "tmpl-123")

