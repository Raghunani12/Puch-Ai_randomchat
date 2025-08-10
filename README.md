# MCP Starter for Puch AI

This is a starter template for creating your own Model Context Protocol (MCP) server that works with Puch AI. It comes with ready-to-use tools for job searching and image processing.

## What is MCP?

MCP (Model Context Protocol) allows AI assistants like Puch to connect to external tools and data sources safely. Think of it like giving your AI extra superpowers without compromising security.

## What's Included in This Starter?

## Folders

- **[`mcp-bearer-token/`](./mcp-bearer-token/)**
  Example MCP servers using **Bearer token** auth (required by Puch AI). Includes:
  - **[`mcp_starter.py`](./mcp-bearer-token/mcp_starter.py)**
    A minimal MCP server with:
    - Text input/output tool (echo-style processing)
    - Image input/output tool (e.g., convert to black & white)
    - Bearer token validation
  - **[`puch-user-id-mcp-example.py`](./mcp-bearer-token/puch-user-id-mcp-example.py)**
    A task management MCP server that demonstrates how to use `puch_user_id` (a unique, Puch-provided user identifier) to scope tasks and data per user.

- **[`mcp-google-oauth/`](./mcp-google-oauth/)**
  Example MCP server showing how to implement **OAuth** with Google for MCP authentication/authorization.

- **[`mcp-oauth-github/`](./mcp-oauth-github/)**
  Example MCP server showing how to implement **OAuth** with GitHub for MCP authentication/authorization.

## Quick Setup Guide

### Step 1: Install Dependencies

First, make sure you have Python 3.11 or higher installed. Then:

```bash
# Create virtual environment
uv venv

# Install all required packages
uv sync

# Activate the environment
source .venv/bin/activate
```

### Step 2: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env
```

Then edit `.env` and add your details:

```env
AUTH_TOKEN=your_secret_token_here
MY_NUMBER=919876543210
```

**Important Notes:**

- `AUTH_TOKEN`: This is your secret token for authentication. Keep it safe!
- `MY_NUMBER`: Your WhatsApp number in format `{country_code}{number}` (e.g., `919876543210` for +91-9876543210)

### Step 3: Run the Server

```bash
cd mcp-bearer-token
python mcp_starter.py
```

You'll see: `🚀 Starting MCP server on http://0.0.0.0:8086`

### Step 4: Make It Public (Required by Puch)

Since Puch needs to access your server over HTTPS, you need to expose your local server:

#### Option A: Using ngrok (Recommended)

1. **Install ngrok:**
   Download from https://ngrok.com/download

2. **Get your authtoken:**
   - Go to https://dashboard.ngrok.com/get-started/your-authtoken
   - Copy your authtoken
   - Run: `ngrok config add-authtoken YOUR_AUTHTOKEN`

3. **Start the tunnel:**
   ```bash
   ngrok http 8086
   ```

#### Option B: Deploy to Cloud

You can also deploy this to services like:

- Railway
- Render
- Heroku
- DigitalOcean App Platform


## WhatsApp Random Connect MCP Server (Puch AI)

This repository includes a production-ready MCP server that enables anonymous, random one-to-one chat inside Puch on WhatsApp. It uses in-memory state for speed and can be swapped to Redis later.

### Highlights
- Anonymous pairing: no phone numbers shared (masked in all outbound text)
- Minimal commands: connect and chat — no fluff
- Scales to 100+ concurrent users (O(1) queue, capped per-user inbox)
- Session safety: per-pair session IDs, strict routing, and locking
- Privacy-first logging (sanitized)

### Prerequisites
- Python 3.11+
- ngrok (for HTTPS tunneling in development)

### Environment
Create or edit .env in the repo root with:

```env
AUTH_TOKEN=gotselected
MY_NUMBER=919014769239
```

Notes:
- AUTH_TOKEN is the Bearer token Puch will use when connecting to your MCP server.
- MY_NUMBER must be in {country_code}{number} without + (required by Puch’s validate tool).

### Run the Random Connect server

```bash
# From the repo root
source .venv/bin/activate  # if using uv venv
python3 mcp-bearer-token/random_connect_server.py
```

