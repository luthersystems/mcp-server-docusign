"""Configuration management for DocuSign MCP Server."""

from pathlib import Path
from typing import Optional

from pydantic import Field
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
    private_key_path: Path = Field(
        default=Path("./private.key"), description="Path to RSA private key (PEM)"
    )
    token_exp_secs: int = Field(default=3600, description="Token expiration in seconds")

    # Runtime cached values (not from env)
    _base_uri: Optional[str] = None
    _account_id: Optional[str] = None

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
    def base_uri(self) -> Optional[str]:
        """Get cached base URI."""
        return self._base_uri

    @property
    def account_id(self) -> Optional[str]:
        """Get cached account ID."""
        return self._account_id

