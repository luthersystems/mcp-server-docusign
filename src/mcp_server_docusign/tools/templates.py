"""Template management tools for DocuSign."""

from typing import Any

from docusign_esign import TemplatesApi
from fastmcp import FastMCP

from ..docusign_client import DocuSignClient


def register_template_tools(mcp: FastMCP, ds_client: DocuSignClient) -> None:
    """Register template-related tools with the MCP server.

    Args:
        mcp: FastMCP server instance.
        ds_client: DocuSign client instance.
    """

    @mcp.tool()
    def list_templates(search_text: str | None = None) -> dict[str, Any]:
        """List available DocuSign templates.

        Args:
            search_text: Optional search text to filter templates by name.

        Returns:
            Dictionary with list of templates and metadata.
        """
        api_client = ds_client.get_api_client()
        templates_api = TemplatesApi(api_client)
        account_id = ds_client.get_account_id()

        # Build options
        options = {}
        if search_text:
            options["search_text"] = search_text

        result = templates_api.list_templates(account_id, **options)

        templates = []
        if result.envelope_templates:
            templates = [
                {
                    "templateId": tmpl.template_id,
                    "name": tmpl.name,
                    "description": tmpl.description,
                    "shared": tmpl.shared,
                    "created": tmpl.created,
                    "lastModified": tmpl.last_modified,
                }
                for tmpl in result.envelope_templates
            ]

        return {
            "templates": templates,
            "resultSetSize": result.result_set_size,
            "totalSetSize": result.total_set_size,
        }

    @mcp.tool()
    def get_template_definition(template_id: str) -> dict[str, Any]:
        """Get the definition and details of a specific template.

        Args:
            template_id: The template ID to retrieve.

        Returns:
            Dictionary with complete template details including roles, tabs,
            documents, and other metadata.
        """
        api_client = ds_client.get_api_client()
        templates_api = TemplatesApi(api_client)
        account_id = ds_client.get_account_id()

        template = templates_api.get(account_id, template_id)

        # Extract recipients/roles
        roles = []
        if template.recipients and template.recipients.signers:
            roles = [
                {
                    "roleName": signer.role_name,
                    "name": signer.name,
                    "recipientId": signer.recipient_id,
                    "routingOrder": signer.routing_order,
                }
                for signer in template.recipients.signers
            ]

        # Extract documents
        documents = []
        if template.documents:
            documents = [
                {
                    "documentId": doc.document_id,
                    "name": doc.name,
                    "fileExtension": doc.file_extension,
                    "order": doc.order,
                }
                for doc in template.documents
            ]

        return {
            "templateId": template.template_id,
            "name": template.name,
            "description": template.description,
            "shared": template.shared,
            "created": template.created,
            "lastModified": template.last_modified,
            "emailSubject": template.email_subject,
            "emailBlurb": template.email_blurb,
            "roles": roles,
            "documents": documents,
        }
