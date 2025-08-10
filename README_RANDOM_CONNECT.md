# WhatsApp Random Connect MCP Server

A production-ready MCP (Model Context Protocol) server that enables anonymous random chat connections through WhatsApp via Puch AI. Users can be paired with strangers for anonymous conversations without sharing phone numbers.

## 🚀 Features

- **Anonymous Matching**: Connect users randomly without revealing phone numbers
- **Simple Commands**: Easy-to-use commands for connecting, disconnecting, and managing chats
- **Phone Number Masking**: Automatic detection and masking of phone numbers in messages
- **Real-time Pairing**: Instant matchmaking with available users
- **Session Management**: Track active chats and manage user states
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Security First**: No phone numbers stored or logged in plaintext

## 🎯 Commands

| Command | Description |
|---------|-------------|
| `#meet` | Find a random available user and start a chat |
| `#bye` | End the current chat and remove partner |
| `#again` | End current chat and immediately search for new partner |
| `#hide` | Toggle phone number masking (ON by default) |
| `#who` | Reveal the nickname of your current partner |

## 🏗️ Architecture

### Core Components
- **RandomConnectManager**: Main logic handler for matchmaking and message routing
- **UserState**: Per-user state management including preferences and activity
- **MatchmakingQueue**: In-memory queue for users waiting for matches
- **ActivePairs**: Dictionary tracking current chat connections

