import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, engine
from models import Base, User, Product, ProductVariant, Order, OrderItem, OrderTimeline, Address, Category, Collection, Review, Coupon, Banner, FAQ
from auth import hash_password

SEED_PRODUCTS = [
    ('Vestido Seda Ébano', 'Ebony Silk Dress', 'Vestidos', 'Dresses', 290, None,
     'https://placehold.co/600x800/2d1b1b/d4a843?text=Vestido%20Seda%20Ébano',
     'Confeccionado en seda salvaje con caída fluida.', 'Nuevo', 45),
    ('Blazer Corte Italiano', 'Italian Cut Blazer', 'Sastrería', 'Tailoring', 450, None,
     'https://placehold.co/600x800/1b1b2d/d4a843?text=Blazer%20Corte%20Italiano',
     'Blazer sartorial en lana virgen italiana.', 'Exclusivo', 35),
    ('Falda Plisada Seda', 'Pleated Silk Skirt', 'Faldas', 'Skirts', 210, None,
     'https://placehold.co/600x800/2d2d1b/d4a843?text=Falda%20Plisada%20Seda',
     'Falda plisada en seda natural.', 'Nuevo', 40),
    ('Gabardina Camel', 'Camel Trench Coat', 'Abrigos', 'Coats', 364, 520,
     'https://placehold.co/600x800/1b2d1b/d4a843?text=Gabardina%20Camel',
     'Gabardina clásica en algodón italiano.', '-30%', 25),
    ('Bolso Cuero Toscano', 'Tuscan Leather Bag', 'Accesorios', 'Accessories', 380, None,
     'https://placehold.co/600x800/2d1b2d/d4a843?text=Bolso%20Cuero%20Toscano',
     'Bolso tote en cuero vacuno toscano.', '', 50),
    ('Camisa Lino Blanca', 'White Linen Shirt', 'Camisas', 'Shirts', 175, None,
     'https://placehold.co/600x800/1b2d15/d4a843?text=Camisa%20Lino%20Blanca',
     'Camisa en lino 100% irlandés.', '', 60),
    ('Blusa Seda Marfil', 'Ivory Silk Blouse', 'Blusas', 'Blouses', 185, None,
     'https://placehold.co/600x800/2d1b15/d4a843?text=Blusa%20Seda%20Marfil',
     'Blusa en seda marfil con detalles de pliegues.', 'Nuevo', 30),
    ('Body Encaje Negro', 'Black Lace Bodysuit', 'Bodys', 'Bodysuits', 165, None,
     'https://placehold.co/600x800/152d1b/d4a843?text=Body%20Encaje%20Negro',
     'Body de encaje francés con cierre en la espalda.', 'Exclusivo', 20),
    ('Jeans Rectos Lavado Claro', 'Light Wash Straight Jeans', 'Jeans', 'Jeans', 220, None,
     'https://placehold.co/600x800/1b152d/d4a843?text=Jeans%20Rectos%20Lavado',
     'Jeans rectos en denim premium.', '', 45),
    ('Buzo Algodón Premium', 'Premium Cotton Sweatshirt', 'Busos', 'Sweatshirts', 175, None,
     'https://placehold.co/600x800/2d2d15/d4a843?text=Buzo%20Algodón%20Premium',
     'Buzo en algodón premium con corte oversized.', '', 50),
    ('Blazer Denim', 'Denim Blazer', 'Blazers', 'Blazers', 320, None,
     'https://placehold.co/600x800/152d2d/d4a843?text=Blazer%20Denim',
     'Blazer confeccionado en denim de alta calidad.', 'Exclusivo', 30),
    ('Vestido Noche Terciopelo', 'Velvet Evening Gown', 'Vestidos', 'Dresses', 520, 650,
     'https://placehold.co/600x800/2d1b1b/d4a843?text=Vestido%20Noche%20Terciop',
     'Vestido largo en terciopelo italiano.', '-20%', 15),
    ('Vestido Corto Lentejuelas', 'Sequin Mini Dress', 'Vestidos', 'Dresses', 280, None,
     'https://placehold.co/600x800/2d1b1b/d4a843?text=Vestido%20Corto%20Lenteju',
     'Vestido corto de lentejuelas doradas.', 'Exclusivo', 30),
    ('Chaqueta Motera Cuero', 'Leather Biker Jacket', 'Abrigos', 'Coats', 420, None,
     'https://placehold.co/600x800/1b2d1b/d4a843?text=Chaqueta%20Motera%20Cuero',
     'Chaqueta motera en cuero nobuck.', '', 25),
    ('Camisa Oxford Blanca', 'White Oxford Shirt', 'Camisas', 'Shirts', 145, None,
     'https://placehold.co/600x800/1b2d15/d4a843?text=Camisa%20Oxford%20Blanca',
     'Camisa Oxford clásica en algodón egipcio.', '', 75),
    ('Falda Lápiz Cuero', 'Leather Pencil Skirt', 'Faldas', 'Skirts', 250, None,
     'https://placehold.co/600x800/2d2d1b/d4a843?text=Falda%20Lápiz%20Cuero',
     'Falda lápiz en cuero vacuno.', 'Exclusivo', 35),
]

