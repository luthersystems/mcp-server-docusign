"""Tests for the errors DocuSignClient raises when authentication fails.

The server's tools surface these errors to the MCP client as the tool error
text. If str() of the error fails, FastMCP cannot build that text and the
client gets only a JSON-RPC "Internal server error" (found in the issue #3
smoke test after the fastmcp 4.2 upgrade).
"""

from unittest.mock import Mock, patch

import pytest
from docusign_esign.client.api_exception import ApiException
from fastmcp import Client, FastMCP

from mcp_server_docusign.config import DocuSignConfig
from mcp_server_docusign.docusign_client import DocuSignClient
from mcp_server_docusign.tools.templates import register_template_tools


def _http_error(status: int, reason: str, body: bytes) -> ApiException:
    """Build an ApiException as the SDK does for an HTTP error response."""
    resp = Mock()
    resp.status = status
    resp.reason = reason
    resp.data = body
    resp.getheaders.return_value = {}
    resp.getheader.return_value = None
    return ApiException(http_resp=resp)


@pytest.fixture
def client(tmp_path):
    key = tmp_path / "private.key"
    key.write_bytes(b"not used: the token request is mocked")
    config = DocuSignConfig(
        integration_key="ik", user_id="uid", private_key_path=key, _env_file=None
    )
    return DocuSignClient(config)


def test_jwt_failure_error_has_readable_message(client):
    err = _http_error(400, "Bad Request", b'{"error":"consent_required"}')
    with patch("mcp_server_docusign.docusign_client.ApiClient") as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.side_effect = err
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    message = str(exc_info.value)
    assert "Failed to obtain JWT token: Bad Request" in message
    assert "admin consent" in message
    assert exc_info.value.status == 400
    assert exc_info.value.__cause__ is err


def test_discovery_failure_error_has_readable_message(client):
    err = _http_error(401, "Unauthorized", b"")
    with patch("mcp_server_docusign.docusign_client.ApiClient") as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.side_effect = err
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    assert "Failed to discover base URI: Unauthorized" in str(exc_info.value)
    assert exc_info.value.status == 401


def test_no_accounts_error_has_readable_message(client):
    with patch("mcp_server_docusign.docusign_client.ApiClient") as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.return_value = Mock(accounts=[])
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    assert "No accounts found for user" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_returns_auth_error_to_mcp_client(client):
    """An auth failure reaches the MCP client as a tool error, not an internal error."""
    mcp = FastMCP("test")
    register_template_tools(mcp, client)
    err = _http_error(400, "Bad Request", b'{"error":"consent_required"}')
    with patch("mcp_server_docusign.docusign_client.ApiClient") as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.side_effect = err
        async with Client(mcp) as mcp_client:
            result = await mcp_client.call_tool("list_templates", {}, raise_on_error=False)

    assert result.is_error
    assert "admin consent" in result.content[0].text
