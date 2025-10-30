"""Document management tools for DocuSign."""

import base64
from typing import Any

from docusign_esign import EnvelopesApi
from fastmcp import FastMCP

from ..docusign_client import DocuSignClient


def register_document_tools(mcp: FastMCP, ds_client: DocuSignClient) -> None:
    """Register document-related tools with the MCP server.

    Args:
        mcp: FastMCP server instance.
        ds_client: DocuSign client instance.
    """

    @mcp.tool()
    def list_envelope_documents(envelope_id: str) -> dict[str, Any]:
        """List all documents in an envelope.

        Args:
            envelope_id: The envelope ID to query.

        Returns:
            Dictionary with list of documents in the envelope.
        """
        api_client = ds_client.get_api_client()
        envelopes_api = EnvelopesApi(api_client)
        account_id = ds_client.get_account_id()

        result = envelopes_api.list_documents(account_id, envelope_id)

        documents = []
        if result.envelope_documents:
            documents = [
                {
                    "documentId": doc.document_id,
                    "name": doc.name,
                    "type": doc.type,
                    "uri": doc.uri,
                    "order": doc.order,
                    "pages": doc.pages,
                }
                for doc in result.envelope_documents
            ]

        return {
            "envelopeId": envelope_id,
            "documents": documents,
        }

    @mcp.tool()
    def download_envelope_document(envelope_id: str, document_id: str) -> dict[str, Any]:
        """Download a specific document from an envelope.

        Args:
            envelope_id: The envelope ID.
            document_id: The document ID to download.

        Returns:
            Dictionary with document content (base64-encoded) and metadata.
        """
        api_client = ds_client.get_api_client()
        envelopes_api = EnvelopesApi(api_client)
        account_id = ds_client.get_account_id()

        # Download the document (returns bytes)
        document_bytes = envelopes_api.get_document(account_id, document_id, envelope_id)

        # Encode to base64 for JSON transport
        document_base64 = base64.b64encode(document_bytes).decode("utf-8")

        return {
            "envelopeId": envelope_id,
            "documentId": document_id,
            "contentBase64": document_base64,
            "sizeBytes": len(document_bytes),
        }

