"""Turn DocuSign failures into tool errors an MCP client can read.

Why this module exists: the SDK's ApiException.__str__ reads trace_token and
timestamp, which the SDK sets only when it builds the exception from an HTTP
response. The SDK also raises ApiException(status=0, reason=...) itself, for
example on an SSL error, and str() of that raises AttributeError. FastMCP
builds the tool error text with str(), so such a failure reached the MCP
client as a bare JSON-RPC "Internal server error" (issue #3). Each tool is
wrapped with translate_api_errors, so a DocuSign failure becomes a ToolError
whose text is built here, without calling ApiException.__str__.
"""

import functools
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from docusign_esign.client.api_exception import ApiException, ArgumentException
from fastmcp.exceptions import ToolError
from urllib3.exceptions import HTTPError as Urllib3HTTPError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# DocuSign error bodies are short JSON objects. Cap the raw text kept for a
# body that is not JSON, so an HTML error page does not flood the client.
_MAX_RAW_BODY = 500


class DocuSignAuthError(ApiException):
    """An authentication or account discovery failure with a readable message.

    It keeps ApiException as its base, so callers that catch ApiException still
    catch it, and carries the HTTP status of the failure that caused it. Its
    own __str__ never reaches ApiException.__str__ (see the module docstring).
    """

    def __init__(self, message: str, status: int | None = None):
        super().__init__(status=status, reason=message)
        # ApiException does not pass the message to Exception.__init__; set
        # args so repr() shows it, and __reduce__ so pickling keeps it.
        self.args = (message,)
        self.message = message

    def __str__(self) -> str:
        return self.message

    def __reduce__(self) -> tuple[Any, ...]:
        return (type(self), (self.message, self.status))


def one_line(text: str) -> str:
    """Collapse whitespace, so a multi-line SDK reason stays on one line."""
    return " ".join(text.split())


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
        data = None
    if not isinstance(data, dict):
        return one_line(text)[:_MAX_RAW_BODY] or None
    code = data.get("error") or data.get("errorCode")
    desc = data.get("error_description") or data.get("message")
    parts = [str(p) for p in (code, desc) if p]
    return one_line(": ".join(parts)) or None


def describe_api_error(err: ApiException) -> str:
    """Build a one-line description of an ApiException without its __str__.

    It keeps DocuSign's trace token, which DocuSign support asks for.
    """
    status = getattr(err, "status", None)
    reason = getattr(err, "reason", None)
    detail = body_detail(getattr(err, "body", None))
    trace = getattr(err, "trace_token", None)
    head = f"DocuSign API error ({status})" if status else "DocuSign API error"
    parts = [one_line(str(p)) for p in (reason, detail) if p]
    text = f"{head}: {' - '.join(parts)}" if parts else head
    return f"{text} (trace token {trace})" if trace else text


def describe_connection_error(err: Exception) -> str:
    """Describe a urllib3 error by its host and cause, without the request URL.

    str() of a MaxRetryError holds the full URL, query string included
    (account ID, envelope IDs, search text). That text goes to the MCP client
    and the model, so keep only the host and the underlying error.
    """
    pool = getattr(err, "pool", None)
    host = getattr(pool, "host", None)
    cause = getattr(err, "reason", None) or err
    where = f" ({host})" if host else ""
    return f"Could not reach DocuSign{where}: {type(cause).__name__}"


# The DocuSign failures a tool turns into a ToolError. ArgumentException is
# what the SDK raises for a call it refuses before sending it.
DOCUSIGN_ERRORS = (ApiException, ArgumentException, Urllib3HTTPError)


def tool_error_message(err: Exception) -> str:
    """Return the tool error text for a DocuSign failure."""
    if isinstance(err, DocuSignAuthError):
        return err.message
    if isinstance(err, ApiException):
        return describe_api_error(err)
    if isinstance(err, Urllib3HTTPError):
        return describe_connection_error(err)
    return f"DocuSign SDK error: {type(err).__name__}: {one_line(str(err))}"


def translate_api_errors(func: F) -> F:
    """Re-raise a DocuSign failure from a tool as a ToolError with a readable message.

    It covers DOCUSIGN_ERRORS (the SDK passes urllib3 connection failures
    through unwrapped). FastMCP logs a ToolError without a traceback,
    so the traceback is logged here. functools.wraps keeps the signature, so
    FastMCP still builds the tool's input schema from the wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except DOCUSIGN_ERRORS as e:
            message = tool_error_message(e)
            logger.warning("DocuSign call in %s failed: %s", func.__name__, message, exc_info=True)
            raise ToolError(message) from e

    return wrapper  # type: ignore[return-value]
