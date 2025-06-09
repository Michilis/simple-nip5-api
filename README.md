# Simple NIP-05 API

A Lightning-powered NIP-05 identity service that allows users to register a NIP-05 identity via LNbits payments and provides admin control over whitelist management. Can also run as an admin-only service without Lightning payments.

## Features

- 🚀 **Lightning Payments**: Integrated with LNbits for instant Bitcoin payments (optional)
- 🆔 **NIP-05 Identity**: Full NIP-05 identity verification support
- 🔄 **Background Polling**: Robust payment verification with webhook fallback
- 🛡️ **Admin Controls**: Secure API for user management
- 📊 **Health Monitoring**: Built-in health checks and status endpoints
- 🗄️ **Database Support**: SQLite by default, PostgreSQL ready
- 🔗 **Nostr Sync**: Automatic username sync from Nostr profiles (kind:0 events)
- ⚙️ **Flexible Mode**: Lightning mode or admin-only mode

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
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
LNBITS_ENABLED=true
ADMIN_API_KEY=your-secret-admin-key-here
LNBITS_API_KEY=your-lnbits-api-key-here
LNBITS_ENDPOINT=https://your-lnbits-instance.com
DOMAIN=yourdomain.com
WEBHOOK_URL=https://yourdomain.com/api/public/webhook/paid
```

**Admin-Only Mode Configuration:**
```env
LNBITS_ENABLED=false
ADMIN_API_KEY=your-secret-admin-key-here
DOMAIN=yourdomain.com
```

### 3. Run the Application

```bash
# Development mode
python run.py

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## Operating Modes

### ⚡ Lightning Mode (`LNBITS_ENABLED=true`)
- **Public Registration**: Users can self-register by paying Lightning invoices
- **Automatic Processing**: Background tasks monitor and process payments
- **Admin Override**: Admins can still manually add/remove users
- **Full Feature Set**: All endpoints and functionality available

### 👨‍💼 Admin-Only Mode (`LNBITS_ENABLED=false`)
- **Manual Registration**: Only admins can add/remove users
- **No Payment Processing**: Lightning endpoints return 503 Service Unavailable
- **Resource Efficient**: No background invoice polling
- **Pure NIP-05 Service**: Focus on identity resolution without payments

## API Endpoints

### Public Endpoints

#### Create Invoice (Lightning Mode Only)
```http
POST /api/public/invoice
```

**Request:**
```json
{
  "username": "alice",
  "npub": "npub1abc123...",
  "subscription_type": "yearly"
}
```

**Response (Lightning Mode):**
```json
{
  "payment_hash": "abc123...",
  "payment_request": "lnbc1000n1...",
  "amount_sats": 1000,
  "expires_at": "2024-01-01T12:00:00Z",
  "username": "alice"
}
```

**Response (Admin-Only Mode):**
```json
{
  "detail": "Lightning payment functionality is disabled. Contact administrator for manual registration."
}
```

#### Payment Webhook (Lightning Mode Only)
```http
POST /api/public/webhook/paid
```

**Request:**
```json
{
  "payment_hash": "abc123...",
  "paid": true,
  "amount": 1000
}
```

### Admin Endpoints

All admin endpoints require the `X-API-Key` header with your admin API key.

#### Add User
```http
POST /api/whitelist/add
Header: X-API-Key: your-admin-key
```

**Request:**
```json
{
  "username": "bob",
  "npub": "npub1def456..."
}
```

#### Remove User
```http
POST /api/whitelist/remove
Header: X-API-Key: your-admin-key
```

**Request:**
```json
{
  "username": "bob"
}
```

#### List Users
```http
GET /api/whitelist/users?active_only=true
Header: X-API-Key: your-admin-key
```

#### Activate/Deactivate User
```http
POST /api/whitelist/activate/alice
POST /api/whitelist/deactivate/alice
Header: X-API-Key: your-admin-key
```

#### Manual Username Sync
```http
POST /api/whitelist/sync-usernames
Header: X-API-Key: your-admin-key
```

### NIP-05 Endpoint

#### Well-Known Nostr JSON
```http
GET /.well-known/nostr.json
```

**Response:**
```json
{
  "names": {
    "alice": "abc123...",
    "bob": "def456..."
  }
}
```

## Username Synchronization

The system automatically syncs usernames from users' Nostr profiles:

### 🔄 How It Works

