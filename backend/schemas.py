from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ===== AUTH =====
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    phone: str = ""


class UserLogin(BaseModel):
    email: str
    password: str
    recaptcha_token: str = ""
    captcha_token: str = ""
    captcha_answer: int = 0


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
    requires_2fa: bool = False
    temp_token: str = ""


class TwoFactorSetup(BaseModel):
    secret: str
    qr_url: str
    backup_codes: list[str]


class TwoFactorVerify(BaseModel):
    code: str


class TwoFactorLoginRequest(BaseModel):
    temp_token: str
    code: str


# ===== ADDRESSES =====
class AddressCreate(BaseModel):
    name: str = ""
    phone: str = ""
    street: str
    city: str
    state: str = ""
    zip_code: str = ""
    label: str = ""
    full_name: str = ""
    country: str = "Colombia"
    is_default: bool = False


class AddressOut(BaseModel):
    id: int
    name: str
    phone: str
    street: str
    city: str
    state: str
    zip_code: str
    is_default: bool

    class Config:
        from_attributes = True


# ===== PRODUCTS =====
class VariantCreate(BaseModel):
    size: str = ""
    color: str = ""
    color_hex: str = "#000000"
    sku: str = ""
    stock: int = 0
    price_override: Optional[float] = None
    image: str = ""


class VariantOut(BaseModel):
    id: int
    size: str
    color: str
    color_hex: str
    sku: str
    stock: int
    price_override: Optional[float] = None
    image: str

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    price: float
    old_price: Optional[float] = None
    category: str
    stock: int = 0
    image: str = ""
    featured: bool = False
    variants: list[VariantCreate] = []
    images: list[str] = []


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    price: float
    old_price: Optional[float] = None
    category: str
    stock: int
    image: str
    status: str
    featured: bool
    variants: list[VariantOut] = []
    images: list[str] = []

    class Config:
        from_attributes = True


# ===== CART =====
class CartItemCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class CartItemOut(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    product_name: str = ""
    product_price: float = 0.0
    product_image: str = ""
    variant_size: str = ""
    variant_color: str = ""
    stock: int = 0

    class Config:
        from_attributes = True


class CartAddRequest(BaseModel):
    product_id: int
    size: str = ""
    color: str = ""
    quantity: int = 1


class CartUpdateRequest(BaseModel):
    id: int
    quantity: int


class CartRemoveRequest(BaseModel):
    id: int


class CartSaveForLaterRequest(BaseModel):
    id: int
    saved: bool = True


class ApplyCouponRequest(BaseModel):
    code: str
    subtotal: float = 0.0


# ===== ORDERS =====
class OrderItemCreate(BaseModel):
    product_id: int
    variant_size: str = ""
    variant_color: str = ""
    quantity: int = 1
    price: float = 0.0


class OrderCreate(BaseModel):
    customer_email: str
    customer_name: str = ""
    customer_phone: str = ""
    shipping_address: str = ""
    shipping_city: str = ""
    shipping_state: str = ""
    shipping_zip: str = ""
    shipping_cost: float = 0.0
    coupon_code: str = ""
    subtotal: float = 0.0
    total: float = 0.0
    discount: float = 0.0
    payment_method: str = "mercadopago"
    payment_id: str = ""
    notes: str = ""
    items: list[OrderItemCreate]


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_email: str
    customer_phone: str
    shipping_address: str
    shipping_city: str
    shipping_state: str
    shipping_zip: str
    shipping_cost: float
    coupon_code: str
    discount: float
    subtotal: float
    total: float
    status: str
    payment_status: str
    payment_method: str
    payment_id: str
    tracking_number: str
    notes: str
    created_at: datetime
    items: list = []

    class Config:
        from_attributes = True


# ===== WISHLIST =====
class WishlistOut(BaseModel):
    id: int
    product_id: int
    product_name: str = ""
    product_price: float = 0.0
    product_image: str = ""

    class Config:
        from_attributes = True


# ===== COUPONS =====
class CouponCreate(BaseModel):
    code: str
    discount_type: str = "percentage"
    discount_value: float = 0.0
    min_purchase: float = 0.0
    usage_limit: int = 0
    expires_at: Optional[str] = None


class CouponOut(BaseModel):
    id: int
    code: str
    discount_type: str
    discount_value: float
    min_purchase: float
    usage_limit: int
    used_count: int
    is_active: bool
    expires_at: Optional[str] = None

    class Config:
        from_attributes = True


# ===== NOTIFICATIONS =====
class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===== FAQ =====
class FAQCreate(BaseModel):
    question: str
    answer: str
    category: str = "general"
    sort_order: int = 0


class FAQOut(BaseModel):
    id: int
    question: str
    answer: str
    category: str
    sort_order: int
    active: bool

    class Config:
        from_attributes = True


# ===== MESSAGES =====
class MessageCreate(BaseModel):
    name: str = ""
    email: str = ""
    message: str


class MessageOut(BaseModel):
    id: int
    name: str
    email: str
    message: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===== CHAT / CONVERSATIONS =====
class ConversationCreate(BaseModel):
    guest_name: str = ""
    guest_email: str = ""
    subject: str = ""
    message: str


class ConversationOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    guest_name: str
    guest_email: str
    subject: str
    status: str
    unread_count: int
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    conversation_id: int
    message: str


class ChatMessageOut(BaseModel):
    id: int
    conversation_id: int
    user_id: Optional[int] = None
    is_admin: bool
    admin_id: Optional[int] = None
    message: str
    created_at: datetime
    read: bool
    sender_name: str = ""

    class Config:
        from_attributes = True


# ===== MERCADOPAGO =====
class PaymentIntent(BaseModel):
    order_id: int
    payment_method: str = "mercadopago"


class PaymentResponse(BaseModel):
    init_point: str = ""
    payment_id: str = ""
    status: str = ""


# ===== ADMIN =====
class OrderStatusRequest(BaseModel):
    id: int
    status: str
    note: str = ""


class NotifSendRequest(BaseModel):
    type: str = "info"
    title: str
    body: str = ""


class ProductCreateRequest(BaseModel):
    name: str
    description: str = ""
    price: float
    category: str
    stock: int = 0
    image: str = ""


class CategoryRequest(BaseModel):
    name: str
    name_en: str = ""
    slug: str = ""
    description: str = ""
    image: str = ""
    is_active: bool = True
    sort_order: int = 0


class CollectionRequest(BaseModel):
    name: str
    name_en: str = ""
    slug: str = ""
    description: str = ""
    image: str = ""
    is_active: bool = True
    is_featured: bool = False


# ===== REVIEWS =====
class ReviewRequest(BaseModel):
    product_id: int
    order_item_id: Optional[int] = None
    rating: int = 5
    title: str = ""
    comment: str = ""
    images: list[str] = []


# ===== BANNERS / NEWSLETTER =====
class NewsletterRequest(BaseModel):
    email: str
