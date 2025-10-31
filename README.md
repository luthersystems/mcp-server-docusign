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
- [DocuSign developer account](https://developers.docusign.com/) (demo or production)
- Integration key with JWT configured
- RSA keypair for JWT authentication (you generate this)
- Admin consent for `signature` + `impersonation` scopes

## Installation

### Using uv (recommended)

```bash
# Install from GitHub
uvx --from git+https://github.com/luthersystems/mcp-server-docusign mcp-server-docusign

# Or install in project
uv pip install git+https://github.com/luthersystems/mcp-server-docusign
```

### Using pip

```bash
pip install git+https://github.com/luthersystems/mcp-server-docusign
```

### Development install

```bash
git clone https://github.com/luthersystems/mcp-server-docusign.git
cd mcp-server-docusign
uv pip install -e ".[dev]"
```

## Configuration

### Environment Variables

Configure the server using environment variables (see [Configuration Reference](https://developers.docusign.com/docs/esign-rest-api/how-to/request-signature-in-app-embedded/)):

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

#### 1. Create or Select Integration Key

1. Log into [DocuSign Admin Console](https://admindemo.docusign.com/) (demo) or [Admin Console](https://admin.docusign.com/) (production)
2. Navigate to **Settings** → **Apps & Keys**
3. Either:
   - **Use an existing integration key** from the list (e.g., `1fa2e333-fdc2-411c-ab65-18ed437eae53`)
   - **Or create a new one**: Click **"+ ADD APP AND INTEGRATION KEY"**
4. Note/copy the **Integration Key** (this is your `DS_INTEGRATION_KEY`)

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
3. Upload your `public.key` file (generated in step 2)
4. Under **Redirect URIs**, click "Add URI" and add: `https://www.docusign.com`
   - **Important**: The redirect URI must exactly match what you'll use in the consent URL (no trailing slash)
5. Click **Save** at the bottom

#### 4. Grant Admin Consent (One-Time Required)

**Critical**: Before the server can operate, an account administrator must grant consent for `signature` and `impersonation` scopes.

**Steps:**

1. **Ensure the redirect URI is configured** in Step 3 above (e.g., `https://www.docusign.com`)

2. **Construct the consent URL** (replace `<INTEGRATION_KEY>` with your actual integration key):
   ```
   https://account-d.docusign.com/oauth/auth?response_type=code&scope=signature%20impersonation&client_id=<INTEGRATION_KEY>&redirect_uri=https://www.docusign.com
   ```
   - For **demo/sandbox**: use `https://account-d.docusign.com`
   - For **production**: use `https://account.docusign.com`
   - The `redirect_uri` parameter **must exactly match** what you added in Step 3

3. **Visit the URL** in your browser while logged in as a DocuSign admin

4. **Click "Allow Access"** to grant consent

5. You'll be redirected to the redirect URI (which may show an error page, but that's OK - the consent was granted)

6. **This is a one-time operation** - you won't need to do it again unless you revoke consent or change scopes

**Troubleshooting Template Permissions:**

If you get 401 errors when accessing templates, ensure:

1. **User has template permissions** in DocuSign:
   - Go to **Settings** → **Users** → select the user
   - Under **Permissions**, ensure "Allow user to create and manage templates" is enabled
   - Save changes

2. **Account has templates feature** enabled (may require certain DocuSign plan levels)

3. **The OAuth scopes are correct**: 
   - The `signature` scope (included in our consent URL) covers template access
   - If you've modified scopes, you may need to re-grant consent

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
npx -y @modelcontextprotocol/inspector uvx --from git+https://github.com/luthersystems/mcp-server-docusign mcp-server-docusign
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
        "git+https://github.com/luthersystems/mcp-server-docusign",
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

# Run unit tests (no credentials needed)
pytest

# Run with coverage
pytest --cov=mcp_server_docusign --cov-report=html

# Run linter
ruff check .

# Format code
ruff format .
```

### Integration Tests (Optional)

Integration tests validate real DocuSign API authentication. They are **skipped by default** and only run when you provide real credentials.

**To enable integration tests:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your DocuSign credentials in `.env`:
   ```bash
   # Required fields (choose ONE of the two private key options):
   
   # Option 1: File path (recommended for local development)
   DS_AUTH_BASE=https://account-d.docusign.com
   DS_INTEGRATION_KEY=your-integration-key-guid
   DS_USER_ID=your-user-guid
   DS_PRIVATE_KEY_PATH=./private.key
   DS_OAUTH_SCOPE=signature impersonation
   
   # Option 2: Base64-encoded key (recommended for CI/CD)
   # DS_PRIVATE_KEY=LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0t...
   ```

3. Create your RSA keypair:
   ```bash
   openssl genrsa -out private.key 2048
   openssl rsa -in private.key -pubout -out public.key
   ```

4. Upload `public.key` to DocuSign and grant admin consent (see `.env.example` for detailed instructions)

5. Run integration tests:
   ```bash
   pytest tests/test_integration.py -v
   ```

### CI/CD Setup (GitHub Actions)

To run integration tests in GitHub Actions:

1. **Encode your private key to base64:**
   ```bash
   # macOS/Linux
   base64 -i private.key | tr -d '\n' | pbcopy
   
   # This copies the base64-encoded key to your clipboard
   ```

2. **Add GitHub repository secrets:**
   - Go to your repo → **Settings** → **Secrets and variables** → **Actions**
   - Add the following secrets:
     - `DS_AUTH_BASE`: `https://account-d.docusign.com`
     - `DS_INTEGRATION_KEY`: Your integration key GUID
     - `DS_USER_ID`: Your user GUID
     - `DS_PRIVATE_KEY`: The base64-encoded private key (from step 1)

3. **The CI workflow will automatically run integration tests** when these secrets are present

**Note**: The integration tests will be skipped in PRs from forks (for security), but will run on pushes to main/develop branches.

**What the integration tests verify:**
- ✅ JWT authentication works with your credentials
- ✅ Access token can be obtained successfully  
- ✅ Account ID can be retrieved
- ✅ Base URI is discovered correctly
- ✅ API calls work (tests `list_templates`)
- ✅ Token refresh mechanism works

**Note**: Integration tests require a DocuSign developer account (demo environment recommended).

**Troubleshooting Template Access (401 Errors):**

If the `test_list_templates` test is skipped with a 401 error, this indicates template access permissions are not configured. To fix:

1. **Check User Permissions** in DocuSign Admin Console:
   - Go to https://admindemo.docusign.com/ → **Users**
   - Click on your user → **Permissions**
   - Ensure these are enabled:
     - ✅ "Allow user to create and manage templates"
     - ✅ "Allow user to use templates"
     - ✅ "Allow user to share templates"
   - Save changes

2. **Verify OAuth Scopes**: The `signature impersonation` scopes already cover template access. If you changed scopes, you may need to re-grant admin consent.

3. **Account Plan Limitations**: Some DocuSign demo accounts may have limited API access. Templates should work with most developer accounts, but if issues persist, it may be an account-level restriction.

**Note**: The template test being skipped doesn't prevent the MCP server from functioning. Once deployed with proper production credentials and permissions, template operations will work normally.

### Project Structure

```
mcp-server-docusign/
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

