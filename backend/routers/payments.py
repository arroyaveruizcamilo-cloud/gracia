from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import Order, OrderStatus, PaymentStatus, PaymentTransaction
from auth import get_current_user
from pydantic import BaseModel
from typing import Optional
import os, json, logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Colombian payment methods mapped to MercadoPago payment_method_ids
PAYMENT_METHODS_MAP = {
    "card": None,
    "pse": "pse",
    "nequi": "nequi",
    "daviplata": "daviplata",
    "llave": "llave",
    "sistecredito": "sistecredito",
}

# Display info for each method
PAYMENT_METHOD_INFO = {
    "card": {
        "name": "Tarjeta de Crédito/Débito",
        "icon": "fa-credit-card",
        "description": "Visa, Mastercard, American Express, Diners",
        "color": "#1a1a2e",
    },
    "pse": {
        "name": "Bancolombia (PSE)",
        "icon": "fa-university",
        "description": "Pago desde tu banco — Bancolombia, Davivienda, Caja Social y más",
        "color": "#003366",
    },
    "nequi": {
        "name": "Nequi",
        "icon": "fa-mobile-screen",
        "description": "Paga desde la app Nequi — rápido y sin fricción",
        "color": "#DD1A7A",
    },
    "daviplata": {
        "name": "Daviplata",
        "icon": "fa-wallet",
        "description": "Paga con tu billetera Daviplata",
        "color": "#ED1C24",
    },
    "llave": {
        "name": "Llave Davivienda",
        "icon": "fa-key",
        "description": "Paga con Llave Davivienda — sin número de tarjeta",
        "color": "#004B93",
    },
    "sistecredito": {
        "name": "SisteCrédito",
        "icon": "fa-calendar-check",
        "description": "Crédito sin tarjeta — paga en cuotas",
        "color": "#FF6600",
    },
}


class CreatePreferenceRequest(BaseModel):
    order_id: int
    payment_method: str = "card"


class PaymentReceipt(BaseModel):
    order_id: int
    email: str = ""


def get_mercado_pago():
    import mercadopago
    return mercadopago.SDK(MP_ACCESS_TOKEN)


