# Simple NIP-05 API

A comprehensive Lightning-powered NIP-05 identity service with automatic database management, Nostr DM notifications, and flexible user management. Supports both Lightning payments and admin-only registration modes.

## ✨ Features

- 🚀 **Lightning Payments**: Integrated with LNbits for instant Bitcoin payments (optional)
- 🆔 **NIP-05 Identity**: Full NIP-05 identity verification support
- 🔄 **Background Polling**: Robust payment verification with webhook fallback
- 🛡️ **Admin Controls**: Secure API for comprehensive user management
- 📊 **Health Monitoring**: Built-in health checks with startup diagnostics
- 🗄️ **Database Support**: SQLite by default, PostgreSQL ready with auto-migration
- 🔗 **Nostr Sync**: Automatic username sync from Nostr profiles (kind:0 events)
- 💬 **Nostr DMs**: Automated direct message notifications for user events
- 📄 **Whitelist.json**: File-based user management with database sync
- ⚙️ **Flexible Modes**: Lightning mode or admin-only mode
- 🌐 **CORS Support**: Configurable cross-origin resource sharing
- 📚 **API Documentation**: Interactive Swagger documentation
- 🔧 **Auto Database Management**: Automatic schema updates and health checks

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Michilis/simple-nip5-api.git
cd simple-nip5-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp env.example .env

# Edit configuration
nano .env
```

**Lightning Mode Configuration:**
```env
# Lightning Settings
LNBITS_ENABLED=true
LNBITS_API_KEY=your-lnbits-api-key
LNBITS_ENDPOINT=https://your-lnbits-instance.com

# Domain & Security
DOMAIN=yourdomain.com
ADMIN_API_KEY=your-secret-admin-key-here
WEBHOOK_URL=https://yourdomain.com/api/webhook/paid

# Nostr DM Notifications (optional)
NOSTR_DM_ENABLED=true
NOSTR_DM_PRIVATE_KEY=your-nostr-private-key-hex
NOSTR_DM_RELAYS=wss://relay.damus.io,wss://nostr.bitcoiner.social

# CORS (optional)
CORS_ENABLED=true
CORS_ORIGINS=*
```

**Admin-Only Mode Configuration:**
```env
# Lightning Settings
LNBITS_ENABLED=false

# Domain & Security
DOMAIN=yourdomain.com
ADMIN_API_KEY=your-secret-admin-key-here

# Optional Features
NOSTR_DM_ENABLED=false
CORS_ENABLED=true
```

### 3. Run the Application

```bash
# Development mode
python run.py

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

### 🔗 Interactive Documentation

Once your application is running, visit **`/api-docs`** for comprehensive Swagger documentation:

```
http://localhost:8000/api-docs
```

### 🎯 API Endpoints Overview

| Endpoint | Method | Description | Auth Required |
|----------|---------|-------------|---------------|
| **Public Endpoints** |
| `/.well-known/nostr.json` | GET | NIP-05 identity resolution | None |
| `/api/invoice` | POST | Create Lightning invoice | None |
| `/api/user/info` | POST | Get user information by npub/pubkey | None |
| `/api/webhook/paid` | POST | Payment webhook (LNbits) | None |
| `/health` | GET | Detailed system health check | None |
| **Admin Endpoints** |
| `/api/whitelist/add` | POST | Add user manually | API Key |
| `/api/whitelist/remove` | POST | Remove user | API Key |
| `/api/whitelist/users` | GET | List all users | API Key |
| `/api/whitelist/activate/{npub}` | POST | Activate user | API Key |
| `/api/whitelist/deactivate/{npub}` | POST | Deactivate user | API Key |
| `/api/whitelist/sync-usernames` | POST | Sync usernames from Nostr | API Key |
| `/api/whitelist/set-username` | POST | Set username manually | API Key |
| `/api/whitelist/remove-username` | POST | Remove manual username setting | API Key |

### 🔧 Input Format Support

Many endpoints now support **flexible input formats**:

- **npub format**: `npub1abc123...` (bech32 encoded)
- **hex pubkey**: `abc123def456...` (64-character hex string)

**Supported endpoints:**
- `/api/user/info` - `npub` field
- `/api/whitelist/add` - `npub` field  
- `/api/whitelist/remove` - `npub` field
- `/api/whitelist/activate/{npub}` - path parameter
- `/api/whitelist/deactivate/{npub}` - path parameter

## 🏗️ Operating Modes

### ⚡ Lightning Mode (`LNBITS_ENABLED=true`)
- **Public Registration**: Users can self-register by paying Lightning invoices
- **Automatic Processing**: Background tasks monitor and process payments
- **Admin Override**: Admins can still manually add/remove users
- **Full Feature Set**: All endpoints and functionality available
- **DM Notifications**: Automatic payment confirmations and updates