You should see it listening on http://0.0.0.0:8086 and the MCP endpoint mounted at /mcp/.

### Expose HTTPS with ngrok

```bash
ngrok http 8086
```
Copy the HTTPS URL, e.g. https://abcd1234.ngrok-free.app

### Connect from WhatsApp (Puch)
- Open: https://wa.me/+919998881729
- Send:

```
/mcp connect https://abcd1234.ngrok-free.app/mcp gotselected
```

If needed, also try with a trailing slash: /mcp connect https://.../mcp/ gotselected

### Use it
- Pair: `#meet`
- Send: `#r your message` (or `#R ...`)
- Check messages: `#m` (or `#M`)
- End: `#bye`
- Reconnect quickly: `#again`
- Mask toggle: `#hide` (ON by default)
- See partner nickname: `#who`

Behavior (MVP, optimized for reliability under load):
- Strict command flow by default for deterministic routing during the hackathon
  - Only `#R/#r` sends to partner
  - Only `#M/#m` pulls queued partner messages
  - Non-command text returns a tip to use `#R` and `#M`
- On successful pairing, both users are notified they’re connected and can start chatting
- Messages are routed only between the two matched users (no user-specified targets)

### Security & Privacy
- Phone numbers are masked in all outbound content and logs (regex-based)
- Chat routing uses active_pairs and per-pair session IDs; misrouted messages are dropped
- All data is in-memory and ephemeral (Redis/Postgres ready if needed)

### Troubleshooting
- 401 Unauthorized: Check your AUTH_TOKEN and ensure you used the `/mcp` path
- 404 Not Found: You hit the root; include `/mcp` or `/mcp/` at the end of your URL
- 307 Temporary Redirect: Normal — `/mcp` redirects to `/mcp/`
- Puch replies in natural language instead of routing through the tool: it should not while a session is active. Our tool description instructs: “While a session is active, ALWAYS call this tool for ALL messages. Do not reply in natural language.” If needed, send `/mcp diagnostics-level debug` once.

### Scale notes
- Matchmaking uses deque + set (O(1))
- Per-user inbox capped at 100 messages to prevent memory pressure
- Lock-protected critical sections; optional asyncio/Redis migration for horizontal scaling

---

## How to Connect with Puch AI

1. **[Open Puch AI](https://wa.me/+919998881729)** in your browser
2. **Start a new conversation**
3. **Use the connect command:**
   ```
   /mcp connect https://your-domain.ngrok.app/mcp your_secret_token_here
   ```

### Debug Mode

To get more detailed error messages:

```
/mcp diagnostics-level debug
```

## Customizing the Starter

### Adding New Tools

1. **Create a new tool function:**

   ```python
   @mcp.tool(description="Your tool description")
   async def your_tool_name(
       parameter: Annotated[str, Field(description="Parameter description")]
   ) -> str:
       # Your tool logic here
       return "Tool result"
   ```

2. **Add required imports** if needed

## 📚 **Additional Documentation Resources**

### **Official Puch AI MCP Documentation**

- **Main Documentation**: https://puch.ai/mcp
- **Protocol Compatibility**: Core MCP specification with Bearer & OAuth support
- **Command Reference**: Complete MCP command documentation
- **Server Requirements**: Tool registration, validation, HTTPS requirements

### **Technical Specifications**

- **JSON-RPC 2.0 Specification**: https://www.jsonrpc.org/specification (for error handling)
- **MCP Protocol**: Core protocol messages, tool definitions, authentication

### **Supported vs Unsupported Features**

**✓ Supported:**

- Core protocol messages
- Tool definitions and calls
- Authentication (Bearer & OAuth)
- Error handling

**✗ Not Supported:**

- Videos extension
- Resources extension
- Prompts extension

## Getting Help

- **Join Puch AI Discord:** https://discord.gg/VMCnMvYx
- **Check Puch AI MCP docs:** https://puch.ai/mcp
- **Puch WhatsApp Number:** +91 99988 81729

---

**Happy coding! 🚀**

Use the hashtag `#BuildWithPuch` in your posts about your MCP!

This starter makes it super easy to create your own MCP server for Puch AI. Just follow the setup steps and you'll be ready to extend Puch with your custom tools!
