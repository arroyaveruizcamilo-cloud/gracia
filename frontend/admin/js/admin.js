const state = {
  token: localStorage.getItem('token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  products: [], orders: [], messages: [],
};

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const fmt = n => '$' + Number(n).toFixed(2);

function showPage(id) {
  $$('.page-section').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(`page-${id}`);
  if (page) page.classList.add('active');
  $$('.sidebar nav a').forEach(a => a.classList.toggle('active', a.dataset.page === id));
  document.getElementById('page-title').textContent = page?.querySelector('h2')?.textContent || 'Dashboard';
}

// ===== AUTH =====
async function handleLogin(e) {
  e.preventDefault();
  const email = $('#login-email').value;
  const password = $('#login-password').value;
  const errEl = $('#login-error');
  errEl.style.display = 'none';
  try {
    const res = await api.login(email, password);
    if (res.user.role !== 'admin') { errEl.textContent = 'Acceso denegado'; errEl.style.display = 'block'; return; }
    state.token = res.access_token; state.user = res.user;
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('user', JSON.stringify(res.user));
    showAdmin();
  } catch (err) { errEl.textContent = err.message; errEl.style.display = 'block'; }
}

function logout() {
  state.token = null; state.user = null;
  localStorage.removeItem('token'); localStorage.removeItem('user');
  $('#login-page').style.display = 'flex';
  $('#admin-app').style.display = 'none';
}

function showAdmin() {
  $('#login-page').style.display = 'none';
  $('#admin-app').style.display = 'flex';
  $('#admin-user-name').textContent = state.user.name;
  loadDashboard(); loadAdminProducts(); loadAdminOrders(); loadAdminMessages();
  loadCoupons(); loadFAQs();
  initAdminSocket();
  loadAdminChatConversations();

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

    if (data.low_stock > 0) {
      $('#low-stock-warning').innerHTML = `<i class="fas fa-exclamation-triangle" style="color:var(--warning)"></i> ${data.low_stock} producto(s) con stock bajo`;
    } else {
      $('#low-stock-warning').innerHTML = '<i class="fas fa-check-circle" style="color:var(--success)"></i> Stock normal';
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
  if (!fileInput.files?.length) return;
  try {
    const res = await api.uploadImage(fileInput.files[0], state.token);
    addImageInput(res.url);
    fileInput.value = '';
    showToast('Imagen subida');
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
    $('#product-image-preview').innerHTML = `<img src="${data.image}" style="max-width:100px;max-height:100px;object-fit:cover">`;
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
    state.products = await api.getProducts('', '');
    const tbody = $('#products-table tbody');
    if (!state.products.length) { tbody.innerHTML = '<tr><td colspan="8" style="color:var(--text2)">Sin productos</td></tr>'; return; }
    tbody.innerHTML = state.products.map(p => `<tr>
      <td>${p.id}</td>
      <td><img src="${p.image||'https://via.placeholder.com/40'}" style="width:40px;height:50px;object-fit:cover"></td>
      <td>${p.name}</td><td>${fmt(p.price)}</td><td>${p.category}</td><td>${p.stock}</td>
      <td>${p.variants?.length || 0} vars</td>
      <td>
        <button class="btn btn-sm btn-warning" onclick="openProductForm(state.products.find(x=>x.id===${p.id}))" style="margin-right:4px"><i class="fas fa-edit"></i></button>
        <button class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id})"><i class="fas fa-trash"></i></button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
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
      <td>#${o.id}</td><td>${o.customer_name||'—'}</td><td>${o.customer_email||'—'}</td>
      <td>${fmt(o.total)}</td>
      <td><span class="status-badge status-${(o.status||'').toLowerCase()}">${o.status}</span></td>
      <td><span class="status-badge" style="background:${o.payment_status==='Pagado'?'var(--success)':'var(--warning)'};color:#fff">${o.payment_status}</span></td>
      <td>
        <select onchange="updateOrderStatus(${o.id}, this.value)" style="background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 8px;font-size:.75rem">
          ${['Pendiente','Procesando','Enviado','Entregado','Cancelado'].map(s =>
            `<option value="${s}" ${o.status===s?'selected':''}>${s}</option>`
          ).join('')}
        </select>
        <input type="text" placeholder="Tracking #" value="${o.tracking_number||''}" style="width:100px;margin-top:4px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px;font-size:.7rem" onchange="api.updateTracking(${o.id},{tracking_number:this.value},state.token).catch(()=>{})">
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
      <td>${m.name||'—'}</td><td>${m.email||'—'}</td>
      <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${m.message}</td>
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
      <td>${c.type==='percentage' ? c.value+'%' : fmt(c.value)}</td>
      <td>${fmt(c.min_purchase)}</td>
      <td>${c.used_count}/${c.max_uses||'∞'}</td>
      <td><span style="color:${c.active?'var(--success)':'var(--danger)'}">${c.active?'Activo':'Inactivo'}</span></td>
      <td>
        <button class="btn btn-sm ${c.active?'btn-warning':'btn-success'}" onclick="toggleCoupon(${c.id})">${c.active?'Desactivar':'Activar'}</button>
        <button class="btn btn-sm btn-danger" onclick="deleteCoupon(${c.id})"><i class="fas fa-trash"></i></button>
      </td>
    </tr>`).join('');
  } catch (err) { console.error(err); }
}

async function createCoupon(e) {
  e.preventDefault();
  const data = {
    code: $('#coupon-code').value,
    type: $('#coupon-type').value,
    value: parseFloat($('#coupon-value').value),
    min_purchase: parseFloat($('#coupon-min').value) || 0,
    max_uses: parseInt($('#coupon-uses').value) || 0,
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
      list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--gray);font-size:.75rem">Sin conversaciones activas</div>';
      return;
    }

    list.innerHTML = convs.map(c => {
      const active = c.id === adminChat.currentConvId ? 'background:rgba(201,168,76,.08)' : '';
      return `<div class="admin-chat-conv" data-id="${c.id}" onclick="selectAdminChat(${c.id})" style="padding:12px 16px;border-bottom:1px solid var(--gray-light);cursor:pointer;transition:background .2s;${active}">
        <div style="display:flex;align-items:center;gap:10px">
          <div style="width:36px;height:36px;border-radius:50%;background:var(--gray-light);display:flex;align-items:center;justify-content:center;font-size:.8rem;color:var(--gray);flex-shrink:0">
            <i class="fas fa-user"></i>
          </div>
          <div style="flex:1;min-width:0">
            <div style="font-size:.78rem;font-weight:600;display:flex;justify-content:space-between">
              <span>${escapeHtml(c.guest_name || c.subject || 'Cliente')}</span>
              ${c.unread_count > 0 ? `<span style="background:var(--danger);color:#fff;font-size:.55rem;padding:1px 7px;border-radius:8px">${c.unread_count}</span>` : ''}
            </div>
            <div style="font-size:.65rem;color:var(--gray);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(c.last_message || '')}</div>
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
        <div style="max-width:75%;${isAdmin ? 'background:var(--gold);color:#fff' : 'background:#fff;border:1px solid var(--gray-mid)'};padding:10px 14px;border-radius:12px;${isAdmin ? 'border-bottom-right-radius:4px' : 'border-bottom-left-radius:4px'}">
          <div style="font-size:.65rem;font-weight:600;margin-bottom:2px;${isAdmin ? 'opacity:.7;text-align:right' : 'color:var(--gray)'}">${isAdmin ? 'Tú' : (m.sender_name || 'Cliente')}</div>
          <div style="font-size:.82rem">${escapeHtml(m.message)}</div>
          <div style="font-size:.6rem;${isAdmin ? 'opacity:.5;text-align:right' : 'color:var(--gray)'};margin-top:4px">${m.created_at ? new Date(m.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : ''}</div>
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

// ===== TOAST =====
function showToast(msg) {
  document.querySelector('.admin-toast')?.remove();
  let el = document.createElement('div');
  el.className = 'admin-toast';
  el.innerHTML = `<span style="width:6px;height:6px;border-radius:50%;background:var(--gold);flex-shrink:0"></span>${msg}`;
  Object.assign(el.style, {
    position: 'fixed', bottom: '24px', right: '24px', zIndex: '9999',
    background: 'var(--black)', color: '#fff', padding: '12px 20px',
    fontFamily: 'var(--body)', fontSize: '.75rem', display: 'flex',
    alignItems: 'center', gap: '10px', letterSpacing: '.5px',
    borderTop: '2px solid var(--gold)', opacity: '0',
    transition: 'opacity .35s', boxShadow: '0 8px 30px rgba(0,0,0,.3)',
  });
  document.body.appendChild(el);
  requestAnimationFrame(() => el.style.opacity = '1');
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 350); }, 2500);
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  $('#login-form').addEventListener('submit', handleLogin);
  $('#product-form-element').addEventListener('submit', saveProduct);
  $('#product-cancel-btn').addEventListener('click', closeProductForm);
  $('#product-modal').addEventListener('click', e => { if (e.target === $('#product-modal')) closeProductForm(); });
  $('#coupon-form').addEventListener('submit', createCoupon);
  $('#faq-form-element').addEventListener('submit', saveFAQ);
  $('#faq-cancel-btn').addEventListener('click', closeFAQForm);
  $('#faq-modal').addEventListener('click', e => { if (e.target === $('#faq-modal')) closeFAQForm(); });
  $('#image-upload-btn').addEventListener('click', uploadImage);
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
      if (page === 'marketing') { loadCoupons(); }
      if (page === 'faqs') { loadFAQs(); }
      if (page === 'analytics') { loadSalesChart(); loadTopProducts(); }
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
});
