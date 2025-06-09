from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from app.database import get_db
from app.models import Invoice, User
from app.schemas import (
    InvoiceRequest, 
    InvoiceResponse, 
    WebhookPayload, 
    StatusResponse,
    ErrorResponse
)
from app.services.nip05 import normalize_username, npub_to_pubkey, validate_npub
from app.services.lnbits import lnbits_service
from app.services.scheduler import invoice_scheduler
from config import settings

router = APIRouter(prefix="/api/public", tags=["public"])

def check_lnbits_enabled():
    """Check if LNbits functionality is enabled"""
    if not settings.LNBITS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lightning payment functionality is disabled. Contact administrator for manual registration."
        )

@router.post(
    "/invoice", 
    response_model=InvoiceResponse,
    summary="Create Lightning Invoice",
    description="""
    Create a Lightning invoice for NIP-05 registration.
    
    **Lightning Mode Only** - This endpoint is only available when `LNBITS_ENABLED=true`.
    
    ### Process:
    1. Validates username and npub format
    2. Checks username availability
    3. Creates Lightning invoice via LNbits
    4. Schedules background payment monitoring
    
    ### Username Rules:
    - Alphanumeric characters, dots, dashes, underscores only
    - Must start with alphanumeric character
    - 1-50 characters in length
    
    ### Subscription Types:
    - **yearly**: {yearly_price} sats per year (can specify multiple years)
    - **lifetime**: {lifetime_price} sats
    
    The user pays the returned `payment_request` (BOLT11 invoice) with any Lightning wallet.
    Once paid, the user will be automatically activated and appear in `/.well-known/nostr.json`.
    """.format(
        yearly_price=settings.NIP05_YEARLY_PRICE_SATS,
        lifetime_price=settings.NIP05_LIFETIME_PRICE_SATS
    ),
    responses={
        200: {
            "description": "Invoice created successfully",
            "model": InvoiceResponse
        },
        400: {
            "description": "Invalid input (bad username, npub, or subscription type)",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid npub format"
                    }
                }
            }
        },
        409: {
            "description": "Username already taken or unpaid invoice exists",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Username already taken"
                    }
                }
            }
        },
        503: {
            "description": "Lightning payments disabled (admin-only mode)",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Lightning payment functionality is disabled. Contact administrator for manual registration."
                    }
                }
            }
        }
    }
)
async def create_invoice(
    request: InvoiceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a Lightning invoice for NIP-05 registration"""
    
    # Check if LNbits is enabled
    check_lnbits_enabled()
    
    try:
        # Validate and normalize inputs
        username = normalize_username(request.username)
        
        if not validate_npub(request.npub):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid npub format"
            )
        
        pubkey = npub_to_pubkey(request.npub)
        
        # Check if username is available or renewal for same user
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user and existing_user.is_active:
            # Allow renewal if it's the same public key
            if existing_user.pubkey != pubkey:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken by different user"
                )
            # Same user - this is a renewal, allow it to proceed
        
        # Remove any existing unpaid invoices for this username
        existing_invoices = db.query(Invoice).filter(
            Invoice.username == username,
            Invoice.status == "unpaid"
        ).all()
        
        for existing_invoice in existing_invoices:
            db.delete(existing_invoice)
        
        db.commit()  # Commit the deletions before creating new invoice
        
        # Determine amount based on subscription type and years
        if request.subscription_type == "yearly":
            amount_sats = settings.NIP05_YEARLY_PRICE_SATS * request.years
        elif request.subscription_type == "lifetime":
            amount_sats = settings.NIP05_LIFETIME_PRICE_SATS
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid subscription type. Must be 'yearly' or 'lifetime'"
            )
        
        # Create invoice via LNbits
        memo = f"NIP-05 {request.subscription_type} registration for {username}@{settings.DOMAIN}"
        if request.subscription_type == "yearly" and request.years > 1:
            memo += f" ({request.years} years)"
        webhook_url = settings.WEBHOOK_URL
        
        lnbits_response = await lnbits_service.create_invoice(
            amount_sats=amount_sats,
            memo=memo,
            webhook_url=webhook_url
        )
        
        # Create invoice record in database
        expires_at = datetime.utcnow() + timedelta(seconds=settings.INVOICE_EXPIRY_SECONDS)
        
        invoice = Invoice(
            payment_hash=lnbits_response['payment_hash'],
            payment_request=lnbits_response['payment_request'],
            amount_sats=amount_sats,
            username=username,
            pubkey=pubkey,
            npub=request.npub,
            subscription_type=request.subscription_type,
            expires_at=expires_at
        )
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        # Schedule polling for this invoice
        background_tasks.add_task(
            invoice_scheduler.schedule_invoice_polling,
            lnbits_response['payment_hash']
        )
        
        return InvoiceResponse(
            payment_hash=lnbits_response['payment_hash'],
            payment_request=lnbits_response['payment_request'],
            amount_sats=amount_sats,
            expires_at=expires_at,
            username=username
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create invoice: {str(e)}"
        )

@router.post(
    "/webhook/paid", 
    response_model=StatusResponse,
    include_in_schema=False,  # Hide from Swagger docs
    summary="Payment Webhook",
    description="""
    Handle webhook notification from LNbits when a payment is received.
    
    **Lightning Mode Only** - This endpoint is only available when `LNBITS_ENABLED=true`.
    
    ### Webhook Flow:
    1. LNbits sends webhook when payment is confirmed
    2. System finds matching invoice
    3. User is activated automatically
    4. Username appears in `/.well-known/nostr.json`
    
    ### Security:
    This endpoint should only be called by your LNbits instance.
    Configure the webhook URL in your LNbits settings.
    
    ### Webhook URL Format:
    `https://yourdomain.com/api/public/webhook/paid`
    """,
    responses={
        200: {
            "description": "Webhook processed successfully",
            "model": StatusResponse
        },
        404: {
            "description": "Invoice not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invoice not found"
                    }
                }
            }
        },
        503: {
            "description": "Lightning payments disabled (admin-only mode)",
            "model": ErrorResponse
        }
    }
)
async def webhook_payment_notification(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    """Handle webhook notification from LNbits when payment is received"""
    
    # Check if LNbits is enabled
    check_lnbits_enabled()
    
    try:
        # Find the invoice
        invoice = db.query(Invoice).filter(
            Invoice.payment_hash == payload.payment_hash
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )
        
        if invoice.status == "paid":
            return StatusResponse(
                status="success",
                message="Invoice already marked as paid"
            )
        
        if payload.paid:
            # Payment confirmed - activate user and handle subscription
            existing_user = db.query(User).filter(User.username == invoice.username).first()
            
            # Calculate subscription expiration date
            now = datetime.utcnow()
            if invoice.subscription_type == "yearly":
                # Calculate years from amount paid
                years = invoice.amount_sats // settings.NIP05_YEARLY_PRICE_SATS
                if years < 1:
                    years = 1  # Default to 1 year if calculation is wrong
                
                if existing_user and existing_user.expires_at and existing_user.expires_at > now:
                    # User has active subscription, extend by years from current expiration
                    new_expires_at = existing_user.expires_at + timedelta(days=365 * years)
                else:
                    # New subscription or expired subscription, start from now
                    new_expires_at = now + timedelta(days=365 * years)
            elif invoice.subscription_type == "lifetime":
                new_expires_at = None  # Lifetime subscription never expires
            else:
                new_expires_at = now + timedelta(days=365)  # Default to yearly
            
            if existing_user:
                # Update existing user
                existing_user.pubkey = invoice.pubkey
                existing_user.npub = invoice.npub
                existing_user.is_active = True
                existing_user.expires_at = new_expires_at
                existing_user.subscription_type = invoice.subscription_type
            else:
                # Create new user
                new_user = User(
                    username=invoice.username,
                    pubkey=invoice.pubkey,
                    npub=invoice.npub,
                    is_active=True,
                    expires_at=new_expires_at,
                    subscription_type=invoice.subscription_type
                )
                db.add(new_user)
            
            # Update invoice status
            invoice.status = "paid"
            invoice.paid_at = datetime.utcnow()
            
            db.commit()
            
            # Prepare response message
            if invoice.subscription_type == "lifetime":
                message = f"Lifetime subscription activated for {invoice.username}"
            else:
                expires_str = new_expires_at.strftime("%Y-%m-%d") if new_expires_at else "never"
                years = invoice.amount_sats // settings.NIP05_YEARLY_PRICE_SATS
                message = f"{years}-year subscription for {invoice.username} expires on {expires_str}"
            
            return StatusResponse(
                status="success",
                message=message
            )
        else:
            return StatusResponse(
                status="pending",
                message="Payment not yet confirmed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing error: {str(e)}"
        ) 
        