@router.post("/create-preference")
def create_preference(data: CreatePreferenceRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    payment_method = data.payment_method
    if payment_method not in PAYMENT_METHODS_MAP:
        raise HTTPException(status_code=400, detail=f"Medio de pago no soportado: {payment_method}")

    method_info = PAYMENT_METHOD_INFO.get(payment_method, {})
    order.payment_method = payment_method
    db.commit()

    if not MP_ACCESS_TOKEN:
        order.payment_status = PaymentStatus.pending
        order.payment_id = f"SIMULATED_{order.id}_{payment_method}"
        db.commit()
        return {
            "init_point": None,
            "sandbox_init_point": None,
            "payment_id": order.payment_id,
            "status": "simulated",
            "payment_method": payment_method,
            "method_info": method_info,
            "message": "Modo simulación — configurá MP_ACCESS_TOKEN en .env para pagos reales",
        }

    items = []
    for item in order.items:
        items.append({
            "title": item.product_name,
            "quantity": item.quantity,
            "unit_price": float(item.price),
            "currency_id": "COP",
        })

    payer = {
        "name": order.customer_name or order.customer_email.split("@")[0] or "Cliente",
        "email": order.customer_email,
    }
    if order.customer_phone:
        payer["phone"] = {"number": order.customer_phone}

    preference_data = {
        "items": items,
        "payer": payer,
        "external_reference": str(order.id),
        "back_urls": {
            "success": f"{FRONTEND_URL}/frontend/index.html?payment=success&order_id={order.id}",
            "failure": f"{FRONTEND_URL}/frontend/index.html?payment=failure&order_id={order.id}",
            "pending": f"{FRONTEND_URL}/frontend/index.html?payment=pending&order_id={order.id}",
        },
        "auto_return": "approved",
        "notification_url": f"{BACKEND_URL}/payments/webhook",
        "statement_descriptor": "GRACIA CLOTHING",
    }

    if payment_method != "card" and PAYMENT_METHODS_MAP[payment_method]:
        preference_data["payment_methods"] = {
            "default_payment_method_id": PAYMENT_METHODS_MAP[payment_method],
        }

    if payment_method == "sistecredito":
        preference_data["payment_methods"] = {
            "default_payment_method_id": "sistecredito",
        }

    sdk = get_mercado_pago()
    try:
        result = sdk.preference().create(preference_data)
        response = result.get("response", {})
    except Exception as e:
        logger.error(f"MercadoPago error: {e}")
        raise HTTPException(status_code=502, detail="Error al conectar con MercadoPago")

    status_code = result.get("status", 500)
    if status_code not in (200, 201):
        logger.error(f"MercadoPago API error: {result}")
        raise HTTPException(status_code=502, detail="Error al crear preferencia de pago")

    preference_id = response.get("id", "")
    order.payment_id = preference_id
    order.payment_method = payment_method
    db.commit()

    # Log transaction
    db.add(PaymentTransaction(
        order_id=order.id,
        transaction_id=preference_id,
        payment_method=payment_method,
        amount=order.total,
        status="preference_created",
        raw_response=json.dumps(response),
    ))
    db.commit()

    return {
        "init_point": response.get("init_point"),
        "sandbox_init_point": response.get("sandbox_init_point"),
        "preference_id": preference_id,
        "payment_id": preference_id,
        "status": "created",
        "payment_method": payment_method,
        "method_info": method_info,
    }


@router.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    logger.info(f"Webhook received: {json.dumps(payload)[:500]}")

    topic = payload.get("topic") or payload.get("type", "")
    data = payload.get("data", {})
    payment_id = data.get("id") if isinstance(data, dict) else None

    if "payment" in topic and payment_id:
        process_payment_notification(payment_id)

    return {"message": "ok"}


@router.get("/webhook")
def webhook_get():
    return {"message": "Webhook endpoint ready"}


def process_payment_notification(payment_id: str):
    if not MP_ACCESS_TOKEN:
        logger.warning("MP_ACCESS_TOKEN not configured, skipping webhook processing")
        return

    try:
        sdk = get_mercado_pago()
        result = sdk.payment().get(payment_id)
        payment_data = result.get("response", {})

        if not payment_data:
            logger.warning(f"No payment data for {payment_id}")
            return

        external_ref = payment_data.get("external_reference", "")
        if not external_ref:
            logger.warning(f"No external_reference for payment {payment_id}")
            return

        order_id = int(external_ref)
        mp_status = payment_data.get("status", "")
        payment_method_id = payment_data.get("payment_method_id", "")
        transaction_amount = payment_data.get("transaction_amount", 0)
        payer_email = payment_data.get("payer", {}).get("email", "")
        instalments = payment_data.get("installments", 1)

        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                logger.warning(f"Order {order_id} not found for payment {payment_id}")
                return

            previous_status = order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status

            if mp_status == "approved" and order.payment_status != PaymentStatus.paid:
                order.payment_status = PaymentStatus.paid
                order.status = OrderStatus.processing
                order.payment_id = str(payment_id)
                logger.info(f"Order {order_id} PAID via {payment_method_id}")

            elif mp_status in ("rejected", "cancelled", "chargeback") and order.payment_status != PaymentStatus.failed:
                order.payment_status = PaymentStatus.failed
                logger.info(f"Order {order_id} FAILED: {mp_status}")

            elif mp_status == "refunded":
                order.payment_status = PaymentStatus.refunded
                logger.info(f"Order {order_id} REFUNDED")

            new_status = order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status

            db.add(PaymentTransaction(
                order_id=order.id,
                transaction_id=str(payment_id),
                payment_method=payment_method_id or "unknown",
                amount=float(transaction_amount or order.total),
                status=f"webhook_{mp_status}",
                payer_email=payer_email,
                extra_data=json.dumps({
                    "instalments": instalments,
                    "previous_status": previous_status,
                    "new_status": new_status,
                }),
                raw_response=json.dumps(payment_data, default=str),
            ))
            db.commit()

        except Exception as e:
            logger.error(f"Error processing payment {payment_id}: {e}")
            db.rollback()
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")


@router.get("/status/{order_id}")
def check_payment_status(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    payment_method = order.payment_method or ""
    method_info = PAYMENT_METHOD_INFO.get(payment_method, {})

    mp_status = None
    if payment_method not in ("", "simulado") and order.payment_id and MP_ACCESS_TOKEN:
        try:
            sdk = get_mercado_pago()
            if order.payment_id.startswith("SIMULATED_"):
                pass
            else:
                result = sdk.payment().get(order.payment_id)
                payment_data = result.get("response", {})
                mp_status = payment_data.get("status", "")
                payment_method_id = payment_data.get("payment_method_id", "")

                if mp_status == "approved" and order.payment_status != PaymentStatus.paid:
                    order.payment_status = PaymentStatus.paid
                    order.status = OrderStatus.processing
                    db.commit()
                elif mp_status in ("rejected", "cancelled") and order.payment_status != PaymentStatus.failed:
                    order.payment_status = PaymentStatus.failed
                    db.commit()
        except Exception:
            pass

    return {
        "order_id": order.id,
        "status": order.status.value if hasattr(order.status, "value") else order.status,
        "payment_status": order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status,
        "payment_method": payment_method,
        "payment_id": order.payment_id,
        "method_info": method_info,
        "mp_status": mp_status,
        "total": order.total,
        "customer_email": order.customer_email,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.get("/methods")
def list_payment_methods():
    methods = []
    for key, info in PAYMENT_METHOD_INFO.items():
        methods.append({
            "id": key,
            "name": info["name"],
            "icon": info["icon"],
            "description": info["description"],
            "color": info["color"],
        })
    return {"methods": methods, "has_mp_token": bool(MP_ACCESS_TOKEN)}


@router.post("/simulate/{order_id}")
def simulate_payment(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    previous_status = order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status

    order.payment_status = PaymentStatus.paid
    order.status = OrderStatus.processing
    order.payment_id = f"SIM_{order.id}_{datetime.now(timezone.utc).timestamp()}"
    db.commit()

    db.add(PaymentTransaction(
        order_id=order.id,
        transaction_id=order.payment_id,
        payment_method=order.payment_method or "simulado",
        amount=order.total,
        status="simulated_success",
        extra_data=json.dumps({"previous_status": previous_status}),
    ))
    db.commit()

    return {
        "message": "Pago simulado exitoso",
        "order_id": order_id,
        "total": order.total,
        "payment_status": "Pagado",
    }


@router.get("/receipt/{order_id}")
def get_payment_receipt(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    transactions = db.query(PaymentTransaction).filter(
        PaymentTransaction.order_id == order_id
    ).order_by(PaymentTransaction.created_at.desc()).all()

    return {
        "receipt": {
            "order_id": order.id,
            "customer": order.customer_name or "Cliente",
            "email": order.customer_email,
            "items": [
                {
                    "product": i.product_name,
                    "quantity": i.quantity,
                    "price": i.price,
                }
                for i in order.items
            ],
            "subtotal": order.subtotal,
            "discount": order.discount,
            "shipping": order.shipping_cost,
            "total": order.total,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status,
            "payment_id": order.payment_id,
            "status": order.status.value if hasattr(order.status, "value") else order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        },
        "transactions": [
            {
                "id": t.id,
                "transaction_id": t.transaction_id,
                "method": t.payment_method,
                "amount": t.amount,
                "status": t.status,
                "date": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ],
    }
