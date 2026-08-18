const state = {
  token: localStorage.getItem('token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  products: [], orders: [], messages: [],
  tempToken: null,
  pendingUser: null,
  recaptchaKey: null,
  recaptchaReady: false,
};

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const fmt = n => '$' + Number(n).toFixed(2);

const PAGE_TITLES = {
  dashboard: 'Dashboard',
  products: 'Productos',
  orders: 'Pedidos',
  chat: 'Chat',
  messages: 'Mensajes',
  customers: 'Clientes',
  catalog: 'Catálogo',
  marketing: 'Marketing',
  faqs: 'FAQs',
  reviews: 'Reseñas',
  analytics: 'Analíticas',
  security: 'Seguridad',
};

// ===== AUTO-LOGOUT POR INACTIVIDAD (30 min) =====
const SESSION_TIMEOUT_MS = (parseInt(sessionStorage.getItem('session_timeout') || '0') || 30) * 60 * 1000;
let _inactivityTimer = null;
let _warningTimer = null;

function resetInactivityTimer() {
  clearTimeout(_inactivityTimer);
  clearTimeout(_warningTimer);

  // Warning at 25 minutes
  _warningTimer = setTimeout(() => {
    if (state.token) {
      const remaining = Math.ceil((SESSION_TIMEOUT_MS - 25 * 60 * 1000) / 60000);
      const toast = document.createElement('div');
      toast.className = 'admin-toast';
      toast.id = 'session-warning-toast';
      toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:99999;background:var(--warning);color:#000;padding:14px 28px;border-radius:10px;font-size:.85rem;font-weight:600;box-shadow:0 8px 32px rgba(0,0,0,.3);display:flex;align-items:center;gap:10px;animation:fadeIn .3s ease';
      toast.innerHTML = `<i class="fas fa-clock"></i> Tu sesión expira en ${remaining} min por inactividad. <button onclick="this.parentElement.remove();resetInactivityTimer()" style="background:#000;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:700;font-size:.75rem">Extender</button>`;
      document.body.appendChild(toast);
    }
  }, SESSION_TIMEOUT_MS - 5 * 60 * 1000); // 5 min before expiry

  // Auto-logout
  _inactivityTimer = setTimeout(() => {
    if (state.token) {
      document.getElementById('session-warning-toast')?.remove();
      showToast('Sesión expirada por inactividad');
      setTimeout(() => logout(), 1000);
    }
  }, SESSION_TIMEOUT_MS);
}

function startInactivityTracking() {
  ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach(evt => {
    document.addEventListener(evt, resetInactivityTimer, { passive: true });
  });
  resetInactivityTimer();
}

function stopInactivityTracking() {
  clearTimeout(_inactivityTimer);
  clearTimeout(_warningTimer);
  document.removeEventListener('click', resetInactivityTimer);
  document.removeEventListener('keydown', resetInactivityTimer);
  document.removeEventListener('mousemove', resetInactivityTimer);
  document.removeEventListener('scroll', resetInactivityTimer);
  document.removeEventListener('touchstart', resetInactivityTimer);
}

function showPage(id) {
  $$('.page-section').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(`page-${id}`);
  if (page) page.classList.add('active');
  $$('.sidebar nav a').forEach(a => a.classList.toggle('active', a.dataset.page === id));
  const titled = page?.querySelector('.page-title')?.textContent?.trim();
  document.getElementById('page-title').textContent = titled || PAGE_TITLES[id] || 'Dashboard';
}

// ===== AUTH =====
async function loadRecaptchaConfig() {
  try {
    const res = await fetch('/api/config/recaptcha');
    const data = await res.json();
    if (data.site_key) {
      state.recaptchaKey = data.site_key;
      // Load the reCAPTCHA script
      const script = document.createElement('script');
      script.src = `https://www.google.com/recaptcha/api.js?render=explicit`;
      script.async = true;
      script.defer = true;
      script.onload = () => {
        const container = document.getElementById('recaptcha-container');
        if (container) {
          container.style.display = 'block';
          grecaptcha.render('recaptcha-widget', {
            sitekey: data.site_key,
            callback: (token) => { state.recaptchaReady = true; },
            'expired-callback': () => { state.recaptchaReady = false; },
            'error-callback': () => { state.recaptchaReady = false; },
          });
        }
      };
      document.head.appendChild(script);
    }
  } catch (err) {
    // reCAPTCHA config not available — proceed without it
  }
}

function getRecaptchaToken() {
  if (!state.recaptchaKey) return '';
  if (typeof grecaptcha === 'undefined') return '';
  try {
    return grecaptcha.getResponse() || '';
  } catch {
    return '';
  }
}

// ===== VISUAL CAPTCHA =====
async function loadMathCaptcha() {
  const imgWrap = $('#captcha-image-wrap');
  const loading = $('#captcha-loading');
  const label = $('#captcha-label');
  const tokenInput = $('#captcha-token');
  const answerInput = $('#captcha-answer');
  try {
    if (loading) loading.style.display = '';
    if (label) label.textContent = 'Escribi los caracteres que ves:';
    const res = await fetch('/api/auth/captcha');
    const data = await res.json();
    if (data.image_svg && imgWrap) {
      imgWrap.innerHTML = data.image_svg;
      const svg = imgWrap.querySelector('svg');
      if (svg) { svg.style.maxWidth = '100%'; svg.style.height = 'auto'; }
    }
    if (tokenInput && data.token) {
      tokenInput.value = data.token;
    }
    if (answerInput) {
      answerInput.value = '';
      answerInput.focus();
    }
  } catch (err) {
    if (imgWrap) imgWrap.innerHTML = '<span style="font-size:.8rem;color:var(--danger);padding:12px">Error cargando CAPTCHA. Hace clic en refresh.</span>';
    if (label) label.textContent = 'Error cargando verificación';
  }
}

function getCaptchaAnswer() {
  const tokenInput = $('#captcha-token');
  const answerInput = $('#captcha-answer');
  return {
    token: tokenInput ? tokenInput.value : '',
    answer: answerInput ? parseInt(answerInput.value, 10) || 0 : 0,
    answerText: answerInput ? answerInput.value.trim() : '',
  };
}

async function handleLogin(e) {
  e.preventDefault();
  const email = $('#login-email').value;
  const password = $('#login-password').value;
  const errEl = $('#login-error');
  errEl.style.display = 'none';

  // Validate reCAPTCHA if configured
  const recaptchaToken = getRecaptchaToken();
  if (state.recaptchaKey && !recaptchaToken) {
    errEl.textContent = 'Por favor completá la verificación reCAPTCHA.';
    errEl.style.display = 'block';
    return;
  }

  // Validate visual CAPTCHA
  const captcha = getCaptchaAnswer();
  const hasServerToken = !!captcha.token;
  const hasAnswer = captcha.answerText.length > 0;
  if (!hasAnswer) {
    errEl.textContent = 'Por favor completá la verificación.';
    errEl.style.display = 'block';
    return;
  }

  const submitBtn = e.target.querySelector('button[type="submit"]');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Verificando...'; }

  try {
    const res = await api.login(email, password, recaptchaToken, captcha.token, captcha.answer, captcha.answerText);

    if (res.requires_2fa) {
      state.tempToken = res.temp_token || null;
      state.pendingUser = res.user;
      $('#login-page').style.display = 'none';
      $('#twofa-page').style.display = 'flex';
      $('#twofa-code').focus();
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Iniciar Sesión'; }
      return;
    }

    if (res.user.role !== 'admin') {
      errEl.textContent = 'Acceso denegado: no tenés permisos de administrador';
      errEl.style.display = 'block';
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Iniciar Sesión'; }
      if (typeof grecaptcha !== 'undefined' && state.recaptchaKey) {
        try { grecaptcha.reset(); } catch {}
      }
      return;
    }

    state.token = res.access_token; state.user = res.user;
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('user', JSON.stringify(res.user));
    showAdmin();
  } catch (err) {
    let msg = err.message;
    if (msg.includes('423') || msg.includes('bloqueada')) {
      msg = 'Cuenta bloqueada temporalmente por demasiados intentos fallidos. Esperá unos minutos.';
    } else if (msg.includes('429') || msg.includes('Demasiados')) {
      msg = 'Demasiados intentos. Esperá un momento antes de intentar de nuevo.';
    }
    errEl.textContent = msg;
    errEl.style.display = 'block';
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Iniciar Sesión'; }
    // Reset reCAPTCHA so user can try again
    if (typeof grecaptcha !== 'undefined' && state.recaptchaKey) {
      try { grecaptcha.reset(); } catch {}
    }
    // Refresh math CAPTCHA on failure
    loadMathCaptcha();
  }
}

async function handle2faVerify(e) {
  e.preventDefault();
  const code = $('#twofa-code').value;
  const errEl = $('#twofa-error');
  errEl.style.display = 'none';

  const submitBtn = e.target.querySelector('button[type="submit"]');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Verificando...'; }

  try {
    const res = await api.verify2fa(state.tempToken, code);

    state.token = res.access_token;
    state.user = res.user;
    state.tempToken = null;
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('user', JSON.stringify(res.user));

    $('#twofa-page').style.display = 'none';
    showAdmin();
  } catch (err) {
    let msg = err.message;
    if (msg.includes('expirado')) {
      msg = 'El código expiró. Iniciá sesión de nuevo.';
      setTimeout(() => { $('#twofa-page').style.display = 'none'; $('#login-page').style.display = 'flex'; }, 2000);
    }
    errEl.textContent = msg;
    errEl.style.display = 'block';
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Verificar'; }
  }
}

function backToLogin() {
  state.tempToken = null;
  state.pendingUser = null;
  $('#twofa-page').style.display = 'none';
  $('#login-page').style.display = 'flex';
  $('#twofa-code').value = '';
  $('#twofa-error').style.display = 'none';
}

function logout() {
  state.token = null; state.user = null; state.tempToken = null; state.pendingUser = null;
  localStorage.removeItem('token'); localStorage.removeItem('user');
  stopInactivityTracking();
  $('#login-page').style.display = 'flex';
  $('#twofa-page').style.display = 'none';
  $('#admin-app').style.display = 'none';
  $('#login-error').style.display = 'none';
  $('#twofa-error').style.display = 'none';
  // Reset reCAPTCHA for next login
  if (typeof grecaptcha !== 'undefined' && state.recaptchaKey) {
    try { grecaptcha.reset(); } catch {}
  }
}

function showAdmin() {
  $('#login-page').style.display = 'none';
  $('#admin-app').style.display = 'flex';
  $('#admin-user-name').textContent = state.user.name;
  loadDashboard(); loadAdminProducts(); loadAdminOrders(); loadAdminMessages();
  loadCoupons(); loadFAQs(); loadAdminReviews();
  initAdminSocket();
  loadAdminChatConversations();
  startInactivityTracking();

  // Poll for new conversations
  setInterval(() => {
    if (state.token) {
      api.adminGetConversations(state.token).then(convs => {
        const totalUnread = convs.reduce((s, c) => s + (c.unread_count || 0), 0);
        const badge = $('#admin-chat-badge');
        if (badge) {
          if (totalUnread > 0) {
            badge.textContent = totalUnread;
            badge.style.display = 'inline';
          } else {
            badge.style.display = 'none';
          }
        }
      }).catch(() => {});
    }
  }, 10000);
}

// ===== DASHBOARD =====
async function loadDashboard() {
  try {
    const data = await api.getDashboard(state.token);
    $('#stat-orders').textContent = data.total_orders;
    $('#stat-revenue').textContent = fmt(data.total_revenue);
    $('#stat-products').textContent = data.total_products;
    $('#stat-messages').textContent = data.total_messages;

    const tbody = $('#recent-orders tbody');
    if (data.recent_orders?.length) {
      tbody.innerHTML = data.recent_orders.map(o => `<tr>
        <td>#${o.id}</td><td>${o.customer||'—'}</td><td>${fmt(o.total)}</td>
        <td><span class="status-badge status-${o.status.toLowerCase()}">${o.status}</span></td>
        <td>${o.date ? new Date(o.date).toLocaleDateString() : '—'}</td>
      </tr>`).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text2)">Sin pedidos recientes</td></tr>';
    }

    const stockEl = $('#low-stock-warning');
    if (data.low_stock > 0) {
      stockEl.className = 'alert-warn';
      stockEl.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${data.low_stock} producto(s) con stock bajo`;
    } else {
      stockEl.className = 'alert-ok';
      stockEl.innerHTML = '<i class="fas fa-check-circle"></i> Stock normal';
    }
  } catch (err) { console.error(err); }
}

// ===== PRODUCTS with VARIANTS =====
function addVariantRow(size = '', color = '', colorHex = '#000000', stock = 0) {
  const container = $('#variants-container');
  const div = document.createElement('div');
  div.className = 'variant-row';
  div.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 80px 80px 30px;gap:8px;margin-bottom:8px;align-items:center';
  div.innerHTML = `
    <input type="text" class="v-size" value="${size}" placeholder="Talla (S,M,L)">
    <input type="text" class="v-color" value="${color}" placeholder="Color (Negro)">
    <input type="color" class="v-hex" value="${colorHex}">
    <input type="number" class="v-stock" value="${stock}" placeholder="Stock" min="0">
    <button type="button" class="btn btn-sm btn-danger" onclick="this.parentElement.remove()">×</button>
  `;
  container.appendChild(div);
}

function addImageInput(url = '') {
  const container = $('#images-container');
  const div = document.createElement('div');
  div.style.cssText = 'display:flex;gap:8px;margin-bottom:8px;align-items:center';
  div.innerHTML = `
    <input type="text" class="img-url" value="${url}" placeholder="URL de imagen" style="flex:1">
    <button type="button" class="btn btn-sm btn-danger" onclick="this.parentElement.remove()">×</button>
  `;
  container.appendChild(div);
}

async function uploadImage() {
  const fileInput = $('#image-upload-input');
  const files = fileInput.files;
  if (!files?.length) return;
  for (const file of files) {
    try {
      const res = await api.uploadImage(file, state.token);
      addImageInput(res.url);
      showToast('Imagen subida');
    } catch (err) { showToast(err.message); }
  }
  fileInput.value = '';
}

async function uploadMainImage() {
  const fileInput = $('#main-image-upload-input');
  if (!fileInput.files?.length) return;
  try {
    const res = await api.uploadImage(fileInput.files[0], state.token);
    $('#product-form-image').value = res.url;
    $('#product-image-preview').innerHTML = `<img src="${res.url}" alt="Vista previa">`;
    fileInput.value = '';
    showToast('Imagen principal subida');
  } catch (err) { showToast(err.message); }
}

function openProductForm(data = null) {
  const f = $('#product-form-element');
  f.reset();
  $('#product-form-id').value = data ? data.id : '';
  $('#product-form-name').value = data ? data.name : '';
  $('#product-form-description').value = data ? data.description : '';
  $('#product-form-price').value = data ? data.price : '';
  $('#product-form-old-price').value = data ? (data.old_price || '') : '';
  $('#product-form-category').value = data ? data.category : 'Vestidos';
  $('#product-form-stock').value = data ? data.stock : 10;
  $('#product-form-image').value = data ? data.image : '';
  $('#product-form-featured').checked = data ? data.featured : false;
  $('#product-modal-title').textContent = data ? 'Editar Producto' : 'Nuevo Producto';

  // Variants
  const vc = $('#variants-container');
  vc.innerHTML = '';
  if (data?.variants?.length) {
    data.variants.forEach(v => addVariantRow(v.size, v.color, v.color_hex, v.stock));
  }

  // Images
  const ic = $('#images-container');
  ic.innerHTML = '';
  if (data?.images?.length) {
    data.images.forEach(u => addImageInput(u));
  }

  // Preview current image
  if (data?.image) {
    $('#product-image-preview').innerHTML = `<img src="${data.image}" alt="Vista previa">`;
  } else {
    $('#product-image-preview').innerHTML = '';
  }

  $('#product-modal').classList.add('open');
}

function closeProductForm() { $('#product-modal').classList.remove('open'); }

async function saveProduct(e) {
  e.preventDefault();
  const id = $('#product-form-id').value;
  const variants = [...$$('#variants-container .variant-row')].map(row => ({
    size: row.querySelector('.v-size').value,
    color: row.querySelector('.v-color').value,
    color_hex: row.querySelector('.v-hex').value,
    stock: parseInt(row.querySelector('.v-stock').value) || 0,
    sku: '', price_override: null, image: '',
  }));
  const images = [...$$('#images-container .img-url')].map(inp => inp.value).filter(Boolean);
  const data = {
    name: $('#product-form-name').value,
    description: $('#product-form-description').value,
    price: parseFloat($('#product-form-price').value),
    old_price: $('#product-form-old-price').value ? parseFloat($('#product-form-old-price').value) : null,
    category: $('#product-form-category').value,
    stock: parseInt($('#product-form-stock').value),
    image: $('#product-form-image').value,
    featured: $('#product-form-featured').checked,
    variants, images,
  };
  try {
    if (id) { await api.updateProduct(parseInt(id), data, state.token); }
    else { await api.createProduct(data, state.token); }
    showToast('Producto guardado');
    closeProductForm();
    loadAdminProducts();
  } catch (err) { showToast(err.message); }
}

async function loadAdminProducts() {
  try {
    state.products = await api.getAdminProducts(state.token);
    const tbody = $('#products-table tbody');
    if (!state.products.length) { tbody.innerHTML = '<tr><td colspan="9" style="color:var(--text2)">Sin productos</td></tr>'; return; }
    tbody.innerHTML = state.products.map(p => {
      const active = p.status !== 'inactive';
      const varStock = (p.variants || [])
        .filter(v => v.size || v.color)
        .map(v => `${escapeHtml(v.size||'—')}${v.color?':'+escapeHtml(v.color.slice(0,1)):''}=${v.stock}`)
        .join(', ');
      return `<tr style="${active ? '' : 'opacity:.5'}">
      <td>${p.id}</td>
      <td><img src="${p.image||'https://via.placeholder.com/40'}" style="width:40px;height:50px;object-fit:cover"></td>
      <td>${escapeHtml(p.name)} ${active ? '' : '<span style="color:var(--danger);font-size:.7rem">(inactivo)</span>'}</td>
      <td>${fmt(p.price)}</td><td>${escapeHtml(p.category)}</td>
      <td>${p.stock} ${varStock ? `<span style="font-size:.65rem;color:var(--text2);display:block">${varStock}</span>` : ''}</td>
      <td>${p.variants?.length || 0} vars</td>
      <td><span style="color:${active?'var(--success)':'var(--danger)'}">${active?'Activo':'Inactivo'}</span></td>
      <td style="white-space:nowrap">
        <button class="btn btn-sm btn-warning" onclick="openProductForm(state.products.find(x=>x.id===${p.id}))" style="margin-right:4px"><i class="fas fa-edit"></i></button>
        ${active
          ? `<button class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id})"><i class="fas fa-trash"></i></button>`
          : `<button class="btn btn-sm btn-success" onclick="activateProduct(${p.id})"><i class="fas fa-power-off"></i></button>`}
      </td>
    </tr>`;
    }).join('');
  } catch (err) { console.error(err); }
}

async function activateProduct(id) {
  try {
    await api.adminActivateProduct(id, state.token);
    showToast('Producto reactivado');
    loadAdminProducts();
  } catch (err) { showToast(err.message); }
}

async function deleteProduct(id) {
  if (!confirm('¿Desactivar producto?')) return;
  try { await api.deleteProduct(id, state.token); showToast('Producto desactivado'); loadAdminProducts(); }
  catch (err) { showToast(err.message); }
}

// ===== ORDERS =====
async function loadAdminOrders() {
  try {
    state.orders = await api.getOrders(state.token);
    const tbody = $('#orders-table tbody');
    if (!state.orders.length) { tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text2)">Sin pedidos</td></tr>'; return; }
    tbody.innerHTML = state.orders.map(o => `<tr>
      <td>#${o.id}</td><td>${escapeHtml(o.customer_name||'—')}</td><td>${escapeHtml(o.customer_email||'—')}</td>
      <td>${fmt(o.total)}</td>
      <td><span class="status-badge status-${(o.status||'').toLowerCase()}">${escapeHtml(o.status)}</span></td>
      <td><span class="status-badge" style="background:${o.payment_status==='Pagado'?'var(--success)':'var(--warning)'};color:#fff">${escapeHtml(o.payment_status)}</span></td>
      <td>
        <select onchange="updateOrderStatus(${o.id}, this.value)" style="background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 8px;font-size:.75rem">
          ${['Pendiente','Procesando','Enviado','Entregado','Cancelado'].map(s =>
            `<option value="${s}" ${o.status===s?'selected':''}>${s}</option>`
          ).join('')}
        </select>
        <input type="text" placeholder="Tracking #" value="${escapeHtml(o.tracking_number||'')}" style="width:100px;margin-top:4px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px;font-size:.7rem" onchange="api.updateTracking(${o.id},{tracking_number:this.value},state.token).catch(()=>{})">
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

async function updateOrderStatus(id, status) {
  try { await api.updateOrderStatus(id, {status}, state.token); showToast('Estado actualizado'); loadAdminOrders(); loadDashboard(); }
  catch (err) { showToast(err.message); }
}

// ===== MESSAGES =====
async function loadAdminMessages() {
  try {
    const msgs = await api.getMessages(state.token);
    const tbody = $('#messages-table tbody');
    if (!msgs.length) { tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text2)">Sin mensajes</td></tr>'; return; }
    tbody.innerHTML = msgs.map(m => `<tr>
      <td>${escapeHtml(m.name||'—')}</td><td>${escapeHtml(m.email||'—')}</td>
      <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(m.message)}</td>
      <td>${m.created_at?new Date(m.created_at).toLocaleDateString():'—'}</td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

// ===== COUPONS =====
async function loadCoupons() {
  try {
    const coupons = await api.getCoupons(state.token);
    const tbody = $('#coupons-table tbody');
    if (!coupons.length) { tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text2)">Sin cupones</td></tr>'; return; }
    tbody.innerHTML = coupons.map(c => `<tr>
      <td style="font-weight:700;font-family:monospace">${c.code}</td>
      <td>${c.discount_type==='percentage' ? c.discount_value+'%' : fmt(c.discount_value)}</td>
      <td>${fmt(c.min_purchase)}</td>
      <td>${c.used_count}/${c.usage_limit||'∞'}</td>
      <td>${c.expires_at?new Date(c.expires_at).toLocaleDateString():'—'}</td>
      <td><span style="color:${c.is_active?'var(--success)':'var(--danger)'}">${c.is_active?'Activo':'Inactivo'}</span></td>
      <td>
        <button class="btn btn-sm ${c.is_active?'btn-warning':'btn-success'}" onclick="toggleCoupon(${c.id})">${c.is_active?'Desactivar':'Activar'}</button>
        <button class="btn btn-sm btn-danger" onclick="deleteCoupon(${c.id})"><i class="fas fa-trash"></i></button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

async function createCoupon(e) {
  e.preventDefault();
  const data = {
    code: $('#coupon-code').value,
    discount_type: $('#coupon-type').value,
    discount_value: parseFloat($('#coupon-value').value) || 0,
    min_purchase: parseFloat($('#coupon-min').value) || 0,
    usage_limit: parseInt($('#coupon-uses').value) || 0,
    expires_at: $('#coupon-expires').value || null,
  };
  try { await api.createCoupon(data, state.token); showToast('Cupón creado'); loadCoupons(); e.target.reset(); }
  catch (err) { showToast(err.message); }
}

async function toggleCoupon(id) {
  try { await api.toggleCoupon(id, state.token); loadCoupons(); }
  catch (err) { showToast(err.message); }
}

async function deleteCoupon(id) {
  if (!confirm('¿Eliminar cupón?')) return;
  try { await api.deleteCoupon(id, state.token); showToast('Cupón eliminado'); loadCoupons(); }
  catch (err) { showToast(err.message); }
}

// ===== REVIEWS =====
function reviewStars(n) {
  return '<span style="color:#e6b91e">' + Array.from({ length: 5 }, (_, i) => `<i class="fas fa-star${i < n ? '' : '-o'}"></i>`).join('') + '</span>';
}

async function loadAdminReviews() {
  try {
    const reviews = await api.adminGetReviews(state.token);
    const tbody = $('#reviews-table tbody');
    if (!reviews.length) { tbody.innerHTML = '<tr><td colspan="8" style="color:var(--text2)">Sin reseñas</td></tr>'; return; }
    tbody.innerHTML = reviews.map(r => `<tr>
      <td>${escapeHtml(r.user_name)}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(r.product_name)}</td>
      <td>${reviewStars(r.rating)}</td>
      <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(r.comment || r.title || '—')}</td>
      <td>${r.is_reported ? '<span style="color:var(--danger)"><i class="fas fa-flag"></i> Sí</span>' : '—'}</td>
      <td><span style="color:${r.is_approved?'var(--success)':'var(--danger)'}">${r.is_approved?'Aprobada':'Oculta'}</span></td>
      <td>${r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}</td>
      <td>
        <button class="btn btn-sm ${r.is_approved?'btn-warning':'btn-success'}" onclick="toggleAdminReview(${r.id})">${r.is_approved?'Ocultar':'Aprobar'}</button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

async function toggleAdminReview(id) {
  try { await api.adminToggleReview(id, state.token); loadAdminReviews(); showToast('Estado actualizado'); }
  catch (err) { showToast(err.message); }
}

// ===== FAQs =====
async function loadFAQs() {
  try {
    const faqs = await api.getAllFAQs(state.token);
    const tbody = $('#faqs-table tbody');
    if (!faqs.length) { tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text2)">Sin FAQs</td></tr>'; return; }
    tbody.innerHTML = faqs.map(f => `<tr>
      <td>${f.question}</td>
      <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${f.answer}</td>
      <td><span style="color:${f.active?'var(--success)':'var(--danger)'}">${f.active?'Activa':'Inactiva'}</span></td>
      <td>
        <button class="btn btn-sm btn-warning" onclick="editFAQ(${f.id})"><i class="fas fa-edit"></i></button>
        <button class="btn btn-sm ${f.active?'btn-warning':'btn-success'}" onclick="toggleFAQ(${f.id})">${f.active?'Ocultar':'Mostrar'}</button>
        <button class="btn btn-sm btn-danger" onclick="deleteFAQ(${f.id})"><i class="fas fa-trash"></i></button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

function openFAQForm() {
  $('#faq-form-element').reset();
  $('#faq-form-id').value = '';
  $('#faq-modal-title').textContent = 'Nueva FAQ';
  $('#faq-modal').classList.add('open');
}

function closeFAQForm() { $('#faq-modal').classList.remove('open'); }

async function editFAQ(id) {
  try {
    const faqs = await api.getAllFAQs(state.token);
    const f = faqs.find(x => x.id === id);
    if (!f) return;
    $('#faq-form-id').value = f.id;
    $('#faq-question').value = f.question;
    $('#faq-answer').value = f.answer;
    $('#faq-category').value = f.category;
    $('#faq-modal-title').textContent = 'Editar FAQ';
    $('#faq-modal').classList.add('open');
  } catch (err) { showToast(err.message); }
}

async function saveFAQ(e) {
  e.preventDefault();
  const id = $('#faq-form-id').value;
  const data = {
    question: $('#faq-question').value,
    answer: $('#faq-answer').value,
    category: $('#faq-category').value,
    sort_order: 0,
  };
  try {
    if (id) { await api.updateFAQ(parseInt(id), data, state.token); }
    else { await api.createFAQ(data, state.token); }
    showToast('FAQ guardada'); closeFAQForm(); loadFAQs();
  } catch (err) { showToast(err.message); }
}

async function toggleFAQ(id) {
  try { await api.toggleFAQ(id, state.token); loadFAQs(); }
  catch (err) { showToast(err.message); }
}

async function deleteFAQ(id) {
  if (!confirm('¿Eliminar FAQ?')) return;
  try { await api.deleteFAQ(id, state.token); showToast('FAQ eliminada'); loadFAQs(); }
  catch (err) { showToast(err.message); }
}

// ===== CUSTOMERS =====
async function loadCustomers() {
  try {
    const users = await api.getCustomers(state.token);
    const tbody = $('#customers-table tbody');
    if (!users.length) { tbody.innerHTML = '<tr><td colspan="11" style="color:var(--text2)">Sin clientes registrados</td></tr>'; return; }
    tbody.innerHTML = users.map(u => `
      <tr style="${u.is_active ? '' : 'opacity:.5'}">
        <td>${u.id}</td>
        <td>${escapeHtml(u.name || '—')}</td>
        <td>${escapeHtml(u.email)}</td>
        <td>${escapeHtml(u.phone || '—')}</td>
        <td>${u.total_orders ?? 0}</td>
        <td>${fmt(u.total_spent || 0)}</td>
        <td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</td>
        <td>${u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Nunca'}</td>
        <td style="font-size:.78rem;color:var(--text2)">${u.last_login_ip || '—'}</td>
        <td><span style="color:${u.is_active?'var(--success)':'var(--danger)'}">${u.is_active?'Activo':'Bloqueado'}</span></td>
        <td>
          <button class="btn btn-sm ${u.is_active?'btn-danger':'btn-success'}" onclick="toggleCustomerBlock(${u.id})">${u.is_active?'Bloquear':'Desbloquear'}</button>
        </td>
      </tr>`).join('');
  } catch (err) { console.error(err); }
}

async function toggleCustomerBlock(id) {
  try {
    const res = await api.toggleCustomerBlock(id, state.token);
    showToast(res.is_active ? 'Usuario desbloqueado' : 'Usuario bloqueado');
    loadCustomers();
  } catch (err) { showToast(err.message); }
}

// ===== CATEGORIES =====
async function loadCategories() {
  try {
    const cats = await api.getAdminCategories(state.token);
    const tbody = $('#categories-table tbody');
    if (!cats.length) { tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text2)">Sin categorías</td></tr>'; return; }
    tbody.innerHTML = cats.map(c => `<tr>
      <td>${c.name}</td><td>${c.slug || '—'}</td><td>${c.product_count ?? 0}</td><td>${c.sort_order ?? 0}</td>
      <td><span style="color:${c.is_active?'var(--success)':'var(--danger)'}">${c.is_active?'Activa':'Inactiva'}</span></td>
      <td>
        <button class="btn btn-sm btn-warning" onclick="editCategory(${c.id})"><i class="fas fa-edit"></i></button>
        <button class="btn btn-sm btn-danger" onclick="deleteCategory(${c.id})"><i class="fas fa-trash"></i></button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

function openCategoryForm() {
  $('#category-form-element').reset();
  $('#category-form-id').value = '';
  $('#category-modal-title').textContent = 'Nueva Categoría';
  $('#category-modal').classList.add('open');
}

function closeCategoryForm() { $('#category-modal').classList.remove('open'); }

async function editCategory(id) {
  try {
    const cats = await api.getAdminCategories(state.token);
    const c = cats.find(x => x.id === id);
    if (!c) return;
    $('#category-form-id').value = c.id;
    $('#category-name').value = c.name;
    $('#category-slug').value = c.slug || '';
    $('#category-description').value = c.description || '';
    $('#category-image').value = c.image || '';
    $('#category-sort').value = c.sort_order ?? 0;
    $('#category-active').value = c.is_active ? 'true' : 'false';
    $('#category-modal-title').textContent = 'Editar Categoría';
    $('#category-modal').classList.add('open');
  } catch (err) { showToast(err.message); }
}

async function saveCategory(e) {
  e.preventDefault();
  const id = $('#category-form-id').value;
  const data = {
    name: $('#category-name').value,
    slug: $('#category-slug').value,
    description: $('#category-description').value,
    image: $('#category-image').value,
    sort_order: parseInt($('#category-sort').value) || 0,
    is_active: $('#category-active').value === 'true',
  };
  try {
    if (id) { await api.updateCategory(parseInt(id), data, state.token); }
    else { await api.createCategory(data, state.token); }
    showToast('Categoría guardada'); closeCategoryForm(); loadCategories();
  } catch (err) { showToast(err.message); }
}

async function deleteCategory(id) {
  if (!confirm('¿Eliminar categoría?')) return;
  try { await api.deleteCategory(id, state.token); showToast('Categoría eliminada'); loadCategories(); }
  catch (err) { showToast(err.message); }
}

// ===== COLLECTIONS =====
async function loadCollections() {
  try {
    const cols = await api.getAdminCollections(state.token);
    const tbody = $('#collections-table tbody');
    if (!cols.length) { tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text2)">Sin colecciones</td></tr>'; return; }
    tbody.innerHTML = cols.map(c => `<tr>
      <td>${c.name}</td><td>${c.slug || '—'}</td><td>${c.product_count ?? 0}</td>
      <td>${c.is_featured ? '★' : '—'}</td>
      <td><span style="color:${c.is_active?'var(--success)':'var(--danger)'}">${c.is_active?'Activa':'Inactiva'}</span></td>
      <td>
        <button class="btn btn-sm btn-warning" onclick="editCollection(${c.id})"><i class="fas fa-edit"></i></button>
        <button class="btn btn-sm btn-danger" onclick="deleteCollection(${c.id})"><i class="fas fa-trash"></i></button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

function openCollectionForm() {
  $('#collection-form-element').reset();
  $('#collection-form-id').value = '';
  $('#collection-modal-title').textContent = 'Nueva Colección';
  $('#collection-modal').classList.add('open');
}

function closeCollectionForm() { $('#collection-modal').classList.remove('open'); }

async function editCollection(id) {
  try {
    const cols = await api.getAdminCollections(state.token);
    const c = cols.find(x => x.id === id);
    if (!c) return;
    $('#collection-form-id').value = c.id;
    $('#collection-name').value = c.name;
    $('#collection-slug').value = c.slug || '';
    $('#collection-description').value = c.description || '';
    $('#collection-image').value = c.image || '';
    $('#collection-featured').value = c.is_featured ? 'true' : 'false';
    $('#collection-active').value = c.is_active ? 'true' : 'false';
    $('#collection-modal-title').textContent = 'Editar Colección';
    $('#collection-modal').classList.add('open');
  } catch (err) { showToast(err.message); }
}

async function saveCollection(e) {
  e.preventDefault();
  const id = $('#collection-form-id').value;
  const data = {
    name: $('#collection-name').value,
    slug: $('#collection-slug').value,
    description: $('#collection-description').value,
    image: $('#collection-image').value,
    is_featured: $('#collection-featured').value === 'true',
    is_active: $('#collection-active').value === 'true',
  };
  try {
    if (id) { await api.updateCollection(parseInt(id), data, state.token); }
    else { await api.createCollection(data, state.token); }
    showToast('Colección guardada'); closeCollectionForm(); loadCollections();
  } catch (err) { showToast(err.message); }
}

async function deleteCollection(id) {
  if (!confirm('¿Eliminar colección?')) return;
  try { await api.deleteCollection(id, state.token); showToast('Colección eliminada'); loadCollections(); }
  catch (err) { showToast(err.message); }
}

// ===== BANNERS =====
async function loadBanners() {
  try {
    const banners = await api.getAdminBanners(state.token);
    const tbody = $('#banners-table tbody');
    if (!banners.length) { tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text2)">Sin banners</td></tr>'; return; }
    tbody.innerHTML = banners.map(b => `<tr>
      <td><img src="${b.image_url||b.image||''}" style="width:80px;height:40px;object-fit:cover;border-radius:4px"></td>
      <td>${b.title || '—'}</td><td>${b.subtitle || '—'}</td><td>${b.sort_order ?? 0}</td>
      <td><span style="color:${b.is_active?'var(--success)':'var(--danger)'}">${b.is_active?'Activo':'Inactivo'}</span></td>
      <td><button class="btn btn-sm btn-danger" onclick="deleteBanner(${b.id})"><i class="fas fa-trash"></i></button></td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

function openBannerForm() {
  $('#banner-form-element').reset();
  $('#banner-form-id').value = '';
  $('#banner-modal-title').textContent = 'Nuevo Banner';
  $('#banner-modal').classList.add('open');
}

function closeBannerForm() { $('#banner-modal').classList.remove('open'); }

async function saveBanner(e) {
  e.preventDefault();
  const id = $('#banner-form-id').value;
  const data = {
    title: $('#banner-title').value,
    subtitle: $('#banner-subtitle').value,
    image_url: $('#banner-image').value,
    sort_order: parseInt($('#banner-sort').value) || 0,
    is_active: $('#banner-active').value === 'true',
  };
  try {
    if (id) { await api.updateBanner?.(parseInt(id), data, state.token); }
    else { await api.createBanner(data, state.token); }
    showToast('Banner guardado'); closeBannerForm(); loadBanners();
  } catch (err) { showToast(err.message); }
}

async function deleteBanner(id) {
  if (!confirm('¿Eliminar banner?')) return;
  try { await api.deleteBanner(id, state.token); showToast('Banner eliminado'); loadBanners(); }
  catch (err) { showToast(err.message); }
}

// ===== NOTIFICATIONS =====
async function sendNotification(e) {
  e.preventDefault();
  const data = {
    type: $('#notif-type').value,
    title: $('#notif-title').value,
    body: $('#notif-body').value,
  };
  try {
    const res = await api.sendNotification(data, state.token);
    showToast(res.sent ? `Notificación enviada a ${res.sent} cliente(s)` : 'Notificación enviada');
    $('#notif-form').reset();
  } catch (err) { showToast(err.message); }
}

// ===== LIVE CHAT =====
const adminChat = {
  socket: null,
  conversations: [],
  currentConvId: null,
  messages: [],
};

function initAdminSocket() {
  if (adminChat.socket) return;
  adminChat.socket = io(API_BASE, {
    transports: ['websocket', 'polling'],
    reconnection: true,
  });

  adminChat.socket.on('connect', () => {
    adminChat.socket.emit('join_chat', { role: 'admin' });
  });

  adminChat.socket.on('admin_new_message', (data) => {
    loadAdminChatConversations();
    if (adminChat.currentConvId === data.conversation_id) {
      loadAdminChatMessages(adminChat.currentConvId);
    } else {
      // Flash the chat nav
      const badge = $('#admin-chat-badge');
      if (badge) {
        const current = parseInt(badge.textContent) || 0;
        badge.textContent = current + 1;
        badge.style.display = 'inline';
      }
    }
  });

  adminChat.socket.on('user_typing', (data) => {
    if (!data.is_admin && adminChat.currentConvId) {
      $('#admin-chat-typing').style.display = 'flex';
      clearTimeout(adminChat._typingTimer);
      adminChat._typingTimer = setTimeout(() => {
        $('#admin-chat-typing').style.display = 'none';
      }, 2000);
    }
  });
}

async function loadAdminChatConversations() {
  try {
    const convs = await api.adminGetConversations(state.token);
    adminChat.conversations = convs;
    const list = $('#admin-chat-list');

    if (!convs.length) {
      list.innerHTML = '<div class="admin-chat-empty">Sin conversaciones activas</div>';
      return;
    }

    list.innerHTML = convs.map(c => {
      const active = c.id === adminChat.currentConvId ? 'background:rgba(184,148,31,.08)' : '';
      return `<div class="admin-chat-conv" data-id="${c.id}" onclick="selectAdminChat(${c.id})" style="padding:14px 16px;border-bottom:1px solid var(--border-light);cursor:pointer;${active}">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:38px;height:38px;border-radius:50%;background:var(--gold-glow);border:1px solid rgba(184,148,31,.15);display:flex;align-items:center;justify-content:center;font-size:.8rem;color:var(--gold);flex-shrink:0">
            <i class="fas fa-user"></i>
          </div>
          <div style="flex:1;min-width:0">
            <div style="font-size:.8rem;font-weight:600;display:flex;justify-content:space-between;gap:8px">
              <span>${escapeHtml(c.guest_name || c.subject || 'Cliente')}</span>
              ${c.unread_count > 0 ? `<span style="background:var(--danger);color:#fff;font-size:.55rem;padding:2px 7px;border-radius:999px;font-weight:700">${c.unread_count}</span>` : ''}
            </div>
            <div style="font-size:.68rem;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px">${escapeHtml(c.last_message || '')}</div>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch (err) { console.error(err); }
}

async function selectAdminChat(convId) {
  adminChat.currentConvId = convId;
  $('#admin-chat-placeholder').style.display = 'none';
  $('#admin-chat-active').style.display = 'flex';
  $('#admin-chat-messages').innerHTML = '';
  $('#admin-chat-typing').style.display = 'none';

  const conv = adminChat.conversations.find(c => c.id === convId);
  if (conv) {
    $('#admin-chat-user-name').textContent = conv.guest_name || conv.subject || 'Cliente';
    $('#admin-chat-user-email').textContent = conv.guest_email || '';
  }

  // Mark as read
  api.adminMarkRead(convId, state.token).catch(() => {});
  loadAdminChatConversations();

  await loadAdminChatMessages(convId);

  // Scroll to bottom
  const msgs = $('#admin-chat-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

async function loadAdminChatMessages(convId) {
  try {
    const msgs = await api.adminGetMessages(convId, state.token);
    adminChat.messages = msgs;
    const container = $('#admin-chat-messages');
    container.innerHTML = msgs.map(m => {
      const isAdmin = m.is_admin;
      return `<div style="display:flex;${isAdmin ? 'justify-content:flex-end' : 'justify-content:flex-start'};margin-bottom:12px">
        <div style="max-width:75%;${isAdmin ? 'background:linear-gradient(135deg,var(--gold),var(--gold-dark));color:#fff' : 'background:#fff;border:1px solid var(--border)'};padding:11px 14px;border-radius:14px;${isAdmin ? 'border-bottom-right-radius:4px' : 'border-bottom-left-radius:4px'};box-shadow:var(--shadow)">
          <div style="font-size:.65rem;font-weight:600;margin-bottom:3px;${isAdmin ? 'opacity:.75;text-align:right' : 'color:var(--text2)'}">${isAdmin ? 'Tú' : escapeHtml(m.sender_name || 'Cliente')}</div>
          <div style="font-size:.84rem;line-height:1.45">${escapeHtml(m.message)}</div>
          <div style="font-size:.6rem;${isAdmin ? 'opacity:.55;text-align:right' : 'color:var(--text3)'};margin-top:5px">${m.created_at ? new Date(m.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : ''}</div>
        </div>
      </div>`;
    }).join('');
    container.scrollTop = container.scrollHeight;
  } catch (err) { console.error(err); }
}

async function adminSendChatMessage() {
  const input = $('#admin-chat-input');
  const text = input.value.trim();
  if (!text || !adminChat.currentConvId) return;

  input.value = '';
  try {
    const result = await api.adminReply(adminChat.currentConvId, { message: text }, state.token);
    loadAdminChatMessages(adminChat.currentConvId);
    loadAdminChatConversations();
  } catch (err) {
    showToast(err.message);
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

// ===== SALES CHART =====
async function loadSalesChart() {
  try {
    const sales = await api.getSales(state.token);
    const container = $('#sales-chart');
    if (!sales.length) {
      container.innerHTML = '<p style="color:var(--text2);text-align:center">Sin datos de ventas</p>';
      return;
    }
    const maxR = Math.max(...sales.map(s => s.revenue), 1);
    container.innerHTML = '<div style="display:flex;align-items:flex-end;gap:12px;height:200px;padding-top:20px">' +
      sales.map(s => {
        const pct = (s.revenue / maxR) * 100;
        return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end">
          <div style="font-size:.65rem;font-weight:600;color:var(--gold);margin-bottom:4px">${fmt(s.revenue)}</div>
          <div style="width:100%;max-width:60px;background:var(--gold);min-height:4px;border-radius:2px 2px 0 0;height:${Math.max(pct,4)}%"></div>
          <div style="font-size:.65rem;color:var(--text2);margin-top:8px;text-align:center">${s.month}</div>
        </div>`;
      }).join('') + '</div>';
  } catch (err) { console.error(err); }
}

async function loadTopProducts() {
  try {
    const top = await api.getTopProducts(state.token);
    const tbody = $('#top-products tbody');
    if (!top.length) { tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text2)">Sin datos</td></tr>'; return; }
    tbody.innerHTML = top.map((p, i) => `<tr>
      <td>${i+1}</td><td>${p.name}</td><td>${p.quantity} vendidos</td><td>${fmt(p.revenue)}</td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

// ===== SECURITY / ACTIVITY LOG =====
async function loadActivityLog() {
  try {
    const logs = await api.adminGetActivityLog(state.token);
    const tbody = $('#activity-log-table tbody');
    if (!logs.length) { tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text2)">Sin actividad registrada</td></tr>'; return; }
    tbody.innerHTML = logs.map(l => {
      const actionColor = l.action.includes('fail') || l.action.includes('block') || l.action.includes('delete')
        ? 'var(--danger)'
        : l.action.includes('login') || l.action.includes('success')
          ? 'var(--success)' : 'var(--text2)';
      const actionIcon = l.action.includes('login') ? 'fa-right-to-bracket'
        : l.action.includes('fail') ? 'fa-triangle-exclamation'
        : l.action.includes('block') ? 'fa-ban'
        : l.action.includes('delete') ? 'fa-trash'
        : l.action.includes('create') || l.action.includes('register') ? 'fa-plus'
        : l.action.includes('update') || l.action.includes('edit') ? 'fa-pen'
        : 'fa-circle-info';
      return `<tr>
        <td><span style="display:inline-flex;align-items:center;gap:6px"><i class="fas ${actionIcon}" style="color:${actionColor};font-size:.8rem"></i> ${escapeHtml(l.action)}</span></td>
        <td>${escapeHtml(l.entity_type || '—')}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(l.details || '')}">${escapeHtml(l.details || '—')}</td>
        <td><code style="font-size:.75rem;background:var(--bg3);padding:2px 8px;border-radius:4px">${escapeHtml(l.ip_address || '—')}</code></td>
        <td style="font-size:.78rem;color:var(--text2)">${l.created_at ? new Date(l.created_at).toLocaleString('es-CO', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : '—'}</td>
      </tr>`;
    }).join('');
  } catch (err) { console.error(err); }
}

// ===== TOAST =====
function showToast(msg) {
  document.querySelector('.admin-toast')?.remove();
  const el = document.createElement('div');
  el.className = 'admin-toast';
  el.innerHTML = `<span style="width:6px;height:6px;border-radius:50%;background:var(--gold);flex-shrink:0"></span>${msg}`;
  el.style.opacity = '0';
  el.style.transition = 'opacity .35s cubic-bezier(0.22, 1, 0.36, 1)';
  document.body.appendChild(el);
  requestAnimationFrame(() => { el.style.opacity = '1'; });
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 350); }, 2500);
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  $('#login-form').addEventListener('submit', handleLogin);
  $('#twofa-form').addEventListener('submit', handle2faVerify);
  $('#twofa-back-btn').addEventListener('click', backToLogin);
  $('#twofa-code').addEventListener('input', (e) => {
    e.target.value = e.target.value.replace(/[^0-9]/g, '');
  });

  // Math CAPTCHA: load on login and wire refresh button
  loadMathCaptcha();
  const refreshBtn = $('#captcha-refresh');
  if (refreshBtn) refreshBtn.addEventListener('click', loadMathCaptcha);

  $('#product-form-element').addEventListener('submit', saveProduct);
  $('#product-cancel-btn').addEventListener('click', closeProductForm);
  $('#product-modal').addEventListener('click', e => { if (e.target === $('#product-modal')) closeProductForm(); });
  $('#coupon-form').addEventListener('submit', createCoupon);
  $('#notif-form').addEventListener('submit', sendNotification);
  $('#faq-form-element').addEventListener('submit', saveFAQ);
  $('#faq-cancel-btn').addEventListener('click', closeFAQForm);
  $('#faq-modal').addEventListener('click', e => { if (e.target === $('#faq-modal')) closeFAQForm(); });
  $('#category-form-element').addEventListener('submit', saveCategory);
  $('#category-cancel-btn').addEventListener('click', closeCategoryForm);
  $('#category-modal').addEventListener('click', e => { if (e.target === $('#category-modal')) closeCategoryForm(); });
  $('#collection-form-element').addEventListener('submit', saveCollection);
  $('#collection-cancel-btn').addEventListener('click', closeCollectionForm);
  $('#collection-modal').addEventListener('click', e => { if (e.target === $('#collection-modal')) closeCollectionForm(); });
  $('#banner-form-element').addEventListener('submit', saveBanner);
  $('#banner-cancel-btn').addEventListener('click', closeBannerForm);
  $('#banner-modal').addEventListener('click', e => { if (e.target === $('#banner-modal')) closeBannerForm(); });
  $('#image-upload-input').addEventListener('change', uploadImage);
  $('#main-image-upload-input').addEventListener('change', uploadMainImage);
  $('#add-variant-btn').addEventListener('click', () => addVariantRow());
  $('#add-image-btn').addEventListener('click', () => addImageInput());

  $$('.sidebar nav a').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      const page = a.dataset.page;
      showPage(page);
      if (page === 'dashboard') { loadDashboard(); }
      if (page === 'products') { loadAdminProducts(); }
      if (page === 'orders') { loadAdminOrders(); }
      if (page === 'chat') { loadAdminChatConversations(); }
      if (page === 'messages') { loadAdminMessages(); }
      if (page === 'customers') { loadCustomers(); }
      if (page === 'catalog') { loadCategories(); loadCollections(); loadBanners(); }
      if (page === 'marketing') { loadCoupons(); }
      if (page === 'faqs') { loadFAQs(); }
      if (page === 'reviews') { loadAdminReviews(); }
      if (page === 'analytics') { loadSalesChart(); loadTopProducts(); }
      if (page === 'security') { loadActivityLog(); }
    });
  });

  // Admin Chat events
  $('#admin-chat-send')?.addEventListener('click', adminSendChatMessage);
  $('#admin-chat-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') adminSendChatMessage(); });
  $('#admin-chat-close-btn')?.addEventListener('click', async () => {
    if (adminChat.currentConvId) {
      await api.adminCloseConversation(adminChat.currentConvId, state.token);
      adminChat.currentConvId = null;
      $('#admin-chat-placeholder').style.display = 'flex';
      $('#admin-chat-active').style.display = 'none';
      loadAdminChatConversations();
      showToast('Conversación cerrada');
    }
  });

  if (state.token) {
    api.me(state.token).then(() => showAdmin()).catch(() => {
      localStorage.removeItem('token'); localStorage.removeItem('user');
    });
  } else {
    // Load reCAPTCHA config for login page
    loadRecaptchaConfig();
  }

  // Mobile sidebar drawer
  const sidebar = document.querySelector('.sidebar');
  const overlay = $('#sidebar-overlay');
  const toggle = $('#sidebar-toggle');
  const closeSidebar = () => { sidebar.classList.remove('open'); overlay.classList.remove('open'); };
  if (toggle) toggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open', sidebar.classList.contains('open'));
  });
  if (overlay) overlay.addEventListener('click', closeSidebar);
  $$('.sidebar nav a').forEach(a => a.addEventListener('click', closeSidebar));
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1100) closeSidebar();
  });
});