1. **Background Task**: Runs every 15 minutes (configurable)
2. **Profile Fetching**: Queries Nostr relays for kind:0 (profile) events
3. **Name Extraction**: Extracts the `name` field from profile metadata
4. **Validation**: Ensures the name is valid for NIP-05 usage
5. **Update**: Updates username if different (checks for conflicts)
6. **Rate Limiting**: Max once per 24 hours per user

### 🔗 Relay Configuration

Default relays (configurable):
- `wss://relay.azzamo.net`
- `wss://relay.damus.io` 
- `wss://primal.net`

### ⚙️ Configuration Options

```env
USERNAME_SYNC_ENABLED=true
USERNAME_SYNC_INTERVAL_MINUTES=15
USERNAME_SYNC_MAX_AGE_HOURS=24
NOSTR_RELAYS=wss://relay.azzamo.net,wss://relay.damus.io,wss://primal.net
```

### 🧪 Testing

Manually trigger sync for testing:
```bash
curl -X POST http://localhost:8000/api/whitelist/sync-usernames \
  -H "X-API-Key: your-admin-key"
```

## Health Monitoring

### Health Check Endpoints

#### Basic Status
```http
GET /
```

**Response:**
```json
{
  "service": "Simple NIP-05 API",
  "status": "healthy",
  "version": "1.0.0",
  "domain": "yourdomain.com",
  "lnbits_enabled": true,
  "username_sync_enabled": true
}
```

#### Detailed Health Check
```http
GET /health
```

**Response (Lightning Mode):**
```json
{
  "status": "healthy",
  "scheduler_running": true,
  "domain": "yourdomain.com",
  "features": {
    "lnbits_enabled": true,
    "username_sync_enabled": true,
    "admin_only_mode": false
  },
  "endpoints": {
    "nostr_json": "/.well-known/nostr.json",
    "create_invoice": "/api/public/invoice",
    "webhook": "/api/public/webhook/paid",
    "admin_add": "/api/whitelist/add",
    "admin_remove": "/api/whitelist/remove",
    "admin_users": "/api/whitelist/users",
    "admin_sync": "/api/whitelist/sync-usernames"
  }
}
```

**Response (Admin-Only Mode):**
```json
{
  "status": "healthy",
  "scheduler_running": true,
  "domain": "yourdomain.com",
  "features": {
    "lnbits_enabled": false,
    "username_sync_enabled": true,
    "admin_only_mode": true
  },
  "endpoints": {
    "nostr_json": "/.well-known/nostr.json",
    "admin_add": "/api/whitelist/add",
    "admin_remove": "/api/whitelist/remove",
    "admin_users": "/api/whitelist/users",
    "admin_sync": "/api/whitelist/sync-usernames"
  }
}
```

## Architecture

```
nip05-api/
├── app/
│   ├── main.py              # FastAPI app and routes
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response models
│   ├── database.py          # DB session and connection
│   ├── services/
│   │   ├── lnbits.py        # LNbits invoice creation & verification
│   │   ├── nip05.py         # Username normalization and nostr.json generation
│   │   ├── nostr_sync.py    # Nostr relay integration and profile sync
│   │   └── scheduler.py     # Polling for unpaid invoices & username sync
│   └── routes/
│       ├── public.py        # /api/public/* endpoints
│       ├── admin.py         # /api/whitelist/* endpoints
│       └── nostr_json.py    # /.well-known/nostr.json
├── config.py                # Settings and .env loading
├── requirements.txt         # Python dependencies
└── run.py                   # App entry point
```

## Payment Flow (Lightning Mode)

1. **User Requests Invoice**: POST to `/api/public/invoice` with username and npub
2. **Invoice Created**: System creates LNbits invoice and returns payment request
3. **User Pays**: User pays the Lightning invoice
4. **Payment Notification**: LNbits sends webhook or system polls for payment
5. **User Activated**: System activates user and includes in nostr.json
6. **NIP-05 Active**: User's identity is now resolvable via `username@yourdomain.com`
7. **Username Sync**: System periodically updates username from Nostr profile

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `LNBITS_ENABLED` | Enable Lightning payment functionality | `true` |
| `ADMIN_API_KEY` | Admin API authentication key | `"your-secret-admin-key-here"` |
| `LNBITS_API_KEY` | LNbits API key | `""` |
| `LNBITS_ENDPOINT` | LNbits instance URL | `"https://demo.lnbits.com"` |
| `NIP05_YEARLY_PRICE_SATS` | Yearly subscription price | `1000` |
| `NIP05_LIFETIME_PRICE_SATS` | Lifetime subscription price | `10000` |
| `INVOICE_EXPIRY_SECONDS` | Invoice expiration time | `1800` (30 min) |
| `DATABASE_URL` | Database connection string | `"sqlite:///./nip05.db"` |
| `DOMAIN` | Your domain name | `"localhost"` |
| `WEBHOOK_URL` | Webhook callback URL | `"http://localhost:8000/api/public/webhook/paid"` |
| `USERNAME_SYNC_ENABLED` | Enable automatic username sync | `true` |
| `USERNAME_SYNC_INTERVAL_MINUTES` | Sync interval in minutes | `15` |
| `USERNAME_SYNC_MAX_AGE_HOURS` | Max hours between syncs per user | `24` |
| `NOSTR_RELAYS` | Comma-separated list of Nostr relays | `"wss://relay.azzamo.net,..."` |

