import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@gracia.moda")


def send_email(to: str, subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EMAIL] No SMTP configured. Would send to {to}: {subject}")
        return False
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[EMAIL] Sent to {to}: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send to {to}: {e}")
        return False


def send_password_reset(to: str, token: str):
    reset_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:5000')}/reset-password?token={token}"
    html = f"""
    <html><body style="font-family:sans-serif;padding:40px;background:#f5f5f5">
    <div style="max-width:500px;margin:auto;background:#fff;border-radius:16px;padding:40px">
    <h2 style="color:#d4af37;margin:0 0 16px">GRACIA</h2>
    <p>Has solicitado restablecer tu contraseña.</p>
    <a href="{reset_link}" style="display:inline-block;padding:14px 32px;background:#d4af37;color:#fff;text-decoration:none;border-radius:8px;margin:20px 0">Restablecer contraseña</a>
    <p style="color:#999;font-size:12px">Este enlace expira en 1 hora. Si no solicitaste esto, ignora este mensaje.</p>
    </div></body></html>
    """
    return send_email(to, "GRACIA — Restablece tu contraseña", html)


def send_order_confirmation(to: str, order_id: int, items: list, total: float, customer_name: str, payment_method: str):
    items_html = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #eee">{i["product_name"]}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #eee;text-align:center">x{i["quantity"]}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #eee;text-align:right">${i["price"]:.2f}</td></tr>'
        for i in items
    )
    html = f"""
    <html><body style="font-family:Inter,sans-serif;margin:0;padding:0;background:#f5f3f0">
    <div style="max-width:560px;margin:auto;background:#fff">
    <div style="background:#0a0a0f;padding:32px;text-align:center">
      <h1 style="font-family:Georgia,serif;color:#c9a84c;margin:0;letter-spacing:6px;font-size:24px">GRACIA</h1>
      <p style="color:rgba(255,255,255,.5);font-size:12px;letter-spacing:3px;margin:8px 0 0">CLOTHING</p>
    </div>
    <div style="padding:40px">
      <h2 style="font-size:22px;margin:0 0 8px;color:#1a1a2e">¡Gracias por tu compra, {customer_name}!</h2>
      <p style="color:#6b6863;font-size:14px;margin:0 0 24px">Hemos recibido tu pedido y lo estamos procesando.</p>

      <div style="background:#faf8f6;border:1px solid #e0dcd4;border-radius:12px;padding:24px;margin-bottom:24px">
        <div style="display:flex;justify-content:space-between;margin-bottom:16px">
          <span style="font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#6b6863">Pedido</span>
          <span style="font-weight:700;font-size:16px">#{order_id}</span>
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <thead><tr>
            <th style="text-align:left;padding:8px 0;border-bottom:2px solid #e0dcd4;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863">Producto</th>
            <th style="text-align:center;padding:8px 0;border-bottom:2px solid #e0dcd4;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863">Cant</th>
            <th style="text-align:right;padding:8px 0;border-bottom:2px solid #e0dcd4;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863">Precio</th>
          </tr></thead>
          <tbody>{items_html}</tbody>
        </table>
        <div style="border-top:2px solid #e0dcd4;margin-top:12px;padding-top:12px;text-align:right;font-size:18px;font-weight:700;color:#c9a84c">Total: ${total:.2f}</div>
      </div>

      <div style="background:#faf8f6;border:1px solid #e0dcd4;border-radius:12px;padding:24px;margin-bottom:24px">
        <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:2px;color:#6b6863;margin:0 0 12px">Medio de pago</h3>
        <p style="margin:0;font-size:15px">{payment_method}</p>
      </div>

      <div style="background:#faf8f6;border:1px solid #e0dcd4;border-radius:12px;padding:24px;margin-bottom:24px">
        <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:2px;color:#6b6863;margin:0 0 12px">¿Qué sigue?</h3>
        <p style="margin:0 0 8px;font-size:14px;color:#6b6863">Recibirás una notificación cuando tu pedido sea enviado.</p>
        <p style="margin:0;font-size:14px;color:#6b6863">Podés rastrear tu pedido desde nuestra web con el número #{order_id} y tu email.</p>
      </div>
    </div>
    <div style="background:#0a0a0f;padding:24px;text-align:center">
      <p style="color:rgba(255,255,255,.3);font-size:12px;margin:0">© 2026 Gracia Clothing — Todos los derechos reservados</p>
    </div>
    </div></body></html>
    """
    return send_email(to, f"GRACIA — Confirmación de pedido #{order_id}", html)


