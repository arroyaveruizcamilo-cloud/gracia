# GRACIA — Atelier de Moda
|istema completo de e-commerce para un atelier de moda con panel administrador, chat en tiempo real, carrito de compras, notificaciones y cambio de idioma.

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
| **Health Check** | `http://localhost:5000/api/health` |

### Credenciales por defecto (solo desarrollo)

| Rol | Email | Contraseña |
|-----|-------|-----------|
| **Admin** | `admin@gracia.moda` | `Admin123!` |
| **Demo** | `demo@gracia.moda` | `Demo123!` |

> ⚠️ **Importante**: Cambiá el email y contraseña del admin en producción usando las variables de entorno `SEED_ADMIN_EMAIL` y `SEED_ADMIN_PASSWORD`.

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
