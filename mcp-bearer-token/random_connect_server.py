import asyncio
import os
import logging
from typing import Annotated
from dotenv import load_dotenv
from fastmcp import FastMCP
# Use the new JWT verifier to avoid deprecation issues
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.bearer import RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field

from random_connect import random_connect_manager

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Auth Provider ---
class SimpleBearerAuthProvider(JWTVerifier):
    """Simple constant-token verifier using JWTVerifier interface.
    Accepts exactly the token configured in .env; rejects everything else.
    """
    def __init__(self, token: str):
        # Generate ephemeral keys to satisfy base class ctor; not used for actual verification
        k = RSAKeyPair.generate()
        super().__init__(jwks_uri=None, issuer=None, audience=None, public_key=k.public_key)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token and token.strip() == (self.token or "").strip():
            return AccessToken(
                token=token,
                client_id="puch-random-connect",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

# --- MCP Server Setup ---
mcp = FastMCP(
    "WhatsApp Random Connect MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    """Validate server availability and return the server owner number.
    Returns the number in {country_code}{number} format as required by Puch.
    """
    if not MY_NUMBER or not MY_NUMBER.isdigit():
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Server not configured: MY_NUMBER missing/invalid"))
    return MY_NUMBER

# --- Tool: handle_message (main random connect functionality) ---
HANDLE_MESSAGE_DESCRIPTION = RichToolDescription(
    description=(
        "WhatsApp Random Connect router. ALWAYS CALL this tool for: "
        "(a) any message that starts with # (#meet, #bye, #again, #hide, #who, #m, #r), and "
        "(b) ANY message while the user is in an active Random Connect session. "
        "While a session is active, ALWAYS call this tool for ALL messages. Do not reply in natural language. "
        "It parses commands, manages matchmaking, and relays messages between paired users."
    ),
    use_when=(
        "When a WhatsApp message is received. Prefer this tool whenever a message begins with #, "
        "or when the user has an active chat session to ensure messages are routed to the partner. "
        "While a session is active, ALWAYS call this tool for ALL messages. Do not reply in natural language."
    ),
    side_effects="May create/end chat connections, update user states, or route messages between users.",
)

@mcp.tool(description=HANDLE_MESSAGE_DESCRIPTION.model_dump_json())
async def handle_message(
    message: Annotated[str, Field(description="The incoming WhatsApp message content")],
    puch_user_id: Annotated[str, Field(description="Unique identifier for the user (provided by Puch AI)")],
    user_nickname: Annotated[str | None, Field(description="User's display name/nickname")] = None,
) -> str:

    """
    Main handler for all WhatsApp messages in the Random Connect system.
    
    Commands:
    - #meet: Find a random chat partner
    - #bye: End current chat
    - #again: End current chat and immediately find new partner
    - #hide: Toggle phone number masking (ON by default)
    - #who: Show current partner's nickname
    
    Regular messages are routed to the user's current chat partner.
    """
    try:
        # Log incoming message (sanitized)
        sanitized_message = random_connect_manager.sanitize_for_logging(message)
        logger.info(f"Processing message from {puch_user_id[:8]}: {sanitized_message}")
        
        # Process the message through the random connect manager
        response = random_connect_manager.process_message(
            user_id=puch_user_id,
            message=message,
            nickname=user_nickname
        )
        
        # Log response (sanitized)
        sanitized_response = random_connect_manager.sanitize_for_logging(response)
        logger.info(f"Response to {puch_user_id[:8]}: {sanitized_response}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing message from {puch_user_id[:8]}: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to process message: {str(e)}"))

# --- Tool: get_stats (for monitoring and debugging) ---
STATS_DESCRIPTION = RichToolDescription(
    description="Get current system statistics for the Random Connect feature including active users, waiting queue, and active chat pairs.",
    use_when="Use this tool to monitor system health, debug issues, or get usage statistics.",
    side_effects="None - read-only operation.",
)

@mcp.tool(description=STATS_DESCRIPTION.model_dump_json())
async def get_stats() -> str:
    """Get current system statistics for monitoring and debugging."""
    try:
        stats = random_connect_manager.get_system_stats()
        
        stats_text = f"""📊 **Random Connect System Stats**

👥 **Active Users**: {stats['active_users']}
⏳ **Waiting for Match**: {stats['waiting_users']}
💬 **Active Chat Pairs**: {stats['active_pairs']}
🔗 **Total Connections**: {stats['total_connections']}

**Commands Available:**
• `#meet` - Find a random chat partner
• `#bye` - End current chat
• `#again` - End current chat and find new partner
• `#hide` - Toggle phone number masking
• `#who` - Show partner's nickname

**System Status**: ✅ Online and Ready"""

        return stats_text
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to get stats: {str(e)}"))

# --- Tool: cleanup_inactive (maintenance) ---
CLEANUP_DESCRIPTION = RichToolDescription(
    description="Clean up inactive users who haven't been active for a specified time period.",
    use_when="Use this tool for system maintenance to remove inactive users and free up resources.",
    side_effects="Removes inactive users from the system and ends their chats.",
)

@mcp.tool(description=CLEANUP_DESCRIPTION.model_dump_json())
async def cleanup_inactive(
    timeout_minutes: Annotated[int, Field(description="Minutes of inactivity before cleanup (default: 30)")] = 30,
) -> str:
    """Clean up users who have been inactive for the specified time period."""
    try:
        initial_stats = random_connect_manager.get_system_stats()
        
        # Perform cleanup
        random_connect_manager.cleanup_inactive_users(timeout_minutes)
        
        final_stats = random_connect_manager.get_system_stats()
        
        cleaned_users = initial_stats['active_users'] - final_stats['active_users']
        
        return f"""🧹 **Cleanup Complete**

⏰ **Timeout**: {timeout_minutes} minutes
🗑️ **Users Cleaned**: {cleaned_users}
👥 **Remaining Active Users**: {final_stats['active_users']}
💬 **Active Chat Pairs**: {final_stats['active_pairs']}

**System Status**: ✅ Cleanup Successful"""
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to cleanup: {str(e)}"))

# --- Tool: help (user guidance) ---
HELP_DESCRIPTION = RichToolDescription(
    description="Provide help and usage instructions for the Random Connect feature.",
    use_when="Use this tool when users need help or want to understand available commands.",
    side_effects="None - informational only.",
)

@mcp.tool(description=HELP_DESCRIPTION.model_dump_json())
async def help() -> str:
    """Provide help and usage instructions for Random Connect."""
    return """🤝 **WhatsApp Random Connect - Help**

**What is Random Connect?**
Connect with random strangers for anonymous chat without sharing phone numbers!

**Available Commands:**
• `#meet` - Find a random available user and start chatting
• `#bye` - End your current chat and disconnect
• `#again` - End current chat and immediately find a new partner
• `#hide` - Toggle phone number masking (ON by default)
• `#who` - Reveal your current partner's nickname (never their phone number)

**How it works:**
1. Send `#meet` to join the matchmaking queue
2. When matched, start chatting normally
3. All your messages are relayed to your partner
4. Use `#bye` when you want to end the chat
5. Use `#again` to quickly find a new partner

**Privacy & Security:**
🔒 Phone numbers are masked by default
🔐 No personal information is shared
👤 Only nicknames are revealed with `#who`
🛡️ All data is ephemeral (not permanently stored)

**Need help?** Just send any message and we'll guide you!"""

# --- Background task for periodic cleanup ---
async def periodic_cleanup():
    """Background task to periodically clean up inactive users."""
    while True:
        try:
            await asyncio.sleep(1800)  # Run every 30 minutes
            random_connect_manager.cleanup_inactive_users(30)
            logger.info("Periodic cleanup completed")
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {str(e)}")

# --- Run MCP Server ---
async def main():
    print("🚀 Starting WhatsApp Random Connect MCP Server on http://0.0.0.0:8086")
    print("📱 Ready to handle WhatsApp messages for anonymous random chat!")
    print("🔗 Commands: #meet #bye #again #hide #who")
    
    # Start background cleanup task
    asyncio.create_task(periodic_cleanup())
    
    # Start the MCP server
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
