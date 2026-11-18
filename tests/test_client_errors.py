"""Tests for DocuSign errors as the MCP client sees them, and auth state.

The server's tools surface these errors to the MCP client as the tool error
text. If str() of the error fails, FastMCP cannot build that text and the
client gets only a JSON-RPC "Internal server error" (found in the issue #3
smoke test after the fastmcp 4.2 upgrade).
"""

import os
from unittest.mock import Mock, patch

import pytest
from docusign_esign.client.api_exception import ApiException
from fastmcp import Client, FastMCP

from mcp_server_docusign.config import DocuSignConfig
from mcp_server_docusign.docusign_client import DocuSignClient
from mcp_server_docusign.errors import describe_api_error
from mcp_server_docusign.tools.templates import register_template_tools

PATCH_API_CLIENT = "mcp_server_docusign.docusign_client.ApiClient"


def _http_error(status: int, reason: str, body: bytes) -> ApiException:
    """Build an ApiException as the SDK does for an HTTP error response."""
    resp = Mock()
    resp.status = status
    resp.reason = reason
    resp.data = body
    resp.getheaders.return_value = {}
    resp.getheader.return_value = None
    return ApiException(http_resp=resp)


def _account(account_id: str, is_default: str) -> Mock:
    return Mock(account_id=account_id, is_default=is_default, base_uri=f"https://{account_id}")


@pytest.fixture(autouse=True)
def _no_ds_env(monkeypatch):
    """Keep DS_* variables from the developer's or CI's shell out of the config."""
    for name in list(os.environ):
        if name.upper().startswith("DS_"):
            monkeypatch.delenv(name)


def _make_client(tmp_path, **overrides) -> DocuSignClient:
    key = tmp_path / "private.key"
    key.write_bytes(b"not used: the token request is mocked")
    config = DocuSignConfig(
        integration_key="ik", user_id="uid", private_key_path=key, _env_file=None, **overrides
    )
    return DocuSignClient(config)


@pytest.fixture
def client(tmp_path):
    return _make_client(tmp_path)


def test_jwt_consent_error_has_readable_message(client):
    err = _http_error(400, "Bad Request", b'{"error":"consent_required"}')
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.side_effect = err
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    message = str(exc_info.value)
    assert "Failed to obtain JWT token: consent_required." in message
    assert "admin consent" in message
    assert exc_info.value.status == 400
    assert exc_info.value.__cause__ is err


def test_jwt_bad_key_error_names_cause_without_consent_hint(client):
    err = _http_error(400, "Bad Request", b'{"error":"no_valid_keys_or_signatures"}')
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.side_effect = err
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    message = str(exc_info.value)
    assert "no_valid_keys_or_signatures" in message
    assert "consent" not in message


def test_discovery_failure_error_has_readable_message(client):
    err = _http_error(401, "Unauthorized", b"")
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.side_effect = err
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    assert "Failed to discover base URI: Unauthorized" in str(exc_info.value)
    assert exc_info.value.status == 401


def test_discovery_failure_is_raised_again_on_next_call(client):
    """A failed discovery must not leave a cached token with no API client."""
    err = _http_error(401, "Unauthorized", b"")
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.side_effect = err
        for _ in range(2):
            with pytest.raises(ApiException, match="Failed to discover base URI"):
                client.get_api_client()
            with pytest.raises(ApiException, match="Failed to discover base URI"):
                client.get_account_id()


def test_no_accounts_error_has_readable_message(client):
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.return_value = Mock(accounts=[])
        with pytest.raises(ApiException) as exc_info:
            client.get_api_client()

    assert str(exc_info.value) == "No accounts found for user"


def test_discovery_uses_default_account(client):
    accounts = [_account("first", "false"), _account("default", "true")]
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.return_value = Mock(accounts=accounts)
        assert client.get_account_id() == "default"
    assert client.config.base_uri == "https://default/restapi"


def test_discovery_uses_configured_oauth_host(tmp_path):
    """With a production DS_AUTH_BASE, userinfo must go to the production host."""
    client = _make_client(tmp_path, auth_base="https://account.docusign.com")
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.return_value = Mock(access_token="tok")
        api_client_cls.return_value.get_user_info.return_value = Mock(
            accounts=[_account("a", "true")]
        )
        client.get_api_client()

    jwt_kwargs = api_client_cls.return_value.request_jwt_user_token.call_args.kwargs
    assert jwt_kwargs["oauth_host_name"] == "account.docusign.com"
    assert any(
        c.kwargs.get("oauth_host_name") == "account.docusign.com"
        for c in api_client_cls.call_args_list
    )


def test_describe_api_error_handles_sdk_errors_without_response():
    # The SDK raises these itself (for example on an SSL error); str() of
    # them raises AttributeError, so the description must not use it.
    assert describe_api_error(ApiException(status=0, reason="ssl failure")) == (
        "DocuSign API error: ssl failure"
    )
    err = _http_error(404, "Not Found", b'{"errorCode":"TEMPLATE_ID_INVALID","message":"bad"}')
    assert describe_api_error(err) == (
        "DocuSign API error (404): Not Found - TEMPLATE_ID_INVALID: bad"
    )


async def _call_list_templates(ds_client) -> object:
    mcp = FastMCP("test")
    register_template_tools(mcp, ds_client)
    async with Client(mcp) as mcp_client:
        return await mcp_client.call_tool("list_templates", {}, raise_on_error=False)


@pytest.mark.asyncio
async def test_tool_returns_auth_error_to_mcp_client(client):
    """An auth failure reaches the MCP client as a tool error, not an internal error."""
    err = _http_error(400, "Bad Request", b'{"error":"consent_required"}')
    with patch(PATCH_API_CLIENT) as api_client_cls:
        api_client_cls.return_value.request_jwt_user_token.side_effect = err
        result = await _call_list_templates(client)

    assert result.is_error
    assert "admin consent" in result.content[0].text


@pytest.mark.asyncio
async def test_tool_returns_sdk_error_without_response_to_mcp_client():
    """An SDK error with no HTTP response also reaches the client as a tool error."""
    ds_client = Mock(spec=DocuSignClient)
    ds_client.get_account_id.return_value = "acct"
    ds_client.get_api_client.return_value = Mock()
    with patch("mcp_server_docusign.tools.templates.TemplatesApi") as templates_api:
        templates_api.return_value.list_templates.side_effect = ApiException(
            status=0, reason="ssl failure"
        )
        result = await _call_list_templates(ds_client)

    assert result.is_error
    assert result.content[0].text == "DocuSign API error: ssl failure"
