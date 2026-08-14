const API_BASE = '/api';

const api = {
  async request(method, path, body = null, token = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Error del servidor');
    return data;
  },

  // Auth
  login(email, pwd) { return this.request('POST', '/auth/login', { email, password: pwd }); },
  register(name, email, pwd, phone) { return this.request('POST', '/auth/register', { name, email, password: pwd, phone }); },
  me(token) { return this.request('GET', '/auth/me', null, token); },

  // Profile
  getProfile(token) { return this.request('GET', '/users/profile', null, token); },
  updateProfile(data, token) { return this.request('PUT', '/users/profile', data, token); },

  // Addresses
  getAddresses(token) { return this.request('GET', '/users/addresses', null, token); },
  createAddress(data, token) { return this.request('POST', '/users/addresses', data, token); },
  deleteAddress(id, token) { return this.request('DELETE', `/users/addresses/${id}`, null, token); },

  // Cart (persistent)
  getCart(token) { return this.request('GET', '/users/cart', null, token); },
  addToCart(data, token) { return this.request('POST', '/users/cart', data, token); },
  updateCartItem(id, data, token) { return this.request('PUT', `/users/cart/${id}`, data, token); },
  removeCartItem(id, token) { return this.request('DELETE', `/users/cart/${id}`, null, token); },
  clearCart(token) { return this.request('DELETE', '/users/cart', null, token); },

  // Wishlist
  getWishlist(token) { return this.request('GET', '/users/wishlist', null, token); },
  addWishlist(pid, token) { return this.request('POST', `/users/wishlist/${pid}`, null, token); },
  removeWishlist(pid, token) { return this.request('DELETE', `/users/wishlist/${pid}`, null, token); },

  // User orders
  getUserOrders(token) { return this.request('GET', '/users/orders', null, token); },

  // Notifications
  getNotifications(token) { return this.request('GET', '/users/notifications', null, token); },
  markNotifRead(id, token) { return this.request('PUT', `/users/notifications/${id}/read`, null, token); },

  // Products
  getProducts(cat = '', search = '', featured = '') {
    const p = new URLSearchParams();
    if (cat) p.set('category', cat);
    if (search) p.set('search', search);
    if (featured) p.set('featured', 'true');
    const qs = p.toString();
    return this.request('GET', `/products${qs ? '?' + qs : ''}`);
  },
  getProduct(id) { return this.request('GET', `/products/${id}`); },
  createProduct(d, t) { return this.request('POST', '/products', d, t); },
  updateProduct(id, d, t) { return this.request('PUT', `/products/${id}`, d, t); },
  deleteProduct(id, t) { return this.request('DELETE', `/products/${id}`, null, t); },

  // Orders
  createOrder(d, token = null) { return this.request('POST', '/orders', d, token); },
  getOrders(t) { return this.request('GET', '/orders', null, t); },
  getOrder(id, t) { return this.request('GET', `/orders/${id}`, null, t); },
  updateOrderStatus(id, d, t) { return this.request('PUT', `/orders/${id}/status`, d, t); },
  updateTracking(id, d, t) { return this.request('PUT', `/orders/${id}/tracking`, d, t); },
  trackOrder(id, email) { return this.request('GET', `/orders/track/${id}?email=${encodeURIComponent(email)}`); },

  // Coupons
  getCoupons(t) { return this.request('GET', '/coupons', null, t); },
  createCoupon(d, t) { return this.request('POST', '/coupons', d, t); },
  toggleCoupon(id, t) { return this.request('PUT', `/coupons/${id}/toggle`, null, t); },
  deleteCoupon(id, t) { return this.request('DELETE', `/coupons/${id}`, null, t); },
  validateCoupon(code, total) { return this.request('POST', '/coupons/validate', { code, cart_total: total }); },

  // Messages
  sendMessage(d) { return this.request('POST', '/messages', d); },
  getMessages(t) { return this.request('GET', '/messages', null, t); },

  // FAQs
  getFAQs() { return this.request('GET', '/faqs'); },
  getAllFAQs(t) { return this.request('GET', '/faqs/all', null, t); },
  createFAQ(d, t) { return this.request('POST', '/faqs', d, t); },
  updateFAQ(id, d, t) { return this.request('PUT', `/faqs/${id}`, d, t); },
  deleteFAQ(id, t) { return this.request('DELETE', `/faqs/${id}`, null, t); },
  toggleFAQ(id, t) { return this.request('PUT', `/faqs/${id}/toggle`, null, t); },

  // Analytics
  getDashboard(t) { return this.request('GET', '/analytics/dashboard', null, t); },
  getSales(t) { return this.request('GET', '/analytics/sales', null, t); },
  getTopProducts(t) { return this.request('GET', '/analytics/products', null, t); },

  // Live Chat
  createConversation(d, t) { return this.request('POST', '/chat/conversations', d, t); },
  createGuestConversation(d) { return this.request('POST', '/chat/conversations/guest', d); },
  getConversations(t) { return this.request('GET', '/chat/conversations', null, t); },
  getConversationMessages(id, t) { return this.request('GET', `/chat/conversations/${id}/messages`, null, t); },
  sendChatMessage(id, d, t) { return this.request('POST', `/chat/conversations/${id}/messages`, d, t); },
  markChatRead(id, t) { return this.request('POST', `/chat/conversations/${id}/read`, null, t); },
  // Admin Chat
  adminGetConversations(t) { return this.request('GET', '/chat/admin/conversations', null, t); },
  adminGetAllConversations(t) { return this.request('GET', '/chat/admin/conversations/all', null, t); },
  adminGetMessages(id, t) { return this.request('GET', `/chat/admin/conversations/${id}/messages`, null, t); },
  adminReply(id, d, t) { return this.request('POST', `/chat/admin/conversations/${id}/reply`, d, t); },
  adminCloseConversation(id, t) { return this.request('POST', `/chat/admin/conversations/${id}/close`, null, t); },
  adminMarkRead(id, t) { return this.request('POST', `/chat/admin/conversations/${id}/read`, null, t); },

  // Payments
  createPreference(d) { return this.request('POST', '/payments/create-preference', d); },
  simulatePayment(id, t) { return this.request('POST', `/payments/simulate/${id}`, null, t); },
  getPaymentMethods() { return this.request('GET', '/payments/methods'); },
  getPaymentStatus(id) { return this.request('GET', `/payments/status/${id}`); },
  getPaymentReceipt(id) { return this.request('GET', `/payments/receipt/${id}`); },

  // Upload
  async uploadImage(file, token) {
    const form = new FormData();
    form.append('file', file);
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', headers, body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al subir');
    return data;
  },
};
