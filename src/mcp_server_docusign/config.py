"""Configuration management for DocuSign MCP Server."""

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class DocuSignConfig(BaseSettings):
    """DocuSign JWT authentication configuration."""

    auth_base: str = Field(
        default="https://account-d.docusign.com",
        description="DocuSign OAuth base URL (prod: https://account.docusign.com)",
    )
    integration_key: str = Field(..., description="DocuSign Integration Key (client_id)")
    user_id: str = Field(..., description="User GUID to impersonate")
    oauth_scope: str = Field(default="signature impersonation", description="OAuth scopes")
    private_key_path: Path | None = Field(default=None, description="Path to RSA private key (PEM)")
    private_key: str | None = Field(
        default=None, description="Base64-encoded RSA private key (alternative to private_key_path)"
    )
    token_exp_secs: int = Field(default=3600, description="Token expiration in seconds")

    @model_validator(mode="after")
    def validate_private_key(self) -> "DocuSignConfig":
        """Ensure either private_key or private_key_path is provided."""
        if not self.private_key and not self.private_key_path:
            # Default to ./private.key if neither is provided
            self.private_key_path = Path("./private.key")
        if self.private_key and self.private_key_path:
            raise ValueError("Provide either DS_PRIVATE_KEY or DS_PRIVATE_KEY_PATH, not both")
        return self

    # Runtime cached values (not from env)
    _base_uri: str | None = None
    _account_id: str | None = None

    model_config = {"env_prefix": "DS_", "case_sensitive": False}

    @classmethod
    def from_env(cls) -> "DocuSignConfig":
        """Load configuration from environment variables."""
        return cls()

    def set_runtime_info(self, base_uri: str, account_id: str) -> None:
        """Store discovered base URI and account ID."""
        self._base_uri = base_uri
        self._account_id = account_id

    @property
    def base_uri(self) -> str | None:
        """Get cached base URI."""
        return self._base_uri

    @property
    def account_id(self) -> str | None:
        """Get cached account ID."""
        return self._account_id