### 👨‍💼 Admin-Only Mode (`LNBITS_ENABLED=false`)
- **Manual Registration**: Only admins can add/remove users
- **No Payment Processing**: Lightning endpoints return 503 Service Unavailable
- **Resource Efficient**: No background invoice polling
- **Pure NIP-05 Service**: Focus on identity resolution without payments
- **Whitelist Management**: Use whitelist.json or API for user management

## 💾 Database Management

### 🔄 Automatic Schema Management

The application includes a comprehensive database management system:

- **Automatic Migrations**: Schema updates applied on startup
- **Health Checks**: 4-stage startup validation process
- **Cross-Database Support**: SQLite, PostgreSQL, MySQL compatible
- **Error Recovery**: Detailed diagnostics and repair guidance
- **Backup Friendly**: Safe migration with rollback support

### 📊 Startup Health Checks

1. **Database Initialization** - Creates tables and runs migrations
2. **Schema Verification** - Confirms all required columns exist  
3. **Configuration Validation** - Checks critical settings
4. **Whitelist Synchronization** - Syncs whitelist.json if present

Check startup status at `/health` endpoint.

## 📄 Whitelist.json Management

### 📝 File-Based User Management

Create a `whitelist.json` file for bulk user management:

```json
{
  "users": [
    {
      "pubkey": "npub1abc123...",
      "username": "alice",
      "active": true,
      "note": "Early supporter"
    },
    {
      "pubkey": "def456789abcdef...",
      "username": "bob", 
      "active": true,
      "note": "Manual addition"
    }
  ]
}
```

### 🔄 Automatic Sync

- **Startup Sync**: Automatically syncs on application start
- **Conflict Resolution**: Whitelist.json takes precedence over database
- **Username Protection**: Whitelist users get manual username protection
- **Status Tracking**: View sync status in health endpoint

## 🔗 Username Synchronization

### 🔄 Automatic Nostr Profile Sync

The system automatically syncs usernames from users' Nostr profiles:

1. **Background Task**: Runs every 60 minutes (configurable)
2. **Profile Fetching**: Queries Nostr relays for kind:0 (profile) events
3. **Name Extraction**: Extracts the `name` field from profile metadata
4. **Validation**: Ensures the name is valid for NIP-05 usage
5. **Conflict Handling**: Resolves username conflicts intelligently
6. **Rate Limiting**: Max once per 24 hours per user

### 🛡️ Manual Username Control

- **Manual Override**: Set usernames manually via API
- **Sync Exclusion**: Manually set usernames excluded from auto-sync
- **Flexible Management**: Enable/disable auto-sync per user

### 🔗 Relay Configuration

```env
NOSTR_RELAYS=wss://relay.azzamo.net,wss://relay.damus.io,wss://primal.net
USERNAME_SYNC_ENABLED=true
USERNAME_SYNC_INTERVAL_MINUTES=60
USERNAME_SYNC_MAX_AGE_HOURS=24
```

## 💬 Nostr DM Notifications

### 📨 Automated Messaging

Send automatic DM notifications for user events:

- **Payment Confirmed**: When Lightning payment is received
- **User Whitelisted**: When manually added by admin
- **User Removed**: When removed from whitelist
- **Subscription Expiry**: Warnings and notifications
- **Username Updates**: When username changes

### 📋 Message Templates

Customize messages in `messages.json`:

```json
{
  "payment_confirmed": {
    "subject": "Payment Confirmed!",
    "body": "Your payment has been confirmed! Welcome to {domain}..."
  },
  "user_whitelisted": {
    "subject": "Welcome to {domain}!",
    "body": "You have been added to our NIP-05 service..."
  }
}
```

### ⚙️ DM Configuration

```env
NOSTR_DM_ENABLED=true
NOSTR_DM_PRIVATE_KEY=your-nostr-private-key-hex
NOSTR_DM_RELAYS=wss://relay.damus.io,wss://nostr.bitcoiner.social
NOSTR_DM_FROM_NAME=NIP-05 Service
```

## 🌐 CORS Configuration

### 🔧 Flexible CORS Setup

Configure cross-origin resource sharing for web applications:

```env
# Enable/disable CORS
CORS_ENABLED=true

# Allow all origins (development)
CORS_ORIGINS=*

# Specific origins (production)
CORS_ORIGINS=https://yourwebsite.com,https://app.yoursite.com

# Additional CORS settings
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE
CORS_ALLOW_HEADERS=*
```

## 💰 Payment Flow (Lightning Mode)

1. **User Requests Invoice**: POST to `/api/invoice` with username and npub
2. **Invoice Created**: System creates LNbits invoice and returns payment request
3. **User Pays**: User pays the Lightning invoice
4. **Payment Notification**: LNbits sends webhook or system polls for payment
5. **User Activated**: System activates user and includes in nostr.json
6. **DM Notification**: User receives payment confirmation (if enabled)
7. **Username Sync**: System periodically updates username from Nostr profile

## ⚙️ Configuration Reference

