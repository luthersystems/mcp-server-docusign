"""DocuSign API client with JWT authentication."""

import base64
import time
from urllib.parse import urlsplit

from docusign_esign import ApiClient
from docusign_esign.client.api_exception import ApiException

from .config import DocuSignConfig
from .errors import DocuSignAuthError, body_detail, describe_api_error

__all__ = ["DocuSignAuthError", "DocuSignClient"]


class DocuSignClient:
    """DocuSign API client with JWT server-to-server authentication."""

    def __init__(self, config: DocuSignConfig | None = None):
        """Initialize the DocuSign client.

        Args:
            config: DocuSign configuration. If None, loads from environment.
        """
        self.config = config or DocuSignConfig.from_env()
        self._api_client: ApiClient | None = None
        self._token: str | None = None
        self._token_expiry: float = 0

    def _read_private_key(self) -> bytes:
        """Read the RSA private key from file or base64-encoded environment variable.

        Returns:
            Private key bytes.

        Raises:
            FileNotFoundError: If private key file doesn't exist.
            ValueError: If base64 decoding fails.
        """
        if self.config.private_key:
            # Decode base64-encoded private key from environment variable
            try:
                return base64.b64decode(self.config.private_key)
            except Exception as e:
                raise ValueError(f"Failed to decode base64 private key: {e}") from e
        elif self.config.private_key_path:
            # Read private key from file
            with open(self.config.private_key_path, "rb") as f:
                return f.read()
        else:
            raise ValueError("No private key configured (DS_PRIVATE_KEY or DS_PRIVATE_KEY_PATH)")

    def _oauth_host(self) -> str:
        """Return the OAuth host name from DS_AUTH_BASE, without scheme or path.

        It is both the JWT audience and the userinfo host, so a path in
        DS_AUTH_BASE must not leak into it.
        """
        base = self.config.auth_base.strip()
        return urlsplit(base if "://" in base else f"https://{base}").netloc

    def _get_jwt_token(self) -> str:
        """Obtain a JWT access token from DocuSign.

        Returns:
            Access token string.

        Raises:
            DocuSignAuthError: If the token request fails.
        """
        # Create temporary API client for token request
        api_client = ApiClient()
        api_client.set_base_path(self.config.auth_base)

        try:
            private_key = self._read_private_key()
            response = api_client.request_jwt_user_token(
                client_id=self.config.integration_key,
                user_id=self.config.user_id,
                oauth_host_name=self._oauth_host(),
                private_key_bytes=private_key,
                expires_in=self.config.token_exp_secs,
                scopes=self.config.oauth_scope.split(),
            )
            return response.access_token
        except ApiException as e:
            # The OAuth body names the real cause (bad key, unknown user,
            # missing consent). Give the consent hint only for that cause, so
            # a wrong key does not send the operator to the consent page.
            message = f"Failed to obtain JWT token: {describe_api_error(e)}"
            if "consent_required" in (body_detail(e.body) or ""):
                message += ". Grant admin consent for the integration key"
            raise DocuSignAuthError(message, status=e.status) from e
        except Exception as e:
            # Everything else here is a setup or network fault: a missing or
            # malformed key (OSError, ValueError, PyJWT errors) or an
            # unreachable DS_AUTH_BASE (urllib3 errors the SDK passes through).
            # Name it as an auth failure so the operator knows where to look.
            raise DocuSignAuthError(
                f"Failed to obtain JWT token: {type(e).__name__}: {' '.join(str(e).split())}"
            ) from e

    def _discover_base_uri_and_account(self, token: str) -> tuple[str, str]:
        """Discover the base URI and default account ID for the user.

        Args:
            token: Access token from _get_jwt_token.

        Returns:
            Tuple of (base_uri, account_id).

        Raises:
            DocuSignAuthError: If the userinfo request fails or finds no account.
        """
        # get_user_info calls the SDK client's oauth_host_name, not its base
        # path. ApiClient() sets that host to the demo server, and
        # set_base_path does not change it, so set it from DS_AUTH_BASE or a
        # production token is sent to the demo userinfo endpoint (401).
        api_client = ApiClient(oauth_host_name=self._oauth_host())
        api_client.set_default_header("Authorization", f"Bearer {token}")

        try:
            user_info = api_client.get_user_info(token)
        except ApiException as e:
            raise DocuSignAuthError(
                f"Failed to discover base URI: {describe_api_error(e)}", status=e.status
            ) from e

        accounts = user_info.accounts or []
        if not accounts:
            raise DocuSignAuthError("No accounts found for user")

        # A user can belong to several accounts; use the one DocuSign marks as
        # the default (is_default is the string "true"), not the first listed.
        account = next((a for a in accounts if str(a.is_default).lower() == "true"), accounts[0])
        return account.base_uri + "/restapi", account.account_id

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid token and API client configured.

        The token and client are stored only after every step succeeds. If
        discovery failed after the token was stored, later calls would skip
        authentication and use a None client and account ID.
        """
        current_time = time.time()

        # Check if token is expired or will expire soon (5 min buffer)
        if not self._token or current_time >= (self._token_expiry - 300):
            token = self._get_jwt_token()

            # Discover base URI and account if not cached
            if not self.config.base_uri or not self.config.account_id:
                base_uri, account_id = self._discover_base_uri_and_account(token)
                self.config.set_runtime_info(base_uri, account_id)

            # Create new API client with discovered base URI
            api_client = ApiClient()
            api_client.host = (
                self.config.base_uri
            )  # Must set host directly, not via set_base_path()
            api_client.set_default_header("Authorization", f"Bearer {token}")

            self._api_client = api_client
            self._token = token
            self._token_expiry = current_time + self.config.token_exp_secs

    def get_api_client(self) -> ApiClient:
        """Get an authenticated API client.

        Returns:
            Configured ApiClient instance.
        """
        self._ensure_authenticated()
        return self._api_client

    def get_account_id(self) -> str:
        """Get the default account ID.

        Returns:
            Account ID string.
        """
        self._ensure_authenticated()
        return self.config.account_id