### Message Flow
1. **Command Parsing**: Detect and process commands (#meet, #bye, etc.)
2. **Message Routing**: Forward non-command messages to chat partners
3. **State Management**: Update user states and connection tracking
4. **Security**: Apply phone number masking and sanitization

## 📦 Installation & Setup

### Prerequisites
- Python 3.11 or higher
- ngrok (for local testing) or cloud hosting platform

### Step 1: Clone and Setup
```bash
# Clone the repository (if not already done)
git clone https://github.com/TurboML-Inc/mcp-starter.git
cd mcp-starter

# Create virtual environment
uv venv

# Install dependencies
uv sync

# Activate environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

### Step 2: Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your details
AUTH_TOKEN="puch_random_connect_secure_token_2025"
MY_NUMBER="919014769239"  # Your WhatsApp number in format: {country_code}{number}
```

### Step 3: Run the Server
```bash
cd mcp-bearer-token
python random_connect_server.py
```

You should see:
```
🚀 Starting WhatsApp Random Connect MCP Server on http://0.0.0.0:8086
📱 Ready to handle WhatsApp messages for anonymous random chat!
🔗 Commands: #meet #bye #again #hide #who
```

## 🌐 Making Your Server Public

### Option A: Using ngrok (Recommended for Testing)

1. **Install ngrok**: Download from [https://ngrok.com/download](https://ngrok.com/download)

2. **Get your authtoken**:
   - Go to [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
   - Copy your authtoken
   - Run: `ngrok config add-authtoken YOUR_AUTHTOKEN`

3. **Start the tunnel**:
   ```bash
   ngrok http 8086
   ```

4. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok.app`)

### Option B: Cloud Deployment

Deploy to any of these platforms:
- **Railway**: `railway deploy`
- **Render**: Connect GitHub repo
- **Heroku**: `git push heroku main`
- **DigitalOcean App Platform**: Use GitHub integration

## 🔗 Connecting to Puch AI

1. **Open Puch AI**: [https://wa.me/+919998881729](https://wa.me/+919998881729)

2. **Connect your MCP server**:
   ```
   /mcp connect https://your-domain.ngrok.app/mcp puch_random_connect_secure_token_2025
   ```

3. **Verify connection**: Puch will confirm successful connection

4. **Enable debug mode** (optional):
   ```
   /mcp diagnostics-level debug
   ```

## 🎮 Usage Examples

### Basic Flow
```
User A: #meet
System: 🔍 Looking for someone to chat with... Please wait while we find you a partner!

User B: #meet
System to A: 🎉 Connected! You're now chatting with User_B. Say hello!
System to B: 🎉 Connected! You're now chatting with User_A. Say hello!

User A: Hello! How are you?
System to B: 📤 Message sent to your partner from User_A: Hello! How are you?

User B: I'm good, thanks! Where are you from?
System to A: 📤 Message sent to your partner from User_B: I'm good, thanks! Where are you from?

User A: #who
System: 👤 You're chatting with: User_B

User A: #bye
System to A: 👋 Chat ended. Use #meet to connect with someone new!
System to B: Your partner left the chat. Use #meet to find a new one.
```

### Advanced Commands
```
# Quick partner switch
User: #again
System: 🔄 New connection! You're now chatting with User_C. Say hello!

# Toggle phone masking
User: #hide
System: 🔒 Phone number masking is now OFF.

User: My number is 9876543210
Partner sees: My number is 9876543210

User: #hide
System: 🔒 Phone number masking is now ON.

User: Call me at 9876543210
Partner sees: Call me at [hidden]
```

## 🛠️ Development & Testing

### Local Testing
```bash
# Run the server
python random_connect_server.py

# In another terminal, test with curl
curl -X POST http://localhost:8086/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer puch_random_connect_secure_token_2025" \
  -d '{"method": "handle_message", "params": {"message": "#meet", "puch_user_id": "test_user_1"}}'
```

### Monitoring
```bash
# Get system stats
curl -X POST http://localhost:8086/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer puch_random_connect_secure_token_2025" \
  -d '{"method": "get_stats", "params": {}}'
```

### Logs
The server provides comprehensive logging:
- **Connection events**: User matches and disconnections
- **Message routing**: Sanitized message forwarding
- **Command processing**: All command executions
- **System maintenance**: Cleanup operations

## 🔒 Security & Privacy

### Phone Number Protection
- **Automatic Masking**: Phone numbers replaced with `[hidden]` by default
- **Regex Patterns**: Comprehensive detection of various phone formats
- **Logging Safety**: All logs sanitized to prevent phone number exposure
- **User Control**: Users can toggle masking with `#hide` command

### Data Privacy
- **Ephemeral Storage**: All data stored in memory only
- **No Persistence**: No permanent storage of user data
- **Automatic Cleanup**: Inactive users removed after 30 minutes
- **Minimal Data**: Only necessary information stored (user ID, nickname, preferences)

### Authentication
- **Bearer Token**: Secure token-based authentication
- **Validation Required**: Server validates tokens before processing
- **Scoped Access**: Limited to authorized operations only

## 📊 System Statistics

The server provides real-time statistics:
- **Active Users**: Currently connected users
- **Waiting Queue**: Users waiting for matches
- **Active Pairs**: Current chat connections
- **System Health**: Overall status and performance

## 🐛 Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check if server is running on port 8086
   - Verify ngrok tunnel is active
   - Confirm AUTH_TOKEN matches

2. **Commands Not Working**
   - Ensure commands start with `#` (hashtag)
   - Check for typos in command names
   - Verify user is properly connected

3. **Messages Not Routing**
   - Check if users are properly matched
   - Verify both users are active
   - Review server logs for errors

### Debug Mode
Enable detailed logging in Puch AI:
```
/mcp diagnostics-level debug
```

### Server Logs
Monitor server output for detailed information:
```bash
tail -f server.log  # If logging to file
# or watch console output
```

## 🚀 Production Deployment

### Environment Variables
```bash
AUTH_TOKEN="your_production_token_here"
MY_NUMBER="your_whatsapp_number"
LOG_LEVEL="INFO"  # or DEBUG for development
```

### Scaling Considerations
- **Memory Usage**: In-memory storage scales with active users
- **Concurrent Users**: Thread-safe operations support multiple users
- **Database Migration**: Easy to swap to Redis/PostgreSQL for persistence

### Monitoring
- **Health Checks**: Use `/health` endpoint (if implemented)
- **Metrics**: Monitor active users and connection rates
- **Alerts**: Set up alerts for high error rates or system issues

## 📝 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

- **Discord**: [Puch AI Community](https://discord.gg/VMCnMvYx)
- **Documentation**: [https://puch.ai/mcp](https://puch.ai/mcp)
- **Issues**: Create GitHub issues for bugs or feature requests

---

**Built with ❤️ for the #BuildWithPuch hackathon**

*Making AI accessible to everyone, one conversation at a time.*
