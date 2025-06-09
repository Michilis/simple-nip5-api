# Simple NIP-05 API

A Lightning-powered NIP-05 identity service that allows users to register a NIP-05 identity via LNbits payments and provides admin control over whitelist management.

## Features

- 🚀 **Lightning Payments**: Integrated with LNbits for instant Bitcoin payments
- 🆔 **NIP-05 Identity**: Full NIP-05 identity verification support
- 🔄 **Background Polling**: Robust payment verification with webhook fallback
- 🛡️ **Admin Controls**: Secure API for user management
- 📊 **Health Monitoring**: Built-in health checks and status endpoints
- 🗄️ **Database Support**: SQLite by default, PostgreSQL ready
- 🔗 **Nostr Sync**: Automatic username sync from Nostr profiles (kind:0 events)

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

**Required Configuration:**
```env
ADMIN_API_KEY=your-secret-admin-key-here
LNBITS_API_KEY=your-lnbits-api-key-here
LNBITS_ENDPOINT=https://your-lnbits-instance.com
DOMAIN=yourdomain.com
WEBHOOK_URL=https://yourdomain.com/api/public/webhook/paid
```

### 3. Run the Application

```bash
# Development mode
python run.py

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Public Endpoints

#### Create Invoice
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

**Response:**
```json
{
  "payment_hash": "abc123...",
  "payment_request": "lnbc1000n1...",
  "amount_sats": 1000,
  "expires_at": "2024-01-01T12:00:00Z",
  "username": "alice"
}
```

#### Payment Webhook
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

## Payment Flow

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

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /.well-known/nostr.json {
        proxy_pass http://localhost:8000/.well-known/nostr.json;
        add_header Access-Control-Allow-Origin *;
    }
}
```

## Health Monitoring

- **Health Check**: `GET /health`
- **Basic Status**: `GET /`
- **Logs**: Application logs include scheduler status and payment processing

## Security

- Admin endpoints are protected by API key authentication
- Input validation and normalization for all user data
- CORS enabled for `.well-known/nostr.json` endpoint
- SQL injection protection via SQLAlchemy ORM

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Create an issue on GitHub
- Check the logs at `/health` endpoint
- Verify your LNbits configuration 