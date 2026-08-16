from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, Enum as SqlEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    client = "client"
    user = "user"


class OrderStatus(str, enum.Enum):
    pending = "Pendiente"
    processing = "Procesando"
    shipped = "Enviado"
    delivered = "Entregado"
    cancelled = "Cancelado"
    confirmed = "Confirmado"
    completed = "Completado"


class PaymentStatus(str, enum.Enum):
    pending = "Pendiente"
    paid = "Pagado"
    failed = "Fallido"
    refunded = "Reembolsado"
    completed = "Completado"


# ===== USERS =====
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(50), default="")
    role = Column(String(20), default=UserRole.client.value)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    two_factor_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    orders = relationship("Order", back_populates="user")
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    wishlist = relationship("Wishlist", back_populates="user", cascade="all, delete-orphan")
    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


# ===== ADDRESSES =====
class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(100), default="")
    phone = Column(String(50), default="")
    street = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), default="")
    zip_code = Column(String(20), default="")
    label = Column(String(50), default="")
    full_name = Column(String(100), default="")
    country = Column(String(100), default="Colombia")
    is_default = Column(Boolean, default=False)

    user = relationship("User", back_populates="addresses")
    orders = relationship("Order", back_populates="address")


# ===== PRODUCTS =====
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    name_en = Column(String(200), default="")
    description = Column(Text, default="")
    description_en = Column(Text, default="")
    price = Column(Float, nullable=False)
    old_price = Column(Float, nullable=True)
    category = Column(String(50), nullable=False)
    category_en = Column(String(50), default="")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    stock = Column(Integer, default=0)
    image = Column(String(500), default="")
    images = Column(JSON, default=list)
    status = Column(String(20), default="active")
    featured = Column(Boolean, default=False)
    is_new = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    badge = Column(String(50), default="")
    badge_color = Column(String(20), default="")
    materials = Column(Text, default="")
    care_instructions = Column(Text, default="")
    delivery_time = Column(String(100), default="")
    sales_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    sku = Column(String(100), default="")
    slug = Column(String(200), default="")
    size_guide = Column(JSON, default=dict)
    cost_price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    order_items = relationship("OrderItem", back_populates="product")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    product_images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan",
                                  order_by="ProductImage.sort_order")
    category_rel = relationship("Category", back_populates="products")
    collection = relationship("Collection", back_populates="products")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    size = Column(String(20), default="")
    color = Column(String(50), default="")
    color_hex = Column(String(7), default="#000000")
    sku = Column(String(100), default="")
    stock = Column(Integer, default=0)
    price_override = Column(Float, nullable=True)
    image = Column(String(500), default="")

    product = relationship("Product", back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(String(500), nullable=False)
    sort_order = Column(Integer, default=0)

    product = relationship("Product", back_populates="product_images")


# ===== CATEGORIES =====
class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100), default="")
    slug = Column(String(100), default="")
    description = Column(Text, default="")
    image = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    products = relationship("Product", back_populates="category_rel")


# ===== COLLECTIONS =====
class Collection(Base):
    __tablename__ = "collections"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100), default="")
    slug = Column(String(100), default="")
    description = Column(Text, default="")
    image = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    products = relationship("Product", back_populates="collection")


# ===== CART =====
class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    quantity = Column(Integer, default=1)
    size = Column(String(20), default="")
    color = Column(String(50), default="")
    saved_for_later = Column(Boolean, default=False)

    user = relationship("User", back_populates="cart_items")
    product = relationship("Product")


# ===== WISHLIST =====
class Wishlist(Base):
    __tablename__ = "wishlist"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="wishlist")
    product = relationship("Product")


# ===== ORDERS =====
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    order_number = Column(String(50), default="")
    customer_name = Column(String(100), default="")
    customer_email = Column(String(100), default="")
    customer_phone = Column(String(50), default="")
    shipping_address = Column(Text, default="")
    shipping_city = Column(String(100), default="")
    shipping_state = Column(String(100), default="")
    shipping_zip = Column(String(20), default="")
    shipping_cost = Column(Float, default=0.0)
    coupon_code = Column(String(50), default="")
    discount = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    status = Column(String(50), default=OrderStatus.pending.value)
    payment_status = Column(String(50), default=PaymentStatus.pending.value)
    payment_method = Column(String(50), default="")
    payment_id = Column(String(255), default="")
    tracking_number = Column(String(255), default="")
    notes = Column(Text, default="")
    delivered_at = Column(DateTime, nullable=True)
    stock_released = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="orders")
    address = relationship("Address", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    timeline = relationship("OrderTimeline", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(200), default="")
    variant_size = Column(String(20), default="")
    variant_color = Column(String(50), default="")
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0.0)
    size = Column(String(20), default="")
    image = Column(String(500), default="")

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class OrderTimeline(Base):
    __tablename__ = "order_timeline"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    status = Column(String(50), default="")
    note = Column(Text, default="")
    created_by = Column(String(100), default="system")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    order = relationship("Order", back_populates="timeline")


# ===== COUPONS =====
class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    discount_type = Column(String(20), default="percentage")
    discount_value = Column(Float, default=0.0)
    min_purchase = Column(Float, default=0.0)
    usage_limit = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    description = Column(Text, default="")
    max_discount = Column(Float, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


# ===== NOTIFICATIONS =====
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    type = Column(String(50), default="info")
    title = Column(String(200), default="")
    body = Column(Text, default="")
    data = Column(JSON, default=dict)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="notifications")


# ===== FAQ =====
class FAQ(Base):
    __tablename__ = "faqs"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(String(255), nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(50), default="general")
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True)


# ===== BANNERS =====
class Banner(Base):
    __tablename__ = "banners"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), default="")
    subtitle = Column(String(200), default="")
    image_url = Column(String(500), default="")
    link_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)


# ===== REVIEWS =====
class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_item_id = Column(Integer, nullable=True)
    rating = Column(Integer, default=5)
    title = Column(String(200), default="")
    comment = Column(Text, default="")
    images = Column(JSON, default=list)
    helpful_count = Column(Integer, default=0)
    is_approved = Column(Boolean, default=True)
    is_reported = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User")
    product = relationship("Product")


# ===== NEWSLETTER SUBSCRIBERS =====
class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


# ===== ACTIVITY LOG =====
class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(50), default="")
    details = Column(Text, default="")
    ip_address = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


# ===== CONVERSATIONS (Live Chat) =====
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    guest_name = Column(String(100), default="")
    guest_email = Column(String(100), default="")
    guest_token = Column(String(128), nullable=True, index=True)
    subject = Column(String(200), default="")
    status = Column(String(20), default="active")
    unread_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id])
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="ChatMessage.created_at")


# ===== CHAT MESSAGES (Live Chat) =====
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_admin = Column(Boolean, default=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    read = Column(Boolean, default=False)

    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_id])


# ===== CONTACT FORM MESSAGES =====
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="")
    email = Column(String(100), default="")
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


# ===== PAYMENT TRANSACTIONS =====
class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    transaction_id = Column(String(255), default="")
    payment_method = Column(String(50), default="")
    amount = Column(Float, default=0.0)
    status = Column(String(50), default="")
    payer_email = Column(String(255), default="")
    extra_data = Column(Text, default="")
    raw_response = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    order = relationship("Order")


# ===== LOGS =====
class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
