# DocuSign MCP Server

**Experimental** Model Context Protocol (MCP) server for DocuSign eSignature API, built with Python + FastMCP. Uses JWT OAuth for true server-to-server authentication (no refresh tokens).

## ⚠️ Status & Disclaimers

- **Experimental**: Not production-ready; no SLA; APIs and behavior may change.
- **No affiliation with DocuSign**: This is a community integration. DocuSign is a trademark of DocuSign, Inc.
- **Security**: Do **not** commit secrets. Treat private keys and tokens as sensitive; use a secrets manager. **Use at your own risk.**

## Features

- 🔐 **JWT server-to-server authentication** - No refresh tokens, fully headless operation
- 📄 **Envelope management** - Create, send, track, and manage envelopes
- 📋 **Template operations** - List and use DocuSign templates
- 📥 **Document handling** - Upload, download, and manage documents
- 🔌 **MCP protocol** - Standard stdio transport for AI assistant integration
- ✅ **Unit tested** - Comprehensive pytest coverage with mocks

## Requirements

- Python 3.11+
- `uv` package manager (recommended) or `pip`
- DocuSign developer account (demo or production)
- Integration key with JWT configured
- RSA keypair for JWT authentication
- Admin consent for `signature` + `impersonation` scopes

## Installation

### Using uv (recommended)

```bash
# Install from GitHub
uvx --from git+https://github.com/luthersystems/mcp-docusign mcp-server-docusign

# Or install in project
uv pip install git+https://github.com/luthersystems/mcp-docusign
```

### Using pip

```bash
pip install git+https://github.com/luthersystems/mcp-docusign
```

### Development install

```bash
git clone https://github.com/luthersystems/mcp-docusign.git
cd mcp-docusign
uv pip install -e ".[dev]"
```

## Configuration

### Environment Variables

Configure the server using environment variables:

```bash
# Authentication base URL
DS_AUTH_BASE=https://account-d.docusign.com  # Demo environment
# DS_AUTH_BASE=https://account.docusign.com  # Production environment

# Integration credentials
DS_INTEGRATION_KEY=<your-integration-key-guid>
DS_USER_ID=<impersonated-user-guid>

# OAuth configuration
DS_OAUTH_SCOPE="signature impersonation"

# Private key path
DS_PRIVATE_KEY_PATH=./private.key

# Token expiration (seconds)
DS_TOKEN_EXP_SECS=3600
```

### DocuSign Setup

#### 1. Create Integration Key

1. Log into DocuSign Admin Console
2. Navigate to **Apps & Keys**
3. Click **Add App and Integration Key**
4. Note the **Integration Key** (client ID)

#### 2. Generate RSA Keypair

```bash
# Generate private key
openssl genrsa -out private.key 2048

# Extract public key
openssl rsa -in private.key -pubout -out public.key
```

#### 3. Configure Integration

1. In DocuSign Admin Console, select your integration
2. Under **Authentication**, choose **JWT (JSON Web Token)**
3. Upload your `public.key` file
4. Add redirect URI (can be `http://localhost` for JWT)
5. Save changes

#### 4. Grant Admin Consent

**Critical**: Before the server can operate, an account administrator must grant consent:

1. Construct consent URL:
   ```
   https://account-d.docusign.com/oauth/auth?response_type=code&scope=signature%20impersonation&client_id=<INTEGRATION_KEY>&redirect_uri=http://localhost
   ```
2. Visit URL in browser while logged in as admin
3. Click **Allow Access**
4. This is a **one-time** operation

#### 5. Get User ID

The User ID (GUID) can be found:
- In DocuSign Admin Console → **Users** → select user → user GUID in URL
- Or via API call to `/oauth/userinfo` after initial authentication

## Running the Server

### Stdio Mode (default)

```bash
# Set environment variables
export DS_AUTH_BASE=https://account-d.docusign.com
export DS_INTEGRATION_KEY=your-integration-key
export DS_USER_ID=your-user-guid
export DS_PRIVATE_KEY_PATH=./private.key

# Run server
mcp-server-docusign
```

The server runs in stdio mode by default, suitable for MCP clients like Claude Desktop or Cursor.

### Testing with MCP Inspector

```bash
npx -y @modelcontextprotocol/inspector uvx --from git+https://github.com/luthersystems/mcp-docusign mcp-server-docusign
```

## Available Tools

### Envelope Operations

#### `create_envelope_from_template`
Creates an envelope from a DocuSign template.

**Parameters:**
- `template_id` (string): Template ID to use
- `email_subject` (string): Email subject line
- `role_assignments` (array): List of role assignments
  - `roleName` (string): Role name from template
  - `name` (string): Recipient's full name
  - `email` (string): Recipient's email
  - `clientUserId` (string, optional): For embedded signing
- `email_blurb` (string, optional): Email body text
- `status` (string, default: "sent"): "sent" or "created"

**Returns:** `{envelopeId, status, statusDateTime}`

#### `create_envelope_from_documents`
Creates an envelope from documents (not using a template).