SEED_CATEGORIES = [
    ("Vestidos", "Dresses", "vestidos", "Vestidos elegantes para toda ocasión"),
    ("Sastrería", "Tailoring", "sastreria", "Trajes y blazers sartoriales"),
    ("Faldas", "Skirts", "faldas", "Faldas en todos los largos y estilos"),
    ("Abrigos", "Coats", "abrigos", "Abrigos y gabardinas de temporada"),
    ("Accesorios", "Accessories", "accesorios", "Bolsos, cinturones y complementos"),
    ("Camisas", "Shirts", "camisas", "Camisas en lino, algodón y seda"),
    ("Blusas", "Blouses", "blusas", "Blusas femeninas y elegantes"),
    ("Bodys", "Bodysuits", "bodys", "Bodys en encaje y algodón"),
    ("Jeans", "Jeans", "jeans", "Jeans de todas las siluetas"),
    ("Busos", "Sweatshirts", "busos", "Busos y sweaters casual"),
    ("Blazers", "Blazers", "blazers", "Blazers para toda ocasión"),
]

ORDER_STATUSES = ["Completado", "Completado", "Completado", "Procesando", "Enviado", "Completado", "Completado", "Pendiente"]
SIZES = ["XS", "S", "M", "L", "XL"]


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(Category).count() == 0:
        for c in SEED_CATEGORIES:
            cat = Category(name=c[0], name_en=c[1], slug=c[2], description=c[3])
            db.add(cat)
        db.flush()
        print("✓ Categorías creadas")

    categories = {c.name: c.id for c in db.query(Category).all()}

    admin_email = "arroyaveruizcamilo@gmail.com"
    admin = db.query(User).filter(User.email == admin_email).first()
    if not admin:
        admin = User(
            name="Administrador",
            email=admin_email,
            password_hash=hash_password("camilo2006_RZ@"),
            role="admin",
            email_verified=True,
            phone="+57 300 123 4567",
        )
        db.add(admin)
        db.flush()
        print("✓ Admin creado")

    demo_user = db.query(User).filter(User.email == "demo@gracia.moda").first()
    if not demo_user:
        demo_user = User(
            name="Cliente Demo",
            email="demo@gracia.moda",
            password_hash=hash_password("Demo123!"),
            role="client",
            email_verified=True,
            phone="+57 300 987 6543",
        )
        db.add(demo_user)
        db.flush()
        print("✓ Usuario demo creado")

    if db.query(Product).count() == 0:
        for i, p in enumerate(SEED_PRODUCTS):
            cat_id = categories.get(p[2])
            product = Product(
                name=p[0], name_en=p[1],
                category=p[2], category_en=p[3],
                category_id=cat_id,
                price=p[4], old_price=p[5],
                image=p[6], description=p[7],
                badge=p[8],
                stock=p[9],
                sales_count=random.randint(10, 200),
                views_count=random.randint(100, 5000),
                is_new=p[8] == "Nuevo",
                is_featured=i < 6,
                sku=f"GRC-{i+1:04d}",
                slug=p[0].lower().replace(" ", "-"),
                is_active=True,
                cost_price=round(p[4] * 0.4, 2),
            )
            db.add(product)
            db.flush()

            for size in SIZES:
                db.add(ProductVariant(
                    product_id=product.id,
                    size=size,
                    color="Negro",
                    color_hex="#000000",
                    stock=random.randint(5, 30) if size != "XS" else random.randint(0, 5),
                ))
                db.add(ProductVariant(
                    product_id=product.id,
                    size=size,
                    color="Blanco",
                    color_hex="#FFFFFF",
                    stock=random.randint(3, 20),
                ))
        print("✓ Productos creados")

    if db.query(Address).count() == 0 and demo_user:
        db.add(Address(
            user_id=demo_user.id, label="Principal", full_name="Cliente Demo",
            phone="+57 300 987 6543", street="Carrera 12 # 34-56, Apartamento 702",
            city="Bogotá", state="Cundinamarca", zip_code="110111", is_default=True,
        ))
        print("✓ Direcciones creadas")

    if db.query(Coupon).count() == 0:
        coupons = [
            Coupon(code="BIENVENIDA10", description="10% de descuento primera compra",
                   discount_type="percentage", discount_value=10, usage_limit=100, min_purchase=100),
            Coupon(code="GRACIA20", description="20% en prendas seleccionadas",
                   discount_type="percentage", discount_value=20, usage_limit=50, min_purchase=200,
                   max_discount=80,
                   expires_at=datetime.now(timezone.utc) + timedelta(days=90)),
        ]
        for c in coupons:
            db.add(c)
        print("✓ Cupones creados")

    if db.query(Banner).count() == 0:
        banners = [
            Banner(title="Colección Otoño-Invierno 2026",
                   subtitle="Descubre la nueva temporada",
                   image_url="https://placehold.co/1600x600/1a1a1a/d4a843?text=Colección+2026",
                   link_url="/", sort_order=1, is_active=True),
            Banner(title="Noche Áurea", subtitle="Looks de gala para ocasiones especiales",
                   image_url="https://placehold.co/1600x600/2a1a1a/d4a843?text=Noche+Áurea",
                   link_url="/", sort_order=2, is_active=True),
        ]
        for b in banners:
            db.add(b)
        print("✓ Banners creados")

    if db.query(Order).count() == 0 and demo_user:
        for i in range(12):
            d = datetime.now(timezone.utc) - timedelta(days=i, hours=random.randint(0, 11))
            subtotal = round(150 + random.random() * 600, 2)
            total = round(subtotal * 1.19, 2)
            st = ORDER_STATUSES[i % len(ORDER_STATUSES)]
            order = Order(
                user_id=demo_user.id,
                order_number=f"GRC-{1000+i}",
                subtotal=subtotal,
                tax=round(subtotal * 0.19, 2),
                total=total,
                status=st,
                payment_method="credit_card",
                payment_status="completed" if st != "Pendiente" else "pending",
                shipping_cost=random.choice([0, 15, 25]),
                created_at=d,
            )
            db.add(order)
            db.flush()

            db.add(OrderTimeline(order_id=order.id, status=st,
                                 note=f"Orden {st}", created_by="system", created_at=d))

            for _ in range(random.randint(1, 3)):
                product = db.query(Product).order_by(func.random()).first()
                if product:
                    db.add(OrderItem(
                        order_id=order.id, product_id=product.id,
                        product_name=product.name,
                        quantity=random.randint(1, 2), price=product.price,
                    ))
        print("✓ Órdenes seed creadas")

    if db.query(Review).count() == 0:
        reviews_data = [
            (1, 5, "Espectacular", "La seda es increíble"),
            (2, 5, "Blazer perfecto", "La calidad de la lana es insuperable"),
            (4, 4, "Muy buena gabardina", "Excelente material"),
            (5, 5, "Bolso hermoso", "El cuero es de primera calidad"),
        ]
        for p_id, rating, title, comment in reviews_data:
            product = db.query(Product).filter(Product.id == p_id).first()
            if product and demo_user:
                db.add(Review(
                    product_id=p_id, user_id=demo_user.id,
                    rating=rating, title=title, comment=comment, is_approved=True
                ))
        print("✓ Reseñas creadas")

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_database()
    print("✦ Base de datos inicializada completamente")