### 🔧 Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DOMAIN` | Your domain name | `"localhost"` |
| `ADMIN_API_KEY` | Admin API authentication key | `"your-secret-admin-key-here"` |
| `DATABASE_URL` | Database connection string | `"sqlite:///./nip05.db"` |

### ⚡ Lightning Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `LNBITS_ENABLED` | Enable Lightning payment functionality | `true` |
| `LNBITS_API_KEY` | LNbits API key | `""` |
| `LNBITS_ENDPOINT` | LNbits instance URL | `"https://demo.lnbits.com"` |
| `NIP05_YEARLY_PRICE_SATS` | Yearly subscription price | `1000` |
| `NIP05_LIFETIME_PRICE_SATS` | Lifetime subscription price | `5000` |
| `INVOICE_EXPIRY_SECONDS` | Invoice expiration time | `1800` (30 min) |
| `WEBHOOK_URL` | Webhook callback URL | `"http://localhost:8000/api/webhook/paid"` |

### 🔗 Nostr Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `USERNAME_SYNC_ENABLED` | Enable automatic username sync | `true` |
| `USERNAME_SYNC_INTERVAL_MINUTES` | Sync interval in minutes | `60` |
| `USERNAME_SYNC_MAX_AGE_HOURS` | Max hours between syncs per user | `24` |
| `NOSTR_RELAYS` | Comma-separated list of Nostr relays | `"wss://relay.azzamo.net,..."` |

### 💬 DM Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `NOSTR_DM_ENABLED` | Enable DM notifications | `true` |
| `NOSTR_DM_PRIVATE_KEY` | Nostr private key for sending DMs | `""` |
| `NOSTR_DM_RELAYS` | Relays for sending DMs | `"wss://relay.damus.io,..."` |
| `NOSTR_DM_FROM_NAME` | Sender name for DMs | `"NIP-05 Service"` |

### 🌐 CORS Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ENABLED` | Enable CORS middleware | `true` |
| `CORS_ORIGINS` | Allowed origins (* for all) | `"*"` |
| `CORS_ALLOW_CREDENTIALS` | Allow credentials | `true` |
| `CORS_ALLOW_METHODS` | Allowed HTTP methods | `"*"` |
| `CORS_ALLOW_HEADERS` | Allowed headers | `"*"` |

### 📄 File Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `WHITELIST_FILE` | Whitelist JSON file path | `"whitelist.json"` |
| `MESSAGES_FILE` | DM messages template file | `"messages.json"` |

## 🚀 Deployment

### 🌐 Production Environment

**Production .env Example:**
```env
# Core Settings
DOMAIN=nip05.yourdomain.com
ADMIN_API_KEY=super-secret-admin-key-123
DATABASE_URL=postgresql://user:pass@localhost/nip05db

# Lightning Settings
LNBITS_ENABLED=true
LNBITS_API_KEY=your-production-lnbits-key
LNBITS_ENDPOINT=https://your-lnbits.com
WEBHOOK_URL=https://nip05.yourdomain.com/api/webhook/paid

# Nostr Settings
USERNAME_SYNC_ENABLED=true
NOSTR_DM_ENABLED=true
NOSTR_DM_PRIVATE_KEY=your-nostr-private-key
NOSTR_DM_RELAYS=wss://relay.damus.io,wss://nostr.bitcoiner.social

# Security
CORS_ENABLED=true
CORS_ORIGINS=https://yoursite.com,https://app.yoursite.com
```

### 🐳 Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 🔄 Systemd Service

```ini
[Unit]
Description=NIP-05 API Service
After=network.target

[Service]
Type=simple
User=nip05
WorkingDirectory=/home/nip05/simple-nip5-api
Environment=PATH=/home/nip05/simple-nip5-api/venv/bin
ExecStart=/home/nip05/simple-nip5-api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📊 Monitoring & Health

### 🔍 Health Endpoints

- **`/`** - Basic health check
- **`/health`** - Detailed system status with:
  - Startup check results (4/4 checks passed)
  - Database information and statistics
  - Feature status and configuration
  - Server uptime and performance metrics

### 📈 Monitoring Integration

The health endpoints provide structured data perfect for monitoring tools:

```bash
# Check basic health
curl http://localhost:8000/

# Detailed health with database info
curl http://localhost:8000/health
```

## 🛠️ Development

### 🏃‍♂️ Local Development

```bash
# Clone and setup
git clone https://github.com/Michilis/simple-nip5-api.git
cd simple-nip5-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure for development
cp env.example .env
# Edit .env with your settings

# Run with auto-reload
python run.py
```

### 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Test specific endpoint
curl -X POST http://localhost:8000/api/user/info \
  -H "Content-Type: application/json" \
  -d '{"npub": "npub1234..."}'
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/Michilis/simple-nip5-api/issues)
- **Documentation**: Visit `/api-docs` when running the application
- **Health Check**: Use `/health` endpoint for system diagnostics 