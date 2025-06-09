# Simple NIP-05 API Architecture

This document describes the complete architecture for a **Simple NIP-05 API** that allows users to register a NIP-05 identity via LNbits payments and provides admin control over whitelist management.

---

## 🗂 Folder & File Structure

```bash
nip05-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app and routes
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response models
│   ├── database.py          # DB session and connection
│   ├── services/
│   │   ├── __init__.py
│   │   ├── lnbits.py        # LNbits invoice creation & verification
│   │   ├── nip05.py         # Username normalization and nostr.json generation
│   │   └── scheduler.py     # Polling for unpaid invoices
│   └── routes/
│       ├── __init__.py
│       ├── public.py        # /api/public/* endpoints
│       ├── admin.py         # /api/whitelist/* endpoints
│       └── nostr_json.py    # /.well-known/nostr.json
├── config.py                # Settings and .env loading
├── requirements.txt         # Python dependencies
├── alembic/                 # (Optional) DB migrations
└── run.py                   # App entry point
```

---

## 📦 Components

### 1. `main.py`

* Initializes the FastAPI app.
* Includes routers from `routes/`.
* Mounts `.well-known` endpoint.

### 2. `models.py`

* SQLAlchemy ORM models:

  * `User`: Stores username, pubkey, npub, active status.
  * `Invoice`: Tracks invoice status, polling metadata.

### 3. `schemas.py`

* Defines all Pydantic schemas for input/output:

  * Invoice request & response
  * Add/remove user
  * Webhook payload

### 4. `database.py`

* Creates engine, session, and dependency injection.
* Central point for DB connection.

### 5. `services/`

#### a. `lnbits.py`

* Functions to:

  * Create invoice via LNbits API
  * Poll/check invoice status
  * Verify payments via `/api/v1/payments/{payment_hash}`

#### b. `nip05.py`

* Normalize `npub` to `pubkey`
* Generate valid `.well-known/nostr.json`
* Reserve username checks

#### c. `scheduler.py`

* Starts background tasks to:

  * Poll unpaid invoices on intervals
  * Use `APScheduler` or asyncio loop

### 6. `routes/`

#### a. `public.py`

* `POST /api/public/invoice`
* `POST /api/public/webhook/paid`

#### b. `admin.py`

* `POST /api/whitelist/add`
* `POST /api/whitelist/remove`

#### c. `nostr_json.py`

* `GET /.well-known/nostr.json`

---

## 🧠 State Management

* **Database (SQLAlchemy + SQLite/PostgreSQL):**

  * Persistent store of user registrations and invoice states.

* **Invoice Status:**

  * Initially set to `unpaid`
  * Updated via webhook or polling
  * `poll_attempts` and `next_poll_time` tracked

* **User Activation:**

  * Controlled by `is_active = true`
  * Affects output in `nostr.json`

---

## 🔌 Services & Integration

### LNbits Integration

* REST API to generate invoices
* Webhook callback to our server
* Polling fallback if webhook fails

### Scheduler

* Background task loop
* Interval logic:

  * Every 1 minute (first 10 min)
  * Every 5 minutes (next 20 min)
  * Stops after 30 min or when paid

### Environment Configuration (`config.py`)

* Loads from `.env`:

```env
ADMIN_API_KEY=...
LNBits_API_KEY=...
LNBits_ENDPOINT=https://...
NIP05_YEARLY_PRICE_SATS=1000
NIP05_LIFETIME_PRICE_SATS=10000
INVOICE_EXPIRY_SECONDS=1800
```

---

## 🌐 Deployment

* Use `uvicorn` to run: `python run.py`
* Enable HTTPS and reverse proxy with Nginx or Caddy
* Optional: use Docker for isolated deployment

---

## ✅ Summary

This architecture is modular, scalable, and production-ready. It allows users to register NIP-05 identities using LNbits payments with strong failover logic, and supports admin control through secure endpoints.
