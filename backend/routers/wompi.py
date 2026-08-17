"""
Wompi payment routes.
Creates transactions, handles webhooks, provides config to frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import Order, OrderStatus, PaymentStatus, PaymentTransaction
from pydantic import BaseModel
from typing import Optional
import os, json, logging
from datetime import datetime, timezone

from services import wompi
from services.order_service import release_stock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments/wompi", tags=["Wompi Payments"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Wompi payment method types
WOMPI_METHODS = {
    "card": "CARD",
    "pse": "PSE",
    "nequi": "NEQUI",
    "daviplata": "DAVIPLATA",
    "bancolombia_transfer": "BANCOLOMBIA_TRANSFER",
}


class WompiPaymentRequest(BaseModel):
    order_id: int
    payment_method: str = "card"


@router.get("/config")
def wompi_config():
    """Return public key and whether Wompi is configured."""
    return {
        "public_key": os.getenv("WOMPI_PUBLIC_KEY", ""),
        "enabled": bool(os.getenv("WOMPI_PRIVATE_KEY", "")),
    }


@router.post("/create")
def create_wompi_transaction(data: WompiPaymentRequest, db: Session = Depends(get_db)):
    """Create a Wompi transaction and return redirect URL."""
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if not os.getenv("WOMPI_PRIVATE_KEY"):
        # Simulated mode
        order.payment_method = data.payment_method
        order.payment_status = PaymentStatus.pending
        order.payment_id = f"WOMPI_SIM_{order.id}_{data.payment_method}"
        db.commit()

        db.add(PaymentTransaction(
            order_id=order.id,
            transaction_id=order.payment_id,
            payment_method=data.payment_method,
            amount=order.total,
            status="simulated",
        ))
        db.commit()

        return {
            "status": "simulated",
            "transaction_id": None,
            "redirect_url": None,
            "message": "Modo simulación — configurá WOMPI_PRIVATE_KEY en .env para pagos reales",
        }

    # Map frontend method to Wompi method
    wompi_method_type = WOMPI_METHODS.get(data.payment_method, "CARD")

    # Build payment method payload
    payment_method_payload = {
        "type": wompi_method_type,
    }

    # Amount in centavos (Wompi uses COP centavos)
    amount_in_cents = int(order.total * 100)

    redirect_url = f"{FRONTEND_URL}/?payment_result=redirect&order_id={order.id}"

    result = wompi.create_transaction(
        reference=str(order.id),
        amount_in_cents=amount_in_cents,
        customer_email=order.customer_email,
        customer_name=order.customer_name or "Cliente",
        customer_phone=order.customer_phone or None,
        payment_method=payment_method_payload,
        redirect_url=redirect_url,
    )

    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])

    # Store transaction info on order
    order.payment_method = data.payment_method
    order.payment_id = str(result.get("transaction_id", ""))
    db.commit()

    db.add(PaymentTransaction(
        order_id=order.id,
        transaction_id=str(result.get("transaction_id", "")),
        payment_method=data.payment_method,
        amount=order.total,
        status="transaction_created",
        raw_response=json.dumps(result),
    ))
    db.commit()

    return {
        "status": "created",
        "transaction_id": result.get("transaction_id"),
        "redirect_url": result.get("redirect_url"),
        "reference": result.get("reference"),
    }


@router.post("/webhook")
async def wompi_webhook(request: Request):
    """Receive Wompi webhook events."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    logger.info(f"Wompi webhook received: {json.dumps(payload)[:500]}")

    # Verify signature
    if not wompi.verify_webhook_signature(payload):
        logger.warning("Wompi webhook signature verification failed")
        return {"message": "invalid signature"}

    event_id = payload.get("id")
    event_type = payload.get("event", "")
    transaction_data = payload.get("transaction", {})

    if not transaction_data:
        return {"message": "no transaction data"}

    wompi_status = transaction_data.get("status", "")
    reference = transaction_data.get("reference", "")
    wompi_tx_id = transaction_data.get("id")

    if not reference:
        return {"message": "no reference"}

    try:
        order_id = int(reference)
    except (ValueError, TypeError):
        logger.warning(f"Invalid reference in wompi webhook: {reference}")
        return {"message": "invalid reference"}

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.warning(f"Order {order_id} not found for wompi webhook")
            return {"message": "order not found"}

        previous_status = order.payment_status

        if wompi_status == "APPROVED" and order.payment_status != PaymentStatus.paid:
            order.payment_status = PaymentStatus.paid
            order.status = OrderStatus.processing
            order.payment_id = str(wompi_tx_id)
            logger.info(f"Order {order_id} PAID via Wompi (transaction {wompi_tx_id})")

        elif wompi_status in ("DECLINED", "VOIDED", "ERROR", "EXPIRED"):
            if order.payment_status != PaymentStatus.failed:
                order.payment_status = PaymentStatus.failed
                release_stock(db, order)
                logger.info(f"Order {order_id} FAILED via Wompi: {wompi_status}")

        elif wompi_status == "PENDING":
            order.payment_status = PaymentStatus.pending
            logger.info(f"Order {order_id} PENDING via Wompi")

        db.add(PaymentTransaction(
            order_id=order.id,
            transaction_id=str(wompi_tx_id or ""),
            payment_method=order.payment_method or "wompi",
            amount=float(transaction_data.get("amount_in_cents", 0)) / 100,
            status=f"webhook_{wompi_status.lower()}",
            payer_email=transaction_data.get("customer_email", ""),
            extra_data=json.dumps({
                "event_type": event_type,
                "event_id": event_id,
                "previous_status": str(previous_status),
                "new_status": str(order.payment_status),
            }),
            raw_response=json.dumps(payload, default=str),
        ))
        db.commit()

    except Exception as e:
        logger.error(f"Error processing Wompi webhook for order {order_id}: {e}")
        db.rollback()
    finally:
        db.close()

    return {"message": "ok"}


@router.get("/status/{order_id}")
def get_wompi_status(order_id: int, db: Session = Depends(get_db)):
    """Check payment status for an order, optionally polling Wompi API."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    wompi_tx_id = None
    live_status = None

    if order.payment_id and not order.payment_id.startswith("WOMPI_SIM_"):
        try:
            wompi_tx_id = int(order.payment_id)
        except (ValueError, TypeError):
            pass

    if wompi_tx_id and os.getenv("WOMPI_PRIVATE_KEY"):
        tx_data = wompi.get_transaction_status(wompi_tx_id)
        if tx_data:
            live_status = tx_data.get("status", "")
            ref_status = tx_data.get("status", "")

            if ref_status == "APPROVED" and order.payment_status != PaymentStatus.paid:
                order.payment_status = PaymentStatus.paid
                order.status = OrderStatus.processing
                db.commit()
            elif ref_status in ("DECLINED", "VOIDED", "ERROR", "EXPIRED"):
                if order.payment_status != PaymentStatus.failed:
                    order.payment_status = PaymentStatus.failed
                    release_stock(db, order)
                    db.commit()

    return {
        "order_id": order.id,
        "payment_status": order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status,
        "payment_method": order.payment_method,
        "total": order.total,
        "live_status": live_status,
    }


@router.get("/webhook")
def wompi_webhook_get():
    return {"message": "Wompi webhook endpoint ready"}
