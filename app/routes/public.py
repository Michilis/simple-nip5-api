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

@router.post("/invoice", response_model=InvoiceResponse)
async def create_invoice(
    request: InvoiceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a Lightning invoice for NIP-05 registration"""
    
    try:
        # Validate and normalize inputs
        username = normalize_username(request.username)
        
        if not validate_npub(request.npub):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid npub format"
            )
        
        pubkey = npub_to_pubkey(request.npub)
        
        # Check if username is available
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user and existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )
        
        # Check for existing unpaid invoice
        existing_invoice = db.query(Invoice).filter(
            Invoice.username == username,
            Invoice.status == "unpaid",
            Invoice.expires_at > datetime.utcnow()
        ).first()
        
        if existing_invoice:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unpaid invoice already exists for this username"
            )
        
        # Determine amount based on subscription type
        if request.subscription_type == "yearly":
            amount_sats = settings.NIP05_YEARLY_PRICE_SATS
        elif request.subscription_type == "lifetime":
            amount_sats = settings.NIP05_LIFETIME_PRICE_SATS
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid subscription type. Must be 'yearly' or 'lifetime'"
            )
        
        # Create invoice via LNbits
        memo = f"NIP-05 {request.subscription_type} registration for {username}@{settings.DOMAIN}"
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

@router.post("/webhook/paid", response_model=StatusResponse)
async def webhook_payment_notification(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    """Handle webhook notification from LNbits when payment is received"""
    
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
            # Payment confirmed - activate user
            existing_user = db.query(User).filter(User.username == invoice.username).first()
            
            if existing_user:
                # Update existing user
                existing_user.pubkey = invoice.pubkey
                existing_user.npub = invoice.npub
                existing_user.is_active = True
            else:
                # Create new user
                new_user = User(
                    username=invoice.username,
                    pubkey=invoice.pubkey,
                    npub=invoice.npub,
                    is_active=True
                )
                db.add(new_user)
            
            # Update invoice status
            invoice.status = "paid"
            invoice.paid_at = datetime.utcnow()
            
            db.commit()
            
            return StatusResponse(
                status="success",
                message=f"Payment confirmed for {invoice.username}"
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