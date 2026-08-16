# GRACIA — Atelier de Moda
Sistema completo de e-commerce para un atelier de moda con panel administrador, chat en tiempo real, carrito de compras, notificaciones y cambio de idioma.

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| **Frontend** | HTML5, CSS3, JavaScript (vanilla) |
| **Backend** | Python + FastAPI + Socket.IO |
| **Base de datos** | SQLite (desarrollo) / PostgreSQL (producción) |
| **Autenticación** | JWT con bcrypt |
| **Rate Limiting** | slowapi |
| **Migraciones** | Alembic |

## Funcionalidades

### Tienda (Frontend)
- Catálogo de productos con imágenes, badges y talles
- Efectos 3D (tilt), animaciones y parallax
- Carrito de compras con persistencia por usuario
- Checkout con selección de método de pago
- Registro e inicio de sesión de usuarios
- Notificaciones push dentro de la plataforma
- Chat en vivo con el administrador (WebSocket)
- Switch de idioma Español / Inglés
- Diseño responsive, modo oscuro + dorado
- Loader animado, cursor personalizado, scroll reveal
- Lookbook carrusel con autoplay
- Contadores animados (fundación, talleres, clientes)
- Toast notifications con feedback visual
- Estados de carga en formularios y acciones

### Panel Administrador
- Dashboard con estadísticas (órdenes, ingresos, usuarios)
- Gráficos de barras de ingresos y órdenes (últimos 7 días)
- Gestión de órdenes (cambio de estado)
- Visualización de productos
- Chat en vivo para responder clientes
- Envío de notificaciones a todos los usuarios
- Configuración de redes sociales

## Seguridad

- JWT configurable via variable de entorno (`JWT_SECRET`)
- CORS con orígenes específicos configurable
- Rate limiting en endpoints de autenticación (10/min login, 5/hora register)
- Security headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, CSP
- Contraseñas hasheadas con bcrypt
- Validación de longitud mínima de contraseña
- Health check endpoint para monitoreo

## Instalación y Ejecución

### Local (desarrollo)

```bash
# Clonar el repositorio
git clone <repo-url>
cd graciacloting

# Activar entorno virtual
source backend/venv/bin/activate

# Instalar dependencias
pip install -r backend/requirements.txt

# Configurar variables de entorno
cp backend/.env backend/.env.local
# Editar backend/.env.local si es necesario

# Iniciar servidor
uvicorn backend.main:app --reload --host 0.0.0.0 --port 5000
```

### Docker (producción)

```bash
# Build y ejecución con PostgreSQL
docker compose up -d

# O solo la app con SQLite
docker build -t gracia .
docker run -p 5000:5000 gracia
```

## Acceso

| Recurso | URL |
|---------|-----|
| **Tienda** | `http://localhost:5000` |
| **Panel Admin** | `http://localhost:5000/admin` |
| **API Docs** | `http://localhost:5000/docs` |
| **Health Check** | `http://localhost:5000/health` |

### Credenciales (solo desarrollo)

En desarrollo el admin se crea al arrancar desde las variables `SEED_ADMIN_EMAIL` y
`SEED_ADMIN_PASSWORD`. **En producción no hay credenciales por defecto**: son obligatorias
esas dos variables, y una vez creado el admin, los deploys siguientes **no** las sobrescriben
(si cambiás la contraseña en el panel, se mantiene).

> ⚠️ **Importante**: En producción (Render) el app exige `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`,
> `JWT_SECRET`, `SMTP_USER` y `SMTP_PASS`; si faltan, no arranca (fail-fast a propósito).

## Deploy en Render

### Requisitos
- Repositorio en GitHub con el `render.yaml` incluido.
- Una base de datos PostgreSQL (el blueprint crea `gracia-db` automáticamente).

### Pasos
1. Crear un servicio en Render seleccionando **Blueprint** y tu repo de GitHub.
2. Render crea la base de datos y el servicio web a partir de `render.yaml`.
3. En el servicio web → **Environment**, agregar a mano (no se sincronizan desde el repo):
   - `CORS_ORIGINS` — origen del frontend (ej. `https://tuapp.onrender.com`)
   - `ALLOWED_HOSTS` — host permitido (ej. `tuapp.onrender.com`)
   - `FRONTEND_URL` — URL del frontend
   - `JWT_SECRET` — valor seguro (generalo con `python -c "import secrets; print(secrets.token_urlsafe(64))"`)
   - `SEED_ADMIN_EMAIL` — email del admin (solo primer arranque)
   - `SEED_ADMIN_PASSWORD` — contraseña fuerte del admin (solo primer arranque)
   - `SMTP_USER` / `SMTP_PASS` — credenciales SMTP para confirmaciones de pedido y reset de contraseña
   - `MP_ACCESS_TOKEN` — access token de MercadoPago para cobrar de verdad
   - `MP_WEBHOOK_SECRET` — secret del webhook de MercadoPago
