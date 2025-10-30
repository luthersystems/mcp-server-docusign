"""Envelope management tools for DocuSign."""

from typing import Any

from docusign_esign import (
    Document,
    EnvelopeDefinition,
    EnvelopesApi,
    Recipients,
    Signer,
    TemplateRole,
)
from fastmcp import FastMCP

from ..docusign_client import DocuSignClient


def register_envelope_tools(mcp: FastMCP, ds_client: DocuSignClient) -> None:
    """Register envelope-related tools with the MCP server.

    Args:
        mcp: FastMCP server instance.
        ds_client: DocuSign client instance.
    """

    @mcp.tool()
    def create_envelope_from_template(
        template_id: str,
        email_subject: str,
        role_assignments: list[dict[str, str]],
        email_blurb: str | None = None,
        status: str = "sent",
    ) -> dict[str, Any]:
        """Create an envelope from a DocuSign template.

        Args:
            template_id: The template ID to use.
            email_subject: Subject line for the email.
            role_assignments: List of role assignments with keys:
                - roleName: The role name in the template
                - name: Recipient's full name
                - email: Recipient's email address
                - clientUserId: (optional) For embedded signing
            email_blurb: Optional body text for the email.
            status: Envelope status - "sent" to send immediately or "created" for draft.

        Returns:
            Dictionary with envelopeId and status.
        """
        # Build template roles
        roles = [
            TemplateRole(
                role_name=ra.get("roleName"),
                name=ra.get("name"),
                email=ra.get("email"),
                client_user_id=ra.get("clientUserId"),
            )
            for ra in role_assignments
        ]

        # Create envelope definition
        env_def = EnvelopeDefinition(
            template_id=template_id,
            email_subject=email_subject,
            email_blurb=email_blurb,
            template_roles=roles,
            status=status,
        )

        # Create envelope
        api_client = ds_client.get_api_client()
        envelopes_api = EnvelopesApi(api_client)
        account_id = ds_client.get_account_id()

        result = envelopes_api.create_envelope(account_id, envelope_definition=env_def)

        return {
            "envelopeId": result.envelope_id,
            "status": result.status,
            "statusDateTime": result.status_date_time,
        }

    @mcp.tool()
    def create_envelope_from_documents(
        documents: list[dict[str, Any]],
        recipients: dict[str, list[dict[str, str]]],
        email_subject: str,
        email_blurb: str | None = None,
        status: str = "sent",
    ) -> dict[str, Any]:
        """Create an envelope from documents (not using a template).

        Args:
            documents: List of documents with keys:
                - name: Document name
                - documentId: Document ID (e.g., "1", "2")
                - fileExtension: File extension (e.g., "pdf")
                - documentBase64: Base64-encoded document content
            recipients: Dictionary of recipient types to lists:
                - signers: List of signers with name, email, recipientId, routingOrder
            email_subject: Subject line for the email.
            email_blurb: Optional body text for the email.
            status: Envelope status - "sent" to send immediately or "created" for draft.

        Returns:
            Dictionary with envelopeId and status.
        """
        # Build documents
        docs = [
            Document(
                name=doc.get("name"),
                document_id=doc.get("documentId"),
                file_extension=doc.get("fileExtension"),
                document_base64=doc.get("documentBase64"),
            )
            for doc in documents
        ]

        # Build recipients
        signers = []
        if "signers" in recipients:
            signers = [
                Signer(
                    name=s.get("name"),
                    email=s.get("email"),
                    recipient_id=s.get("recipientId"),
                    routing_order=s.get("routingOrder", "1"),
                    client_user_id=s.get("clientUserId"),
                )
                for s in recipients["signers"]
            ]

        recipient_obj = Recipients(signers=signers)

        # Create envelope definition
        env_def = EnvelopeDefinition(
            email_subject=email_subject,
            email_blurb=email_blurb,
            documents=docs,
            recipients=recipient_obj,
            status=status,
        )

        # Create envelope
        api_client = ds_client.get_api_client()
        envelopes_api = EnvelopesApi(api_client)
        account_id = ds_client.get_account_id()

        result = envelopes_api.create_envelope(account_id, envelope_definition=env_def)

        return {
            "envelopeId": result.envelope_id,
            "status": result.status,
            "statusDateTime": result.status_date_time,
        }

    @mcp.tool()
    def get_envelope_status(envelope_id: str) -> dict[str, Any]:
        """Get the status and metadata of an envelope.

        Args:
            envelope_id: The envelope ID to query.

        Returns:
            Dictionary with envelope details including envelopeId, status,
            emailSubject, createdDateTime, sentDateTime, completedDateTime, etc.
        """
        api_client = ds_client.get_api_client()
        envelopes_api = EnvelopesApi(api_client)
        account_id = ds_client.get_account_id()

        envelope = envelopes_api.get_envelope(account_id, envelope_id)

        return {
            "envelopeId": envelope.envelope_id,
            "status": envelope.status,
            "emailSubject": envelope.email_subject,
            "emailBlurb": envelope.email_blurb,
            "createdDateTime": envelope.created_date_time,
            "sentDateTime": envelope.sent_date_time,
            "deliveredDateTime": envelope.delivered_date_time,
            "signedDateTime": envelope.signed_date_time,
            "completedDateTime": envelope.completed_date_time,
            "declinedDateTime": envelope.declined_date_time,
            "voidedDateTime": envelope.voided_date_time,
        }

    @mcp.tool()
    def list_envelopes(
        from_date: str | None = None,
        to_date: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List envelopes with optional filters.

        Args:
            from_date: Start date filter (ISO 8601 format, e.g., "2024-01-01T00:00:00Z").
            to_date: End date filter (ISO 8601 format).
            status: Status filter (e.g., "sent", "delivered", "completed", "declined").

        Returns:
            Dictionary with list of envelopes and metadata.
        """
        api_client = ds_client.get_api_client()
        envelopes_api = EnvelopesApi(api_client)
        account_id = ds_client.get_account_id()

        # Build options
        options = {}
        if from_date:
            options["from_date"] = from_date
        if to_date:
            options["to_date"] = to_date
        if status:
            options["status"] = status

        result = envelopes_api.list_status_changes(account_id, **options)

        envelopes = []
        if result.envelopes:
            envelopes = [
                {
                    "envelopeId": env.envelope_id,
                    "status": env.status,
                    "emailSubject": env.email_subject,
                    "createdDateTime": env.created_date_time,
                    "sentDateTime": env.sent_date_time,
                    "completedDateTime": env.completed_date_time,
                }
                for env in result.envelopes
            ]

        return {
            "envelopes": envelopes,
            "resultSetSize": result.result_set_size,
            "totalSetSize": result.total_set_size,
        }