def send_admin_new_order(to: str, order_id: int, customer_name: str, customer_email: str, total: float, items: list):
    items_html = "".join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #eee;font-size:13px">{i["product_name"]}</td>'
        f'<td style="padding:6px 0;border-bottom:1px solid #eee;text-align:center;font-size:13px">x{i["quantity"]}</td>'
        f'<td style="padding:6px 0;border-bottom:1px solid #eee;text-align:right;font-size:13px">${i["price"]:.2f}</td></tr>'
        for i in items
    )
    html = f"""
    <html><body style="font-family:Inter,sans-serif;margin:0;padding:0;background:#f5f3f0">
    <div style="max-width:560px;margin:auto;background:#fff">
    <div style="background:#0a0a0f;padding:24px;text-align:center">
      <h1 style="font-family:Georgia,serif;color:#c9a84c;margin:0;letter-spacing:6px;font-size:20px">GRACIA</h1>
      <p style="color:rgba(255,255,255,.5);font-size:11px;letter-spacing:3px;margin:4px 0 0">NUEVO PEDIDO</p>
    </div>
    <div style="padding:32px">
      <div style="background:#fff4e5;border:1px solid #c9a84c;border-radius:8px;padding:16px;text-align:center;margin-bottom:24px">
        <span style="font-size:28px;font-weight:700;color:#c9a84c">#{order_id}</span>
        <p style="margin:4px 0 0;font-size:13px;color:#6b6863">Nuevo pedido por <strong>${total:.2f}</strong></p>
      </div>

      <table style="width:100%;margin-bottom:16px">
        <tr><td style="font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863;padding:4px 0">Cliente</td>
            <td style="font-size:14px;font-weight:600;padding:4px 0;text-align:right">{customer_name}</td></tr>
        <tr><td style="font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863;padding:4px 0">Email</td>
            <td style="font-size:14px;padding:4px 0;text-align:right">{customer_email}</td></tr>
        <tr><td style="font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863;padding:4px 0">Total</td>
            <td style="font-size:14px;font-weight:700;padding:4px 0;text-align:right;color:#c9a84c">${total:.2f}</td></tr>
      </table>

      <h3 style="font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#6b6863;margin:16px 0 8px">Productos</h3>
      <table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="text-align:left;padding:6px 0;border-bottom:2px solid #e0dcd4;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863">Producto</th>
          <th style="text-align:center;padding:6px 0;border-bottom:2px solid #e0dcd4;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863">Cant</th>
          <th style="text-align:right;padding:6px 0;border-bottom:2px solid #e0dcd4;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#6b6863">Precio</th>
        </tr></thead>
        <tbody>{items_html}</tbody>
      </table>

      <div style="margin-top:24px;background:#faf8f6;border-radius:8px;padding:16px;text-align:center">
        <a href="{os.getenv('FRONTEND_URL', 'http://localhost:5000')}/admin" style="display:inline-block;padding:12px 24px;background:#c9a84c;color:#fff;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600">Ver pedido en el panel</a>
      </div>
    </div>
    </div></body></html>
    """
    return send_email(to, f"🛒 Nuevo pedido #{order_id} — ${total:.2f}", html)


def send_order_status_update(to: str, order_id: int, status: str, customer_name: str, tracking_number: str = ""):
    status_emoji = {"Pendiente": "⏳", "Procesando": "🔄", "Enviado": "📦", "Entregado": "✅", "Cancelado": "❌"}
    emoji = status_emoji.get(status, "📋")
    html = f"""
    <html><body style="font-family:Inter,sans-serif;margin:0;padding:0;background:#f5f3f0">
    <div style="max-width:560px;margin:auto;background:#fff">
    <div style="background:#0a0a0f;padding:32px;text-align:center">
      <h1 style="font-family:Georgia,serif;color:#c9a84c;margin:0;letter-spacing:6px;font-size:24px">GRACIA</h1>
    </div>
    <div style="padding:40px;text-align:center">
      <div style="font-size:48px;margin-bottom:16px">{emoji}</div>
      <h2 style="font-size:22px;margin:0 0 8px;color:#1a1a2e">¡Tu pedido #{order_id} está <span style="color:#c9a84c">{status}</span>!</h2>
      <p style="color:#6b6863;font-size:14px;margin:0 0 24px">Hola {customer_name}, actualizamos el estado de tu pedido.</p>
      {f'<div style="background:#faf8f6;border:1px solid #e0dcd4;border-radius:12px;padding:24px;margin-bottom:24px"><p style="margin:0;font-size:14px;color:#6b6863">Número de guía: <strong style="color:#1a1a2e">{tracking_number}</strong></p></div>' if tracking_number else ""}
    </div>
    <div style="background:#0a0a0f;padding:24px;text-align:center">
      <p style="color:rgba(255,255,255,.3);font-size:12px;margin:0">© 2026 Gracia Clothing</p>
    </div>
    </div></body></html>
    """
    return send_email(to, f"{emoji} Pedido #{order_id} — {status}", html)