4. **Opcionales de producción:**
   - `STORAGE_BACKEND=cloudinary` (o `s3`) + sus credenciales — sin esto las imágenes subidas
     al panel se guardan en disco efímero y se pierden con cada deploy.
   - `REDIS_URL` — rate limiting compartido entre workers/instancias.
   - `SENTRY_DSN` — monitoreo de errores.
5. Click en **Deploy**.

> El Dockerfile instala las dependencias de `backend/requirements.txt`, expone el puerto `5000`
> y arranca con `scripts/entrypoint.sh` (migraciones Alembic en base nueva + uvicorn).
> El health check usa `/health`.

> 🔐 **Seguridad**: nunca commitees `.env`. Las variables reales van solo en el panel de Render.
> Si en algún commit anterior quedaron credenciales reales (p. ej. en README), **rotalas**.

### Producción — Checklist

- [ ] `JWT_SECRET` generado y seguro (≥ 32 caracteres)
- [ ] `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` configurados (solo primer arranque)
- [ ] `SMTP_USER` / `SMTP_PASS` configurados (el app no arranca en producción sin ellos)
- [ ] `MP_ACCESS_TOKEN` de producción (no el de pruebas) + `MP_WEBHOOK_SECRET`
- [ ] `STORAGE_BACKEND=cloudinary` (o `s3`) con sus credenciales
- [ ] `REDIS_URL` configurado para rate limiting persistente
- [ ] Backup diario de PostgreSQL (`scripts/backup_db.sh` + cron/bucket)
- [ ] Dominio propio con HTTPS (Render provee certificados automáticamente)
- [ ] Credenciales por defecto rotadas y fuera del repo

## Tests

```bash
cd backend
pytest tests/ -v
```

## Estructura del Proyecto

```
graciacloting/
├── .env                     # Variables de entorno
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── backend/
│   ├── main.py              # API principal (FastAPI + Socket.IO)
│   ├── database.py           # Conexión SQLAlchemy
│   ├── models.py             # Modelos ORM
│   ├── schemas.py            # Schemas Pydantic
│   ├── auth.py               # Autenticación JWT + bcrypt
│   ├── services/
│   │   ├── order_service.py  # Precios en servidor + reserva/liberación de stock
│   │   ├── storage.py        # Almacenamiento de imágenes (local/cloudinary/s3)
│   │   └── email_service.py  # Envío de correos (SMTP)
│   ├── seed.py               # Datos iniciales
│   ├── requirements.txt
│   ├── alembic.ini           # Configuración de migraciones
│   ├── alembic/              # Migraciones Alembic
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   └── tests/
│       ├── __init__.py
│       └── test_api.py       # Tests automatizados
├── frontend/
│   ├── index.html            # Tienda principal
│   ├── css/
│   │   └── styles.css        # Estilos completos
│   ├── js/
│   │   ├── script.js         # Lógica frontend
│   └── admin/
│       ├── index.html        # Panel administrador
│       ├── css/
│       │   └── admin.css     # Estilos admin
│       └── js/
│           └── admin.js      # Lógica admin
└── assets/                   # Assets estáticos (imágenes, etc.)
```

Además: `scripts/entrypoint.sh` (migraciones en base nueva + uvicorn) y
`scripts/backup_db.sh` (backup de base de datos).

## API Endpoints

### Autenticación
- `POST /api/login` — Iniciar sesión (rate limit: 10/min)
- `POST /api/register` — Registrarse (rate limit: 5/hora)
- `GET /api/me` — Datos del usuario actual
- `POST /api/logout` — Cerrar sesión

### Productos
- `GET /api/products` — Listar productos
- `GET /api/products/{id}` — Ver producto

### Carrito
- `GET /api/cart` — Ver carrito
- `POST /api/cart/add` — Agregar item
- `POST /api/cart/update` — Actualizar cantidad
- `POST /api/cart/remove` — Eliminar item

### Órdenes
- `POST /api/checkout` — Confirmar compra
- `GET /api/orders` — Historial de órdenes

### Admin
- `GET /api/admin/stats` — Estadísticas del dashboard
- `GET /api/admin/orders` — Todas las órdenes
- `POST /api/admin/order/status` — Cambiar estado de orden

### Chat
- `GET /api/messages` — Mensajes del chat
- `GET /api/admin/messages` — Mensajes (admin)
- WebSocket: `send-message` / `new-message`

### Notificaciones
- `GET /api/notifications` — Notificaciones del usuario
- `POST /api/notifications/mark-read` — Marcar como leídas
- `POST /api/notifications/send` — Enviar notificación (admin)

### Sistema
- `GET /api/health` — Health check
- `POST /api/lang` — Cambiar idioma del usuario

## Licencia

Uso interno — GRACIA Atelier de Moda
