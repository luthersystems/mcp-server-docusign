"""DocuSign API client with JWT authentication."""

import time
from typing import Optional

from docusign_esign import ApiClient
from docusign_esign.client.api_exception import ApiException

from .config import DocuSignConfig


class DocuSignClient:
    """DocuSign API client with JWT server-to-server authentication."""

    def __init__(self, config: Optional[DocuSignConfig] = None):
        """Initialize the DocuSign client.

        Args:
            config: DocuSign configuration. If None, loads from environment.
        """
        self.config = config or DocuSignConfig.from_env()
        self._api_client: Optional[ApiClient] = None
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    def _read_private_key(self) -> bytes:
        """Read the RSA private key from file.

        Returns:
            Private key bytes.

        Raises:
            FileNotFoundError: If private key file doesn't exist.
        """
        with open(self.config.private_key_path, "rb") as f:
            return f.read()

    def _get_jwt_token(self) -> str:
        """Obtain a JWT access token from DocuSign.

        Returns:
            Access token string.

        Raises:
            ApiException: If token request fails.
        """
        # Create temporary API client for token request
        api_client = ApiClient()
        api_client.set_base_path(self.config.auth_base)

        private_key = self._read_private_key()

        try:
            # Request JWT token
            response = api_client.request_jwt_user_token(
                client_id=self.config.integration_key,
                user_id=self.config.user_id,
                oauth_host_name=self.config.auth_base.replace("https://", "").replace(
                    "http://", ""
                ),
                private_key_bytes=private_key,
                expires_in=self.config.token_exp_secs,
                scopes=self.config.oauth_scope.split(),
            )
            return response.access_token
        except ApiException as e:
            raise ApiException(
                f"Failed to obtain JWT token: {e.reason}. "
                "Ensure admin consent is granted for the integration key."
            ) from e

    def _discover_base_uri_and_account(self) -> tuple[str, str]:
        """Discover the base URI and default account ID for the user.

        Returns:
            Tuple of (base_uri, account_id).

        Raises:
            ApiException: If userinfo request fails.
        """
        if not self._token:
            raise ValueError("Token must be obtained before discovering base URI")

        # Create temporary API client with token
        api_client = ApiClient()
        api_client.set_base_path(self.config.auth_base)
        api_client.set_default_header("Authorization", f"Bearer {self._token}")

        try:
            # Get user info
            user_info = api_client.get_user_info(self._token)

            # Get default account
            if not user_info.accounts:
                raise ApiException(reason="No accounts found for user")

            default_account = user_info.accounts[0]
            base_uri = default_account.base_uri + "/restapi"
            account_id = default_account.account_id

            return base_uri, account_id
        except ApiException as e:
            raise ApiException(f"Failed to discover base URI: {e.reason}") from e

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid token and API client configured."""
        current_time = time.time()

        # Check if token is expired or will expire soon (5 min buffer)
        if not self._token or current_time >= (self._token_expiry - 300):
            # Get new token
            self._token = self._get_jwt_token()
            self._token_expiry = current_time + self.config.token_exp_secs

            # Discover base URI and account if not cached
            if not self.config.base_uri or not self.config.account_id:
                base_uri, account_id = self._discover_base_uri_and_account()
                self.config.set_runtime_info(base_uri, account_id)

            # Create new API client with discovered base URI
            self._api_client = ApiClient()
            self._api_client.set_base_path(self.config.base_uri)
            self._api_client.set_default_header("Authorization", f"Bearer {self._token}")

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