## Deployment

### Environment Setup

Create `.env` file based on your deployment mode:

**Lightning Mode (.env):**
```env
LNBITS_ENABLED=true
ADMIN_API_KEY=super-secret-admin-key-123
LNBITS_API_KEY=your-lnbits-api-key
LNBITS_ENDPOINT=https://your-lnbits.com
DOMAIN=nip05.yourdomain.com
WEBHOOK_URL=https://nip05.yourdomain.com/api/public/webhook/paid
USERNAME_SYNC_ENABLED=true
```

**Admin-Only Mode (.env):**
```env
LNBITS_ENABLED=false
ADMIN_API_KEY=super-secret-admin-key-123
DOMAIN=nip05.yourdomain.com
USERNAME_SYNC_ENABLED=true
```




## Use Cases

### 🏢 Commercial NIP-05 Service
- **Lightning Mode**: Users pay sats for NIP-05 identity
- **Automatic processing**: Minimal manual intervention
- **Scalable**: Handles high volume of registrations

### 🏠 Personal/Community Service  
- **Admin-Only Mode**: Free service for friends/community
- **Manual approval**: Full control over registrations
- **Cost-effective**: No Lightning infrastructure needed

### 🔄 Hybrid Service
- **Start Admin-Only**: Begin with manual registrations
- **Upgrade to Lightning**: Enable payments when ready
- **Gradual transition**: Existing users unaffected

## Testing

### Manual Testing Commands

```bash
# Check service status
curl http://localhost:8000/health

# Test nostr.json endpoint
curl http://localhost:8000/.well-known/nostr.json

# Add user (admin)
curl -X POST http://localhost:8000/api/whitelist/add \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "npub": "npub1..."}'

# Create invoice (Lightning mode)
curl -X POST http://localhost:8000/api/public/invoice \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "npub": "npub1...", "subscription_type": "yearly"}'

# Trigger username sync
curl -X POST http://localhost:8000/api/whitelist/sync-usernames \
  -H "X-API-Key: your-admin-key"
```

### Automated Testing

```bash
# Run with pytest (when tests are added)
pip install pytest pytest-asyncio httpx
pytest

# Load testing with curl
for i in {1..10}; do
  curl -s http://localhost:8000/health > /dev/null &
done
wait
```

## Security

### Best Practices

- 🔐 **Strong Admin Keys**: Use cryptographically secure API keys
- 🔒 **HTTPS Only**: Always use SSL in production
- 🛡️ **Input Validation**: All inputs validated and sanitized
- 🚫 **Rate Limiting**: Consider adding rate limiting for public endpoints
- 📝 **Access Logs**: Monitor access patterns
- 🔄 **Key Rotation**: Regularly rotate API keys

### Security Headers

```nginx
# Add to nginx config
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
```

## Troubleshooting

### Common Issues

**Issue**: Invoice endpoints return 503
- **Solution**: Check `LNBITS_ENABLED=true` in .env

**Issue**: Username sync not working  
- **Solution**: Verify `NOSTR_RELAYS` are reachable and `USERNAME_SYNC_ENABLED=true`

**Issue**: Users not appearing in nostr.json
- **Solution**: Check `is_active=true` in database and domain configuration

**Issue**: LNbits webhook not working
- **Solution**: Verify `WEBHOOK_URL` is publicly accessible and correct

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python run.py

# Check logs
tail -f /var/log/nip05-api.log
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- 📋 **GitHub Issues**: Create an issue with detailed description
- 📊 **Health Check**: Check `/health` endpoint for system status
- 🔧 **Configuration**: Verify your `.env` settings
- 📖 **Documentation**: Refer to this README for setup instructions

---

**Made with ⚡ for the Nostr ecosystem** 
