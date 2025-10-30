"""Main MCP server entry point for DocuSign."""

from fastmcp import FastMCP

from .docusign_client import DocuSignClient
from .tools.documents import register_document_tools
from .tools.envelopes import register_envelope_tools
from .tools.templates import register_template_tools

# Create FastMCP server
mcp = FastMCP("docusign")

# Initialize DocuSign client
ds_client = DocuSignClient()

# Register all tools
register_envelope_tools(mcp, ds_client)
register_template_tools(mcp, ds_client)
register_document_tools(mcp, ds_client)


def main() -> None:
    """Run the MCP server (stdio by default)."""
    mcp.run()


if __name__ == "__main__":
    main()

