"""Turn DocuSign SDK errors into tool errors an MCP client can read.

Why this module exists: the SDK's ApiException.__str__ reads trace_token and
timestamp, which the SDK sets only when it builds the exception from an HTTP
response. The SDK also raises ApiException(status=0, reason=...) itself, for
example on an SSL error, and str() of that raises AttributeError. FastMCP
builds the tool error text with str(), so such a failure reached the MCP
client as a bare JSON-RPC "Internal server error" (issue #3). Each tool is
wrapped with translate_api_errors, so every DocuSign failure becomes a
ToolError whose text is built here, without calling ApiException.__str__.
"""

import functools
import json
from collections.abc import Callable
from typing import Any, TypeVar

from docusign_esign.client.api_exception import ApiException
from fastmcp.exceptions import ToolError

F = TypeVar("F", bound=Callable[..., Any])

# DocuSign error bodies are short JSON objects. Cap the raw text kept for a
# body that is not JSON, so an HTML error page does not flood the client.
_MAX_RAW_BODY = 500


def body_detail(body: Any) -> str | None:
    """Return DocuSign's own error code and text from a response body.

    OAuth errors use {"error", "error_description"}; eSignature REST errors
    use {"errorCode", "message"}.
    """
    if not body:
        return None
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    try:
        data = json.loads(text)
    except ValueError:
        return text.strip()[:_MAX_RAW_BODY] or None
    if not isinstance(data, dict):
        return text.strip()[:_MAX_RAW_BODY] or None
    code = data.get("error") or data.get("errorCode")
    desc = data.get("error_description") or data.get("message")
    parts = [str(p) for p in (code, desc) if p]
    return ": ".join(parts) or None


def describe_api_error(err: ApiException) -> str:
    """Build a one-line description of an ApiException without its __str__."""
    status = getattr(err, "status", None)
    reason = getattr(err, "reason", None)
    detail = body_detail(getattr(err, "body", None))
    head = f"DocuSign API error ({status})" if status else "DocuSign API error"
    parts = [str(p) for p in (reason, detail) if p]
    return f"{head}: {' - '.join(parts)}" if parts else head


def translate_api_errors(func: F) -> F:
    """Re-raise any ApiException from a tool as a ToolError with a readable message.

    functools.wraps keeps the signature, so FastMCP still builds the tool's
    input schema from the wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            # DocuSignAuthError (docusign_client.py) already has a full message.
            message = e.message if hasattr(e, "message") else describe_api_error(e)
            raise ToolError(message) from e

    return wrapper  # type: ignore[return-value]
