import httpx
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from config import settings

class LNbitsService:
    def __init__(self):
        self.api_key = settings.LNBITS_API_KEY
        self.endpoint = settings.LNBITS_ENDPOINT.rstrip('/')
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    async def create_invoice(
        self, 
        amount_sats: int, 
        memo: str, 
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Lightning invoice via LNbits API"""
        
        payload = {
            'out': False,  # Incoming payment
            'amount': amount_sats,
            'memo': memo,
            'expiry': settings.INVOICE_EXPIRY_SECONDS
        }
        
        if webhook_url:
            payload['webhook'] = webhook_url
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.endpoint}/api/v1/payments",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return {
                    'payment_hash': data['payment_hash'],
                    'payment_request': data['bolt11']
                }
            except httpx.HTTPError as e:
                raise Exception(f"LNbits API error: {str(e)}")
            except json.JSONDecodeError:
                raise Exception("Invalid response from LNbits API")
    
    async def check_invoice_status(self, payment_hash: str) -> Dict[str, Any]:
        """Check the status of a Lightning invoice"""
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.endpoint}/api/v1/payments/{payment_hash}",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return {
                    'paid': data.get('paid', False),
                    'amount': data.get('amount', 0),
                    'payment_hash': data.get('payment_hash'),
                    'time': data.get('time')
                }
            except httpx.HTTPError as e:
                if e.response and e.response.status_code == 404:
                    return {'paid': False, 'error': 'Invoice not found'}
                raise Exception(f"LNbits API error: {str(e)}")
            except json.JSONDecodeError:
                raise Exception("Invalid response from LNbits API")
    
    async def verify_payment(self, payment_hash: str) -> bool:
        """Verify if a payment has been completed"""
        try:
            status = await self.check_invoice_status(payment_hash)
            return status.get('paid', False)
        except:
            return False

# Global service instance
lnbits_service = LNbitsService() 