**Parameters:**
- `documents` (array): List of documents
  - `name` (string): Document name
  - `documentId` (string): Document ID (e.g., "1", "2")
  - `fileExtension` (string): File extension (e.g., "pdf")
  - `documentBase64` (string): Base64-encoded content
- `recipients` (object): Recipient lists
  - `signers` (array): List of signers
- `email_subject` (string): Email subject
- `email_blurb` (string, optional): Email body
- `status` (string, default: "sent"): "sent" or "created"

**Returns:** `{envelopeId, status, statusDateTime}`

#### `get_envelope_status`
Gets status and metadata of an envelope.

**Parameters:**
- `envelope_id` (string): Envelope ID

**Returns:** `{envelopeId, status, emailSubject, createdDateTime, sentDateTime, completedDateTime, ...}`

#### `list_envelopes`
Lists envelopes with optional filters.

**Parameters:**
- `from_date` (string, optional): Start date (ISO 8601)
- `to_date` (string, optional): End date (ISO 8601)
- `status` (string, optional): Status filter

**Returns:** `{envelopes[], resultSetSize, totalSetSize}`

### Template Operations

#### `list_templates`
Lists available DocuSign templates.

**Parameters:**
- `search_text` (string, optional): Filter by name

**Returns:** `{templates[], resultSetSize, totalSetSize}`

#### `get_template_definition`
Gets complete template definition.

**Parameters:**
- `template_id` (string): Template ID

**Returns:** `{templateId, name, description, roles[], documents[], ...}`

### Document Operations

#### `list_envelope_documents`
Lists all documents in an envelope.

**Parameters:**
- `envelope_id` (string): Envelope ID

**Returns:** `{envelopeId, documents[]}`

#### `download_envelope_document`
Downloads a document from an envelope.

**Parameters:**
- `envelope_id` (string): Envelope ID
- `document_id` (string): Document ID

**Returns:** `{envelopeId, documentId, contentBase64, sizeBytes}`

## Example Usage

### Using with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "docusign": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/luthersystems/mcp-docusign",
        "mcp-server-docusign"
      ],
      "env": {
        "DS_AUTH_BASE": "https://account-d.docusign.com",
        "DS_INTEGRATION_KEY": "your-integration-key",
        "DS_USER_ID": "your-user-guid",
        "DS_PRIVATE_KEY_PATH": "/path/to/private.key"
      }
    }
  }
}
```

### Example Prompts

> "List my DocuSign templates"

> "Create an envelope from template [template-id] with John Doe (john@example.com) as Signer1"

> "Check the status of envelope [envelope-id]"

> "Download document 1 from envelope [envelope-id]"

## Development

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mcp_server_docusign --cov-report=html

# Run linter
ruff check .

# Format code
ruff format .
```

### Project Structure

```
mcp-docusign/
├── src/mcp_server_docusign/
│   ├── __init__.py
│   ├── server.py           # Main FastMCP server
│   ├── config.py           # Configuration management
│   ├── docusign_client.py  # JWT auth & API client
│   └── tools/
│       ├── envelopes.py    # Envelope tools
│       ├── templates.py    # Template tools
│       └── documents.py    # Document tools
├── tests/
│   ├── test_envelopes.py
│   ├── test_templates.py
│   └── test_documents.py
├── pyproject.toml
└── README.md
```

## Troubleshooting

### "Failed to obtain JWT token"
- Verify admin consent has been granted
- Check integration key is correct
- Ensure public key is uploaded to DocuSign
- Verify user GUID is correct

### "No accounts found for user"
- User ID must be valid and active
- Check user has proper permissions
- Ensure impersonation scope is granted

### "Authentication failed"
- Verify private key matches uploaded public key
- Check private key file path is correct
- Ensure key file is readable

### "Connection timeout"
- Check internet connectivity
- Verify firewall settings
- Try demo environment (`account-d.docusign.com`) first

## Security Best Practices

1. **Never commit private keys** - Use `.gitignore` and environment variables
2. **Use secrets management** - Store credentials in secure vaults (AWS Secrets Manager, etc.)
3. **Rotate keys regularly** - Generate new keypairs periodically
4. **Limit token lifetime** - Use shorter expiration for sensitive operations
5. **Monitor API usage** - Check DocuSign dashboard for unusual activity
6. **Use demo environment** - Test with demo accounts before production

## Architecture

- **Language**: Python 3.11+
- **Framework**: FastMCP
- **API Client**: Official DocuSign Python SDK (`docusign-esign`)
- **Auth**: JWT server-to-server OAuth
- **Transport**: stdio (MCP protocol)
- **Testing**: pytest with mocks

## References

- [DocuSign eSignature API](https://developers.docusign.com/docs/esign-rest-api/)
- [DocuSign JWT OAuth](https://developers.docusign.com/platform/auth/jwt/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [DocuSign Python SDK](https://github.com/docusign/docusign-esign-python-client)

## License

MIT

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

This is an experimental community project. For DocuSign API issues, consult [DocuSign Developer Center](https://developers.docusign.com/).

