// ===== ANIMATIONS =====
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      if (entry.target.classList.contains('stagger-children')) {
        entry.target.classList.add('visible');
      } else {
        entry.target.classList.add('visible');
      }
      observer.unobserve(entry.target);
    }
  });
}, { threshold: .12, rootMargin: '0px 0px -40px 0px' });

function observeReveal() {
  document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale, .stagger-children, .section-title, .section-subtitle').forEach(el => observer.observe(el));
}

function showSkeleton(count = 4) {
  const grid = $('#product-grid');
  if (!grid) return;
  grid.innerHTML = Array(count).fill(0).map(() => `
    <div class="product-card">
      <div class="skeleton-img"></div>
      <div class="info">
        <div class="skeleton-text" style="width:40%"></div>
        <div class="skeleton-text"></div>
        <div class="skeleton-text" style="width:30%"></div>
      </div>
    </div>
  `).join('');
}

function animateValue(el, start, end, duration = 800) {
  if (!el) return;
  const range = end - start;
  const startTime = performance.now();
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    el.textContent = '$' + Math.round(start + range * ease).toLocaleString('es-CO');
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

// ===== STATE =====
const state = {
  products: [],
  cart: JSON.parse(localStorage.getItem('cart') || '[]'),
  category: '',
  search: '',
  token: localStorage.getItem('token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  wishlist: new Set(JSON.parse(localStorage.getItem('wishlist') || '[]')),
  coupon: null,
  currentPage: 'store',
  selectedVariant: {},
};

// ===== UTILITY =====
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const fmt = n => '$' + Number(n).toFixed(2);

function save(key, val) {
  if (key === 'cart') localStorage.setItem('cart', JSON.stringify(state.cart));
  else if (key === 'wishlist') localStorage.setItem('wishlist', JSON.stringify([...state.wishlist]));
  else if (key === 'token') localStorage.setItem('token', state.token || '');
  else if (key === 'user') localStorage.setItem('user', JSON.stringify(state.user));
}

function showToast(msg) {
  let t = document.getElementById('toast-el');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast-el';
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.remove('visible');
  void t.offsetWidth;
  t.classList.add('visible');
  clearTimeout(t._timeout);
  t._timeout = setTimeout(() => { t.classList.remove('visible'); }, 2500);
}

// ===== AUTH =====
function isLoggedIn() { return !!state.token; }

function updateAuthUI() {
  const logged = isLoggedIn();
  document.getElementById('guest-actions').style.display = logged ? 'none' : '';
  document.getElementById('user-actions').style.display = logged ? '' : 'none';
  document.getElementById('notif-bell-wrap').style.display = logged ? '' : 'none';
  if (logged && state.user) {
    document.getElementById('user-name-display').textContent = state.user.name || state.user.email;
  }
}

// ===== NOTIFICATIONS =====
function toggleNotifications() {
  const panel = document.getElementById('notif-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  if (panel.style.display === 'block') loadNotifications();
}

async function loadNotifications() {
  try {
    const notifs = await api.getMyNotifications(state.token);
    const list = document.getElementById('notif-list');
    const unread = notifs.filter(n => !n.read);
    const badge = document.getElementById('notif-badge');
    if (unread.length) { badge.textContent = unread.length; badge.style.display = 'block'; }
    else { badge.style.display = 'none'; }
    if (!notifs.length) { list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text2);font-size:.85rem">Sin notificaciones</div>'; return; }
    list.innerHTML = notifs.map(n => `
      <div onclick="${n.read ? '' : `markNotificationRead(${n.id})`}" style="padding:10px 16px;border-bottom:1px solid var(--border);cursor:pointer;background:${n.read ? 'transparent' : 'rgba(190,157,95,.08)'}">
        <div style="font-size:.8rem;font-weight:600">${escapeHtml(n.title)}</div>
        ${n.body ? `<div style="font-size:.75rem;color:var(--text2);margin-top:2px">${escapeHtml(n.body)}</div>` : ''}
        <div style="font-size:.65rem;color:var(--text2);margin-top:3px">${new Date(n.created_at).toLocaleString()}</div>
      </div>`).join('');
  } catch (err) { console.error(err); }
}

async function markNotificationRead(id) {
  try {
    await api.markNotificationRead(id, state.token);
    loadNotifications();
  } catch (err) { console.error(err); }
}

document.addEventListener('click', e => {
  const panel = document.getElementById('notif-panel');
  const wrap = document.getElementById('notif-bell-wrap');
  if (panel && wrap && !wrap.contains(e.target)) panel.style.display = 'none';
});

function logoutUser() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  updateAuthUI();
  showPage('store');
  showToast('Sesión cerrada');
}

// ===== PAGE NAV =====
function showPage(page, params) {
  state.currentPage = page;
  $$('.page').forEach(p => p.classList.remove('active'));
  const el = document.getElementById(`page-${page}`);
  if (el) {
    el.classList.add('active');
    el.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale, .section-title, .section-subtitle, .stagger-children').forEach(child => {
      child.classList.remove('visible');
      requestAnimationFrame(() => child.classList.add('visible'));
    });
  }
  $$('.header-nav a, .header-actions a[data-page]').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (page === 'store') loadProducts();
  if (page === 'wishlist') renderWishlist();
  if (page === 'orders') loadUserOrders();
  if (page === 'product' && params?.slug) loadProductDetail(params.slug);
}

function navigateTo(page, params) {
  if (page === 'product' && params?.slug) {
    window.history.pushState(null, '', `/producto/${params.slug}`);
  } else {
    window.history.pushState(null, '', `/`);
  }
  showPage(page, params);
}

window.addEventListener('popstate', () => {
  const match = window.location.pathname.match(/^\/producto\/(.+)/);
  if (match) {
    showPage('product', { slug: match[1] });
  } else {
    showPage('store');
  }
});

// ===== PRODUCT DETAIL =====
async function loadProductDetail(slug) {
  const container = $('#product-detail-content');
  if (!container) return;
  container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:60px"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';
  try {
    const products = await api.getProducts();
    const p = products.find(x => x.slug === slug || x.name.toLowerCase().replace(/[^a-z0-9]+/g, '-') === slug);
    if (!p) { container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:60px;color:var(--text2)">Producto no encontrado</div>'; return; }
    renderProductDetail(p);
  } catch (e) {
    container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:60px;color:var(--danger)">Error al cargar producto</div>';
  }
}

function renderProductDetail(p) {
  const disc = p.old_price && p.old_price > p.price;
  const pct = disc ? Math.round((1 - p.price / p.old_price) * 100) : 0;
  const colors = p.variants ? [...new Map(p.variants.map(v => [v.color, v.color_hex])).entries()] : [];
  const sizes = p.variants ? [...new Set(p.variants.map(v => v.size).filter(Boolean))] : [];

  $('#pd-image').innerHTML = `
    <img src="${p.image || 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800'}" alt="${escapeHtml(p.name)}" style="width:100%;height:auto;border-radius:var(--radius-lg)">
    ${p.images && p.images.length ? `<div style="display:flex;gap:8px;margin-top:12px">${p.images.slice(0, 4).map(u => `<img src="${u}" style="width:80px;height:100px;object-fit:cover;border-radius:var(--radius-sm);cursor:pointer;border:2px solid transparent" onclick="document.querySelector('#pd-image img').src='${u}';this.style.borderColor='var(--gold)';document.querySelectorAll('#pd-image .thumb').forEach(t=>t.style.borderColor='transparent')" class="thumb">`).join('')}</div>` : ''}
  `;

  $('#pd-info').innerHTML = `
    <div class="cat-tag" style="margin-bottom:8px">${escapeHtml(p.category || 'Categoría')}</div>
    <h1 style="font-family:var(--font-d);font-size:2rem;margin-bottom:12px">${escapeHtml(p.name)}</h1>
    <div class="price" style="font-size:1.5rem;margin-bottom:16px">${fmt(p.price)}${disc ? `<span class="old-price" style="font-size:1rem">${fmt(p.old_price)}</span><span class="badge" style="position:static;display:inline-block;margin-left:12px">-${pct}%</span>` : ''}</div>
    <p style="color:var(--text2);line-height:1.8;margin-bottom:24px">${escapeHtml(p.description || 'Descripción no disponible.')}</p>
    ${colors.length ? `<div style="margin-bottom:16px"><strong style="font-size:.8rem;text-transform:uppercase;letter-spacing:1px;color:var(--text2)">Colores:</strong><div style="display:flex;gap:8px;margin-top:8px">${colors.map(([name, hex]) => `<span style="width:28px;height:28px;border-radius:50%;background:${hex};border:2px solid var(--border);cursor:pointer" title="${name}"></span>`).join('')}</div></div>` : ''}
    ${sizes.length ? `<div style="margin-bottom:24px"><strong style="font-size:.8rem;text-transform:uppercase;letter-spacing:1px;color:var(--text2)">Tallas:</strong><div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">${sizes.map(s => `<span style="padding:6px 16px;border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer;font-size:.85rem">${s}</span>`).join('')}</div></div>` : ''}
    <button class="btn btn-gold" onclick="addToCart(${p.id})" style="width:100%;padding:16px" ${p.stock <= 0 ? 'disabled' : ''}>${p.stock <= 0 ? 'Agotado' : 'Añadir al carrito'}</button>
    <button class="btn btn-outline" onclick="toggleWishlist(${p.id})" style="width:100%;margin-top:8px"><i class="fas fa-heart-o"></i> ${state.wishlist.has(p.id) ? 'Quitar de favoritos' : 'Añadir a favoritos'}</button>
  `;

  loadReviews(p.id);
}

// ===== REVIEWS =====
function starRow(rating) {
  return '<span style="color:#e6b91e;letter-spacing:2px;font-size:.9rem">' +
    Array.from({ length: 5 }, (_, i) => `<i class="fas fa-star${i < Math.round(rating) ? '' : '-o'}"></i>`).join('') +
    '</span>';
}

async function loadReviews(productId) {
  const container = $('#pd-reviews');
  if (!container) return;
  try {
    const data = await api.getProductReviews(productId);
    renderReviews(data, productId);
  } catch (e) {
    container.innerHTML = '';
  }
}

function renderReviews(data, productId) {
  const container = $('#pd-reviews');
  const dist = data.distribution || {};
  const maxDist = Math.max(1, ...Object.values(dist));

  container.innerHTML = `
    <div style="border-top:1px solid var(--border);padding-top:40px">
      <h2 style="font-family:var(--font-d);margin-bottom:24px">Reseñas de clientes</h2>
      <div style="display:grid;grid-template-columns:260px 1fr;gap:32px;align-items:start">
        <div style="text-align:center;padding:24px;border:1px solid var(--border);border-radius:var(--radius-lg)">
          <div style="font-size:3rem;font-weight:800;font-family:var(--font-d)">${data.average || '—'}</div>
          <div style="margin:8px 0">${starRow(data.average || 0)}</div>
          <div style="color:var(--text2);font-size:.85rem">${data.total || 0} reseñas</div>
        </div>
        <div>
          ${[5, 4, 3, 2, 1].map(n => `
            <div style="display:flex;align-items:center;gap:8px;margin:6px 0;font-size:.8rem">
              <span style="width:30px;color:var(--text2)">${n}★</span>
              <div style="flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden">
                <div style="height:100%;width:${Math.round(((dist[n] || 0) / maxDist) * 100)}%;background:#e6b91e"></div>
              </div>
              <span style="width:20px;color:var(--text2)">${dist[n] || 0}</span>
            </div>`).join('')}
        </div>
      </div>

      ${state.token ? `
        <div style="margin-top:32px;padding:24px;border:1px solid var(--border);border-radius:var(--radius-lg)">
          <h3 style="font-family:var(--font-d);margin-bottom:16px">Escribí tu reseña</h3>
          <div style="display:flex;gap:8px;margin-bottom:12px" id="rv-stars">
            ${Array.from({ length: 5 }, (_, i) => `<i class="fas fa-star rv-star" data-v="${i + 1}" style="font-size:1.4rem;color:#ccc;cursor:pointer" onclick="setRating(${i + 1})"></i>`).join('')}
          </div>
          <input type="text" id="rv-title" placeholder="Título (opcional)" style="width:100%;padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--card);color:var(--text);margin-bottom:12px">
          <textarea id="rv-comment" rows="3" placeholder="¿Qué te pareció el producto?" style="width:100%;padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--card);color:var(--text);margin-bottom:12px"></textarea>
          <button class="btn btn-gold" onclick="submitReview(${productId})">Publicar reseña</button>
        </div>` : `
        <p style="margin-top:24px;color:var(--text2)"><a href="#" onclick="openAuth('login');return false" style="color:var(--gold)">Iniciá sesión</a> para dejar tu reseña</p>`}

      <div style="margin-top:24px;display:grid;gap:16px">
        ${(data.reviews || []).map(r => `
          <div style="padding:20px;border:1px solid var(--border);border-radius:var(--radius-lg)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <strong>${escapeHtml(r.user_name || 'Cliente')}</strong>
              ${starRow(r.rating)}
            </div>
            ${r.title ? `<h4 style="margin-bottom:4px">${escapeHtml(r.title)}</h4>` : ''}
            <p style="color:var(--text2);line-height:1.7">${escapeHtml(r.comment || '')}</p>
            <div style="margin-top:8px;font-size:.75rem;color:var(--text2)">${r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}</div>
          </div>`).join('')}
        ${!data.reviews || !data.reviews.length ? '<p style="color:var(--text2)">Aún no hay reseñas. ¡Sé el primero!</p>' : ''}
      </div>
    </div>
  `;
}

let _rvRating = 5;
function setRating(n) {
  _rvRating = n;
  document.querySelectorAll('.rv-star').forEach(s => {
    s.style.color = parseInt(s.dataset.v) <= n ? '#e6b91e' : '#ccc';
  });
}

async function submitReview(productId) {
  const title = $('#rv-title').value.trim();
  const comment = $('#rv-comment').value.trim();
  if (!comment && !title) { showToast('Escribí un comentario o título'); return; }
  try {
    const res = await api.createReview({ product_id: productId, rating: _rvRating, title, comment }, state.token);
    if (res.ok === false) { showToast(res.error); return; }
    showToast('¡Gracias por tu reseña!');
    loadReviews(productId);
  } catch (err) { showToast(err.message); }
}

// ===== PRODUCTS =====
async function loadProducts() {
  showSkeleton(4);
  try {
    state.products = await api.getProducts(state.category, state.search);
    renderProducts(state.products);
    // Animate prices
    requestAnimationFrame(() => {
      document.querySelectorAll('.product-card .info .price').forEach(el => {
        const val = parseFloat(el.dataset.value || '0');
        if (val) animateValue(el, 0, val, 600);
      });
    });
  } catch (err) { showToast('Error al cargar productos'); }
}

function renderProducts(products) {
  const grid = $('#product-grid');
  if (!grid) return;
  if (!products.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:60px;color:var(--text2)">No se encontraron productos</div>';
    return;
  }
  grid.classList.add('stagger-children');
  grid.innerHTML = products.map(p => {
    const disc = p.old_price && p.old_price > p.price;
    const pct = disc ? Math.round((1 - p.price / p.old_price) * 100) : 0;
    const inWish = state.wishlist.has(p.id);
    const hasVariants = p.variants && p.variants.length > 0;
    const colors = hasVariants ? [...new Map(p.variants.map(v => [v.color, v.color_hex])).entries()] : [];
    const outOfStock = (p.stock || 0) <= 0;
    return `
      <div class="product-card" data-id="${p.id}" onclick="navigateTo('product',{slug:'${(p.slug||p.name).toLowerCase().replace(/[^a-z0-9]+/g,'-')}')}">
        <div class="img-wrap">
          <img src="${p.image || 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=500'}" alt="${escapeHtml(p.name)}" loading="lazy" style="${outOfStock ? 'filter:grayscale(.9);opacity:.6' : ''}">
          ${disc ? `<span class="badge">-${pct}%</span>` : ''}
          ${outOfStock ? '<span class="badge" style="background:var(--text);color:#fff;left:auto;right:12px">Agotado</span>' : ''}
          <button class="wishlist-btn ${inWish ? 'active' : ''}" onclick="event.stopPropagation(); toggleWishlist(${p.id})">
            <i class="fas ${inWish ? 'fa-heart' : 'fa-heart-o'}"></i>
          </button>
          <div class="overlay">
            <button class="btn btn-gold" onclick="event.stopPropagation(); addToCart(${p.id})" ${outOfStock ? 'disabled' : ''}>${outOfStock ? 'Agotado' : 'Añadir'}</button>
            <button class="btn btn-outline" onclick="event.stopPropagation(); quickView(${p.id})">Ver</button>
          </div>
        </div>
        <div class="info">
          <div class="cat-tag">${escapeHtml(p.category)}</div>
          <h3>${escapeHtml(p.name)}</h3>
          <div class="price" data-value="${p.price}">${fmt(p.price)}${disc ? `<span class="old-price">${fmt(p.old_price)}</span>` : ''}</div>
          ${colors.length ? `<div class="variants-preview">${colors.map(([name, hex]) => `<span class="variant-dot" style="background:${hex}" title="${name}"></span>`).join('')}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');
  observer.observe(grid);
}

// ===== QUICK VIEW =====
async function quickView(id) {
  try {
    const p = state.products.find(x => x.id === id) || await api.getProduct(id);
    const disc = p.old_price && p.old_price > p.price;
    const colors = p.variants ? [...new Map(p.variants.map(v => [v.color, v.color_hex])).entries()] : [];
    const sizes = p.variants ? [...new Set(p.variants.map(v => v.size).filter(Boolean))] : [];
    const ov = document.createElement('div');
    ov.className = 'modal-overlay open';
    ov.onclick = e => { if (e.target === ov) ov.remove(); };
    ov.innerHTML = `
      <div class="modal" style="max-width:700px">
        <button class="close-modal" onclick="this.closest('.modal-overlay').remove()">&times;</button>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
          <div>
            <img src="${p.image}" alt="${escapeHtml(p.name)}" style="width:100%;height:auto;object-fit:cover">
            ${p.images && p.images.length ? `<div style="display:flex;gap:8px;margin-top:8px">
              ${p.images.slice(0, 4).map(u => `<img src="${u}" style="width:60px;height:80px;object-fit:cover;cursor:pointer;border:1px solid var(--border)" onclick="this.parentElement.parentElement.previousElementSibling.src='${u}'">`).join('')}
            </div>` : ''}
          </div>
          <div>
            <div class="cat-tag" style="font-size:.7rem;color:var(--gold);text-transform:uppercase;letter-spacing:1.5px">${escapeHtml(p.category)}</div>
            <h3 style="font-family:var(--font-d);font-size:1.3rem;margin:8px 0">${escapeHtml(p.name)}</h3>
            <p style="color:var(--text2);font-size:.9rem;margin-bottom:12px">${escapeHtml(p.description)}</p>
            <div class="price" style="font-size:1.3rem;font-weight:600;color:var(--gold)">
              ${fmt(p.price)}${disc ? `<span class="old-price" style="font-size:1rem;color:var(--text2);text-decoration:line-through;margin-left:8px">${fmt(p.old_price)}</span>` : ''}
            </div>
            ${sizes.length ? `<div style="margin:12px 0"><label style="font-size:.75rem;color:var(--text2);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Talla</label>
              <div style="display:flex;gap:6px">${sizes.map(s => `<button class="btn btn-sm btn-outline size-btn" onclick="document.querySelectorAll('.size-btn').forEach(b=>b.classList.remove('active'));this.classList.add('active');state.selectedVariant.size='${s}'">${s}</button>`).join('')}</div>
            </div>` : ''}
            ${colors.length ? `<div style="margin:12px 0"><label style="font-size:.75rem;color:var(--text2);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Color</label>
              <div style="display:flex;gap:8px">${colors.map(([name, hex]) => `<span class="variant-dot" style="background:${hex};width:24px;height:24px" onclick="document.querySelectorAll('.color-btn').forEach(b=>b.classList.remove('active'));this.classList.add('active');state.selectedVariant.color='${name}'"></span>`).join('')}</div>
            </div>` : ''}
            <button class="btn btn-gold" style="width:100%;margin-top:16px" onclick="addToCart(${p.id}); this.closest('.modal-overlay').remove()">Añadir al Carrito</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(ov);
  } catch (err) { showToast('Error'); }
}

// ===== CART =====
function addToCart(pid) {
  const p = state.products.find(x => x.id === pid);
  if (!p) return;
  const maxStock = p.stock || 0;
  if (maxStock <= 0) { showToast('Producto sin stock'); return; }
  const existing = state.cart.find(i => i.id === pid);
  if (existing) existing.qty = Math.min(existing.qty + 1, maxStock);
  else state.cart.push({ id: pid, name: p.name, price: p.price, image: p.image, qty: 1, stock: maxStock });
  save('cart');
  updateCartUI();
  renderCartItems();
  
  // Animated toast
  showToast(`✨ ${p.name} añadido al carrito`);
  
  // Open cart with animation
  const cartBtn = document.getElementById('cart-btn');
  if (cartBtn) {
    cartBtn.style.animation = 'none';
    setTimeout(() => {
      cartBtn.style.animation = 'pulse 0.6s var(--ease) 2';
    }, 10);
  }
  
  updateCartFooter();

  // Sync with server if logged in
  if (isLoggedIn()) {
    api.addToCart({ product_id: pid, quantity: 1 }, state.token).catch(() => {});
  }
}

function removeCartItem(id) {
  // Animate item removal
  const itemEl = document.querySelector(`[data-cart-id="${id}"]`);
  if (itemEl) {
    itemEl.style.animation = 'fadeOut 0.4s var(--ease) forwards';
    setTimeout(() => {
      state.cart = state.cart.filter(i => i.id !== id);
      save('cart');
      updateCartUI();
      renderCartItems();
      showToast(`✓ Producto removido del carrito`);
      if (isLoggedIn()) api.removeCartItem(id, state.token).catch(() => {});
    }, 400);
  } else {
    state.cart = state.cart.filter(i => i.id !== id);
    save('cart');
    updateCartUI();
    renderCartItems();
    if (isLoggedIn()) api.removeCartItem(id, state.token).catch(() => {});
  }
}

function updateQty(id, delta) {
  const item = state.cart.find(i => i.id === id);
  if (!item) return;
  
  const oldQty = item.qty;
  item.qty = Math.max(1, Math.min(item.qty + delta, 99));
  
  // Animate quantity change
  if (item.qty !== oldQty) {
    const itemEl = document.querySelector(`[data-cart-id="${id}"]`);
    if (itemEl) {
      const qtyEl = itemEl.querySelector('.qty-value');
      if (qtyEl) {
        qtyEl.style.animation = 'none';
        setTimeout(() => {
          qtyEl.style.animation = 'pulse 0.4s var(--ease)';
        }, 10);
      }
    }
  }
  
  save('cart');
  renderCartItems();
  updateCartFooter();
}

function cartTotal() { return state.cart.reduce((s, i) => s + i.price * i.qty, 0); }

function updateCartUI() {
  const count = state.cart.reduce((s, i) => s + i.qty, 0);
  $$('.cart-count').forEach(el => { el.textContent = count; el.style.display = count > 0 ? 'flex' : 'none'; });
}

function renderCartItems() {
  const container = $('#cart-items');
  if (!container) return;
  if (!state.cart.length) {
    container.innerHTML = '<div class="cart-empty"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="60"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z"/></svg><p>Tu carrito está vacío</p></div>';
    return;
  }
  container.innerHTML = state.cart.map(i => `
    <div class="cart-item" data-cart-id="${i.id}">
      <img src="${i.image || 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=200'}" alt="${escapeHtml(i.name)}">
      <div class="cart-item-details">
        <h4>${escapeHtml(i.name)}</h4>
        <div class="price">${fmt(i.price)}</div>
        <div class="cart-item-qty">
          <button class="qty-btn" onclick="updateQty(${i.id}, -1)">−</button>
          <span class="qty-value">${i.qty}</span>
          <button class="qty-btn" onclick="updateQty(${i.id}, 1)">+</button>
        </div>
        <button class="cart-item-remove" onclick="removeCartItem(${i.id})">✕ Eliminar</button>
      </div>
    </div>
  `).join('');
}

function updateCartFooter() {
  const el = $('#cart-total-amount');
  if (el) el.textContent = fmt(cartTotal());
  applyCouponDisplay();
}

// ===== COUPON =====
async function applyCoupon() {
  const code = $('#coupon-input').value.trim();
  if (!code) return;
  try {
    const r = await api.validateCoupon(code, cartTotal());
    state.coupon = r;
    $('#coupon-msg').className = 'coupon-msg success';
    $('#coupon-msg').textContent = `Cupón aplicado! Descuento: ${fmt(r.discount)}`;
    applyCouponDisplay();
  } catch (err) {
    state.coupon = null;
    $('#coupon-msg').className = 'coupon-msg error';
    $('#coupon-msg').textContent = err.message;
    applyCouponDisplay();
  }
}

function applyCouponDisplay() {
  const el = $('#cart-discount-row');
  const totalEl = $('#cart-total-amount');
  if (!el || !totalEl) return;
  const total = cartTotal();
  const disc = state.coupon ? state.coupon.discount : 0;
  const finalTotal = total - disc;
  if (state.coupon) {
    el.style.display = 'flex';
    $('#cart-discount-amount').textContent = `-${fmt(disc)}`;
  } else {
    el.style.display = 'none';
  }
  totalEl.textContent = fmt(Math.max(0, finalTotal));
}

// ===== WISHLIST =====
function toggleWishlist(pid) {
  if (state.wishlist.has(pid)) {
    state.wishlist.delete(pid);
    showToast('Eliminado de favoritos');
  } else {
    state.wishlist.add(pid);
    showToast('Añadido a favoritos');
  }
  save('wishlist');
  renderProducts(state.products);
}

async function renderWishlist() {
  const grid = $('#wishlist-grid');
  if (!grid) return;
  const ids = [...state.wishlist];
  if (!ids.length) { grid.innerHTML = '<p style="text-align:center;color:var(--text2);padding:40px">No tienes favoritos aún</p>'; return; }
  try {
    const all = await api.getProducts();
    const items = all.filter(p => ids.includes(p.id));
    grid.innerHTML = items.map(p => `
      <div class="wishlist-item">
        <img src="${p.image || 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=500'}" alt="${escapeHtml(p.name)}">
        <div class="info">
          <h4>${escapeHtml(p.name)}</h4>
          <div class="price">${fmt(p.price)}</div>
          <button class="btn btn-gold btn-sm" style="width:100%;margin-top:8px" onclick="addToCart(${p.id}); renderWishlist()">Añadir al Carrito</button>
        </div>
      </div>
    `).join('');
  } catch (err) { showToast('Error'); }
}

// ===== PAYMENT REDIRECT HANDLER =====
(function handlePaymentRedirect() {
  const params = new URLSearchParams(window.location.search);
  const payment = params.get('payment');
  const orderId = params.get('order_id');
  if (payment && orderId) {
    const url = new URL(window.location);
    url.searchParams.delete('payment');
    url.searchParams.delete('order_id');
    window.history.replaceState({}, '', url);

    api.getPaymentStatus(parseInt(orderId), state.token)
      .then(data => {
        state.cart = []; save('cart'); updateCartUI();
        if (data.payment_status === 'Pagado') {
          showSuccessView(orderId, data.total, data.payment_method, data.customer_email);
          $('#checkout-modal').classList.add('open');
        } else if (payment === 'failure') {
          $('#checkout-modal').classList.add('open');
          showCheckoutView('error');
          document.getElementById('cs-error-message').textContent =
            'El pago no se completó. Podés intentar de nuevo con otro medio.';
        } else {
          $('#checkout-modal').classList.add('open');
          showCheckoutView('error');
          document.getElementById('cs-error-message').textContent =
            'Estamos esperando la confirmación del pago. Te notificaremos por email.';
        }
      })
      .catch(() => {
        if (payment === 'success') {
          showToast(`¡Pedido #${orderId} creado! Te confirmaremos por email.`);
        } else {
          showToast(`El pago del pedido #${orderId} no se completó.`);
        }
      });
  }
})();

// ===== CHECKOUT PROFESSIONAL =====
const PAYMENT_METHODS = {
  card: { name: 'Tarjeta Débito / Crédito', icon: 'fa-credit-card', desc: 'Visa, Mastercard, American Express' },
  pse: { name: 'PSE', icon: 'fa-university', desc: 'Bancolombia, Davivienda, Caja Social +' },
  nequi: { name: 'Nequi', icon: 'fa-mobile-screen-button', desc: 'Paga directo desde la app Nequi' },
  daviplata: { name: 'Daviplata', icon: 'fa-wallet', desc: 'Billetera digital Davivienda' },
  llave: { name: 'Llave Davivienda', icon: 'fa-key', desc: 'Sin número de tarjeta, solo tu Llave' },
  sistecredito: { name: 'SisteCrédito', icon: 'fa-calendar-check', desc: 'Crédito sin tarjeta, paga en cuotas' },
  cod: { name: 'Contra Entrega', icon: 'fa-money-bill-1', desc: 'Efectivo al recibir' },
};

let selectedMethod = 'card';

function selectPaymentMethod(method) {
  selectedMethod = method;
  document.querySelectorAll('.pay-method-card').forEach(c => c.classList.remove('selected'));
  document.querySelector(`.pay-method-card[data-method="${method}"]`)?.classList.add('selected');
  document.getElementById('checkout-continue-btn').disabled = false;
}

function openCheckout() {
  if (!state.cart.length) { showToast('Carrito vacío'); return; }
  selectedMethod = 'card';
  showCheckoutView('method');
  resetCheckoutViews();
  showCheckoutStep(1);
  document.querySelector('.pay-method-card[data-method="card"]')?.classList.add('selected');
  document.getElementById('checkout-continue-btn').disabled = false;
  renderCheckoutSummaryItems();
  updateCheckoutTotals();
  updatePaymentSummary();
  $('#checkout-modal').classList.add('open');
  document.getElementById('checkout-coupon-msg').textContent = '';
}

function resetCheckoutViews() {
  document.getElementById('checkout-view-success').classList.remove('active');
  document.getElementById('checkout-view-error').classList.remove('active');
  document.getElementById('checkout-view-method').classList.add('active');
}

function showCheckoutView(view) {
  document.getElementById('checkout-view-success').classList.toggle('active', view === 'success');
  document.getElementById('checkout-view-error').classList.toggle('active', view === 'error');
  document.getElementById('checkout-view-method').classList.toggle('active', view === 'method');
}

function showCheckoutStep(step) {
  document.querySelectorAll('.checkout-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.checkout-step').forEach(s => s.classList.remove('active'));
  const panel = document.getElementById(`check-step-${step}`);
  const stepEl = document.getElementById(`cs-${step === 1 ? 'method' : step === 2 ? 'confirm' : 'result'}`);
  if (panel) panel.classList.add('active');
  if (stepEl) stepEl.classList.add('active');
}

function renderCheckoutSummaryItems() {
  const container = document.getElementById('checkout-summary-items');
  if (!container) return;
  container.innerHTML = state.cart.map(i => `
    <div class="checkout-summary-item">
      <img src="${i.image || 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=200'}" alt="${escapeHtml(i.name)}">
      <div class="info">
        <div class="name">${escapeHtml(i.name)}</div>
        <div class="meta">Cant: ${i.qty}</div>
        <div class="price">${fmt(i.price * i.qty)}</div>
      </div>
    </div>
  `).join('');
}

function updateCheckoutTotals() {
  const total = cartTotal();
  const disc = state.coupon ? state.coupon.discount : 0;
  const finalTotal = Math.max(0, total - disc);
  document.getElementById('co-subtotal').textContent = fmt(total);
  const dr = document.getElementById('co-discount-row');
  if (disc > 0 && state.coupon) {
    dr.style.display = 'flex';
    document.getElementById('co-discount').textContent = `-${fmt(disc)}`;
  } else {
    dr.style.display = 'none';
  }
  document.getElementById('co-total').textContent = fmt(finalTotal);
  document.getElementById('co-pay-amount').textContent = fmt(finalTotal);
}

function updatePaymentSummary() {
  const info = PAYMENT_METHODS[selectedMethod] || PAYMENT_METHODS.card;
  document.getElementById('co-payment-info').innerHTML =
    `<i class="fa-regular ${info.icon}"></i><span>${info.name}</span>`;
}

function proceedToConfirm() {
  showCheckoutStep(2);
  updateCheckoutTotals();
  updatePaymentSummary();
}

// Coupon
document.getElementById('checkout-apply-coupon')?.addEventListener('click', applyCheckoutCoupon);

async function applyCheckoutCoupon() {
  const code = document.getElementById('checkout-coupon-input').value.trim();
  if (!code) return;
  try {
    const r = await api.validateCoupon(code, cartTotal());
    state.coupon = r;
    document.getElementById('checkout-coupon-msg').className = 'coupon-msg success';
    document.getElementById('checkout-coupon-msg').textContent = `Cupón aplicado! Descuento: ${fmt(r.discount)}`;
    updateCheckoutTotals();
  } catch (err) {
    state.coupon = null;
    document.getElementById('checkout-coupon-msg').className = 'coupon-msg error';
    document.getElementById('checkout-coupon-msg').textContent = err.message;
    updateCheckoutTotals();
  }
}

async function submitOrder() {
  const email = document.getElementById('checkout-email').value.trim();
  if (!email) { showToast('Ingresá tu correo electrónico'); return; }

  const name = document.getElementById('checkout-name').value.trim() || email.split('@')[0] || 'Cliente';
  const address = document.getElementById('checkout-address').value.trim();
  const city = document.getElementById('checkout-city').value.trim();
  if (!address) { showToast('Ingresá tu dirección de entrega'); return; }
  if (!city) { showToast('Ingresá la ciudad de entrega'); return; }

  const locMsg = document.getElementById('checkout-location-msg');
  locMsg.className = '';
  locMsg.textContent = '';

  const btn = document.getElementById('submit-order-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="cr-spinner" style="width:20px;height:20px;border-width:2px;margin:0"></span> Procesando...';

  showCheckoutStep(3);
  const loader = document.querySelector('#checkout-result-content .checkout-result-loader');
  const actions = document.getElementById('checkout-result-actions');
  if (loader) loader.style.display = 'block';
  if (actions) actions.style.display = 'none';

  try {
    const total = cartTotal();
    const disc = state.coupon ? state.coupon.discount : 0;
    const data = {
      customer_name: name,
      customer_email: email,
      shipping_address: address,
      shipping_city: city,
      shipping_cost: 0,
      coupon_code: state.coupon ? state.coupon.code : '',
      subtotal: total,
      discount: disc,
      total: Math.max(0, total - disc),
      payment_method: selectedMethod,
      items: state.cart.map(i => ({ product_id: i.id, quantity: i.qty, price: i.price })),
    };

    const order = await api.createOrder(data, state.token);

    if (selectedMethod === 'cod') {
      showSuccessView(order.order_id, order.total ?? total - disc, 'cod', email);
      state.cart = []; state.coupon = null;
      save('cart');
      updateCartUI();
      btn.disabled = false;
      btn.innerHTML = '<span>Pagar <span id="co-pay-amount"></span></span>';
      updateCheckoutTotals();
      return;
    }

    const pref = await api.createPreference({ order_id: order.order_id, payment_method: selectedMethod });

    if (pref.status === 'simulated' || (!pref.init_point && !pref.sandbox_init_point)) {
      await api.simulatePayment(order.order_id, state.token);
      showSuccessView(order.order_id, total - disc, selectedMethod, email);
    } else {
      const redirectUrl = pref.init_point || pref.sandbox_init_point;
      showCheckoutStep(3);
      if (loader) loader.innerHTML = `
        <div class="cr-spinner"></div>
        <h3>Redirigiendo a MercadoPago...</h3>
        <p>Serás redirigido al entorno seguro de MercadoPago para completar el pago.</p>
        <button class="btn btn-gold" style="margin-top:20px" onclick="window.location.href='${redirectUrl}'">
          Ir a pagar ahora
        </button>
      `;
      setTimeout(() => { window.location.href = redirectUrl; }, 1500);
    }

    state.cart = []; state.coupon = null;
    save('cart');
    updateCartUI();
  } catch (err) {
    const loaderEl = document.querySelector('#checkout-result-content .checkout-result-loader');
    if (loaderEl) loaderEl.style.display = 'none';
    document.getElementById('checkout-result-actions').style.display = 'flex';
    showCheckoutView('error');
    document.getElementById('cs-error-message').textContent = err.message || 'Ocurrió un error al procesar tu pago.';
  }
  btn.disabled = false;
  btn.innerHTML = '<span>Pagar <span id="co-pay-amount"></span></span>';
  updateCheckoutTotals();
}

function showSuccessView(orderId, total, method, email) {
  showCheckoutView('success');
  const info = PAYMENT_METHODS[method] || PAYMENT_METHODS.card;
  const isCOD = method === 'cod';
  const address = document.getElementById('checkout-address')?.value || '';
  const city = document.getElementById('checkout-city')?.value || '';
  document.getElementById('cs-order-info').innerHTML = `
    <div class="row"><span class="label">Pedido</span><span class="value">#${orderId}</span></div>
    <div class="row"><span class="label">Total</span><span class="value" style="color:var(--gold)">${fmt(total)}</span></div>
    <div class="row"><span class="label">Medio de pago</span><span class="value">${info.name}</span></div>
    <div class="row"><span class="label">Email</span><span class="value">${email}</span></div>
    ${address ? `<div class="row"><span class="label">Dirección</span><span class="value">${address}, ${city}</span></div>` : ''}
    <div class="row"><span class="label">Estado</span><span class="value" style="color:${isCOD ? 'var(--gold)' : 'var(--success)'}">${isCOD ? 'Pendiente de pago' : 'Pagado'}</span></div>
  `;
  document.getElementById('cs-success-message').textContent = isCOD
    ? 'Tu pedido fue registrado. Pagás en efectivo cuando recibas la entrega.'
    : 'Tu pedido fue registrado exitosamente. Recibirás la confirmación en tu correo electrónico.';
}

function closeCheckoutAndReset() {
  $('#checkout-modal').classList.remove('open');
  state.coupon = null;
  resetCheckoutViews();
  showCheckoutStep(1);
  document.querySelectorAll('.pay-method-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('checkout-coupon-input').value = '';
  document.getElementById('checkout-coupon-msg').textContent = '';
  document.getElementById('checkout-email').value = '';
  document.getElementById('checkout-name').value = '';
  document.getElementById('checkout-address').value = '';
  document.getElementById('checkout-city').value = '';
  document.getElementById('checkout-location-msg').className = '';
  document.getElementById('checkout-location-msg').textContent = '';
}

function resetCheckout() {
  showCheckoutView('method');
  showCheckoutStep(1);
  document.getElementById('checkout-continue-btn').disabled = true;
  document.querySelectorAll('.pay-method-card').forEach(c => c.classList.remove('selected'));
}

// ===== ORDERS =====
async function loadUserOrders() {
  if (!isLoggedIn()) { showToast('Inicia sesión'); return; }
  const el = $('#orders-list');
  if (!el) return;
  el.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const orders = await api.getUserOrders(state.token);
    if (!orders.length) {
      el.innerHTML = `
        <div style="text-align:center;padding:60px 20px;color:var(--text2)">
          <div style="font-size:3rem;margin-bottom:16px;opacity:.3"><i class="fa-regular fa-box-open"></i></div>
          <p style="font-size:1.1rem;margin-bottom:8px">No tenés pedidos aún</p>
          <p style="font-size:.85rem">Tus compras aparecerán acá después de realizar tu primer pedido.</p>
        </div>`;
      return;
    }
    el.innerHTML = orders.map(o => {
      const statusColor = {
        'Pendiente': '#f39c12', 'Procesando': '#3498db',
        'Enviado': '#2ecc71', 'Entregado': '#27ae60', 'Cancelado': '#e74c3c',
      }[o.status] || '#6b6863';
      const payStatusColor = o.payment_status === 'Pagado' ? '#2ecc71' : '#f39c12';
      const hasTracking = o.tracking_number;
      return `
      <div class="order-card" style="background:var(--surface);border:1px solid var(--border);border-radius:12px;margin-bottom:16px;overflow:hidden;transition:box-shadow .3s">
        <div class="order-card-header" style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;background:var(--bg2);border-bottom:1px solid var(--border);cursor:pointer" onclick="this.nextElementSibling.classList.toggle('open')">
          <div style="display:flex;align-items:center;gap:12px">
            <span style="font-weight:700;font-size:1.05rem">#${o.id}</span>
            <span style="font-size:.75rem;color:var(--text3)">${new Date(o.created_at).toLocaleDateString('es-CO', {year:'numeric',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'})}</span>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <span style="font-weight:700;color:var(--gold);font-size:1rem">${fmt(o.total)}</span>
            <span style="display:inline-block;padding:4px 12px;border-radius:100px;font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;background:${statusColor}15;color:${statusColor}">${o.status}</span>
            <span style="font-size:.8rem;color:var(--text3)"><i class="fa-regular fa-chevron-down"></i></span>
          </div>
        </div>
        <div class="order-card-body" style="max-height:0;overflow:hidden;transition:max-height .4s ease">
          <div style="padding:20px">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
              <div style="background:var(--bg3);padding:12px 16px;border-radius:8px">
                <div style="font-size:.6rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px">Email</div>
                <div style="font-size:.85rem;font-weight:500;word-break:break-all">${state.user?.email || o.customer_email || '—'}</div>
              </div>
              <div style="background:var(--bg3);padding:12px 16px;border-radius:8px">
                <div style="font-size:.6rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px">Pago</div>
                <div style="font-size:.85rem;font-weight:500;display:flex;align-items:center;gap:6px">
                  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${payStatusColor}"></span>
                  ${o.payment_status}
                </div>
              </div>
            </div>
            ${hasTracking ? `
            <div style="background:var(--bg3);padding:12px 16px;border-radius:8px;margin-bottom:16px">
              <div style="font-size:.6rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px">Número de guía / seguimiento</div>
              <div style="font-size:.85rem;font-weight:600">${hasTracking}</div>
            </div>` : ''}
            <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:8px">Productos</div>
            ${o.items.map(i => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:.85rem">
                <span>${i.product_name} <span style="color:var(--text3);font-size:.75rem">×${i.quantity}</span></span>
                <span style="font-weight:600;color:var(--gold)">${fmt(i.price)}</span>
              </div>
            `).join('')}
            <button class="btn btn-sm btn-outline" style="margin-top:16px" onclick="openReceipt(${o.id})"><i class="fa-regular fa-file-lines"></i> Ver recibo de pago</button>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch (err) { showToast('Error al cargar pedidos'); }
}

// ===== RECIBO DE PAGO =====
async function openReceipt(orderId) {
  try {
    const data = await api.getPaymentReceipt(orderId, state.token);
    const r = data.receipt;
    const payColor = r.payment_status === 'Pagado' ? 'var(--success)' : 'var(--warning)';
    $('#receipt-content').innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)">
        <span style="color:var(--text2)">Pedido</span>
        <strong>#${r.order_id}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)">
        <span style="color:var(--text2)">Cliente</span>
        <strong>${escapeHtml(r.customer)}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)">
        <span style="color:var(--text2)">Email</span>
        <strong style="word-break:break-all;text-align:right">${escapeHtml(r.email)}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)">
        <span style="color:var(--text2)">Fecha</span>
        <strong>${new Date(r.created_at).toLocaleString('es-CO')}</strong>
      </div>
      <div style="padding:12px 0;border-bottom:1px solid var(--border)">
        <div style="font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:8px">Detalle</div>
        ${r.items.map(i => `
          <div style="display:flex;justify-content:space-between;font-size:.82rem;padding:4px 0">
            <span>${escapeHtml(i.product)} <span style="color:var(--text3)">×${i.quantity}</span></span>
            <span>${fmt(i.price)}</span>
          </div>`).join('')}
      </div>
      <div style="display:flex;justify-content:space-between;padding:8px 0;font-size:.85rem">
        <span style="color:var(--text2)">Subtotal</span><span>${fmt(r.subtotal)}</span>
      </div>
      ${r.discount ? `<div style="display:flex;justify-content:space-between;padding:8px 0;font-size:.85rem">
        <span style="color:var(--text2)">Descuento</span><span style="color:var(--success)">-${fmt(r.discount)}</span>
      </div>` : ''}
      <div style="display:flex;justify-content:space-between;padding:8px 0;font-size:.85rem">
        <span style="color:var(--text2)">Envío</span><span>${r.shipping ? fmt(r.shipping) : 'Gratis'}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:12px 0;font-size:1.05rem;border-top:2px solid var(--border);font-weight:700">
        <span>Total</span><span style="color:var(--gold)">${fmt(r.total)}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0">
        <span style="color:var(--text2)">Método de pago</span>
        <span style="text-transform:capitalize">${r.payment_method || 'Contra entrega'}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0">
        <span style="color:var(--text2)">Estado del pago</span>
        <strong style="color:${payColor}">${r.payment_status}</strong>
      </div>
      <button class="btn btn-gold" style="width:100%;justify-content:center;margin-top:8px" onclick="window.print()"><i class="fa-regular fa-print"></i> Imprimir</button>
    `;
    $('#receipt-modal').classList.add('open');
  } catch (err) { showToast(err.message); }
}

// ===== SEGUIMIENTO (INVITADOS) =====
function renderTrackResult(o) {
  const statusColor = {
    'Pendiente': '#f39c12', 'Procesando': '#3498db',
    'Enviado': '#2ecc71', 'Entregado': '#27ae60', 'Cancelado': '#e74c3c',
  }[o.status] || '#6b6863';
  const payColor = o.payment_status === 'Pagado' ? 'var(--success)' : 'var(--warning)';
  $('#track-result').innerHTML = `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <strong style="font-size:1.1rem">Pedido #${o.id}</strong>
        <span style="display:inline-block;padding:4px 12px;border-radius:100px;font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;background:${statusColor}15;color:${statusColor}">${escapeHtml(o.status)}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
        <div style="background:var(--bg3);padding:12px 14px;border-radius:8px">
          <div style="font-size:.6rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px">Fecha</div>
          <div style="font-size:.82rem;font-weight:500">${new Date(o.created_at).toLocaleDateString('es-CO', {year:'numeric',month:'long',day:'numeric'})}</div>
        </div>
        <div style="background:var(--bg3);padding:12px 14px;border-radius:8px">
          <div style="font-size:.6rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px">Pago</div>
          <div style="font-size:.82rem;font-weight:600;color:${payColor}">${o.payment_status}</div>
        </div>
      </div>
      ${o.tracking_number ? `
      <div style="background:var(--bg3);padding:12px 14px;border-radius:8px;margin-bottom:16px">
        <div style="font-size:.6rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px">Número de guía / seguimiento</div>
        <div style="font-size:.9rem;font-weight:700">${escapeHtml(o.tracking_number)}</div>
      </div>` : ''}
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:8px">Productos</div>
      ${o.items.map(i => `
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border);font-size:.85rem">
          <span>${escapeHtml(i.product_name)} <span style="color:var(--text3)">×${i.quantity}</span></span>
        </div>`).join('')}
      <div style="display:flex;justify-content:space-between;padding:12px 0;font-size:1.05rem;font-weight:700;border-top:2px solid var(--border)">
        <span>Total</span><span style="color:var(--gold)">${fmt(o.total)}</span>
      </div>
    </div>`;
}
// ===== NOTIFICATIONS =====
// ===== LIVE CHAT =====
const chatState = {
  socket: null,
  connected: false,
  currentConvId: null,
  guestToken: null,
  conversations: [],
  messages: [],
  guestMode: false,
  initialized: false,
};

function initSocketIO() {
  if (chatState.socket) return;
  chatState.socket = io(API_BASE, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: Infinity,
    auth: { token: state.token || '' },
  });

  chatState.socket.on('connect', () => {
    chatState.connected = true;
    updateChatStatus(true);
    if (chatState.currentConvId) {
      emitJoinChat();
    }
  });

  chatState.socket.on('disconnect', () => {
    chatState.connected = false;
    updateChatStatus(false);
  });

  chatState.socket.on('new_message', (data) => {
    if (chatState.currentConvId === data.conversation_id) {
      addChatMessage(data, data.is_admin ? 'admin' : 'user');
      chatState.messages.push(data);
      scrollChat();
    }
  });

  chatState.socket.on('user_typing', (data) => {
    if (data.is_admin && chatState.currentConvId) {
      $('#chat-typing').style.display = 'flex';
      clearTimeout(chatState._typingTimer);
      chatState._typingTimer = setTimeout(() => {
        $('#chat-typing').style.display = 'none';
      }, 2000);
    }
  });
}

function updateChatStatus(online) {
  const el = $('#chat-status');
  if (!el) return;
  if (online) {
    el.innerHTML = '<i class="fas fa-circle" style="color:var(--success)"></i> En línea';
  } else {
    el.innerHTML = '<i class="fas fa-circle" style="color:var(--text2)"></i> Desconectado';
  }
}

function toggleChat() {
  const w = $('#chat-window');
  w.classList.toggle('open');

  if (w.classList.contains('open')) {
    initSocketIO();
    if (!chatState.initialized) {
      chatState.initialized = true;
      if (isLoggedIn()) {
        showChatConversations();
      }
    }
    if (chatState.currentConvId) {
      emitJoinChat();
    }
  }
}

function showChatWelcome() {
  $('#chat-welcome').style.display = 'block';
  $('#chat-guest-form').style.display = 'none';
  $('#chat-conv-list').style.display = 'none';
  $('#chat-conversation').style.display = 'none';
  $('#chat-footer').style.display = 'none';
}

function showChatGuestForm() {
  $('#chat-welcome').style.display = 'none';
  $('#chat-guest-form').style.display = 'block';
  $('#chat-conv-list').style.display = 'none';
  $('#chat-conversation').style.display = 'none';
  $('#chat-footer').style.display = 'none';
}

async function showChatConversations() {
  $('#chat-welcome').style.display = 'none';
  $('#chat-guest-form').style.display = 'none';
  $('#chat-conversation').style.display = 'none';
  $('#chat-footer').style.display = 'none';
  $('#chat-conv-list').style.display = 'block';

  if (!isLoggedIn()) {
    showChatWelcome();
    return;
  }

  try {
    chatState.conversations = await api.getConversations(state.token);
    const container = $('#chat-conv-items');
    if (!chatState.conversations.length) {
      container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text2);font-size:.8rem">No tienes conversaciones activas</div>';
      return;
    }
    container.innerHTML = chatState.conversations.map(c => `
      <div class="chat-conv-item" data-id="${c.id}" onclick="openChatConversation(${c.id})">
        <div class="chat-conv-item-avatar"><i class="fas fa-user"></i></div>
        <div class="chat-conv-item-info">
          <div class="chat-conv-item-name">${escapeHtml(c.subject || 'Consulta')}</div>
          <div class="chat-conv-item-preview">${escapeHtml(c.last_message || 'Sin mensajes')}</div>
        </div>
        <div class="chat-conv-item-meta">
          ${c.unread_count > 0 ? `<span class="chat-unread">${c.unread_count}</span>` : ''}
        </div>
      </div>
    `).join('');
  } catch (err) {
    showToast('Error al cargar conversaciones');
  }
}

async function openChatConversation(convId) {
  chatState.currentConvId = convId;
  $('#chat-conv-list').style.display = 'none';
  $('#chat-conversation').style.display = 'flex';
  $('#chat-footer').style.display = 'flex';
  $('#chat-msg-area').innerHTML = '';

  if (chatState.socket?.connected) {
    emitJoinChat();
  }

  if (isLoggedIn()) {
    api.markChatRead(convId, state.token).catch(() => {});
  }

  try {
    chatState.messages = isLoggedIn()
      ? await api.getConversationMessages(convId, state.token)
      : [];
    renderChatMessages();
  } catch (err) {
    showToast('Error al cargar mensajes');
  }
}

function renderChatMessages() {
  const area = $('#chat-msg-area');
  area.innerHTML = '';
  chatState.messages.forEach(m => {
    addChatMessage(m, m.is_admin ? 'admin' : 'user');
  });
  scrollChat();
}

function addChatMessage(msg, type) {
  const area = $('#chat-msg-area');
  const div = document.createElement('div');
  const isAdmin = type === 'admin';
  const name = isAdmin ? (msg.sender_name || 'Gracia Clothing') : 'Tú';
  const time = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
  div.className = `chat-msg ${isAdmin ? 'admin' : 'user'}`;
  div.innerHTML = `
    ${isAdmin ? '<div class="chat-msg-avatar"><i class="fas fa-comments"></i></div>' : ''}
    <div class="chat-msg-content">
      <div class="chat-msg-sender">${escapeHtml(name)}</div>
      <div class="chat-msg-text">${escapeHtml(msg.message)}</div>
      <div class="chat-msg-time">${time}</div>
    </div>
  `;
  area.appendChild(div);
}

async function sendChatMessage() {
  const input = $('#chat-input');
  const text = input.value.trim();
  if (!text || !chatState.currentConvId) return;

  input.value = '';
  const tempId = 'temp_' + Date.now();

  // Optimistic UI
  const tempMsg = {
    id: tempId,
    conversation_id: chatState.currentConvId,
    is_admin: false,
    message: text,
    created_at: new Date().toISOString(),
    sender_name: state.user?.name || 'Tú',
  };
  chatState.messages.push(tempMsg);
  addChatMessage(tempMsg, 'user');
  scrollChat();

  try {
    const result = await api.sendChatMessage(
      chatState.currentConvId,
      { message: text },
      state.token,
      chatState.guestToken || ''
    );
    // Replace temp message
    const idx = chatState.messages.findIndex(m => m.id === tempId);
    if (idx !== -1) chatState.messages[idx] = result;
  } catch (err) {
    showToast('Error al enviar mensaje');
  }
}

function emitJoinChat() {
  if (!chatState.socket?.connected || !chatState.currentConvId) return;
  const data = {
    conversation_id: chatState.currentConvId,
    role: 'user',
    user_id: state.user?.id,
    guest_token: chatState.guestToken || '',
  };
  chatState.socket.emit('join_chat', data);
}

function startNewChatFromGuest() {
  const name = $('#chat-guest-name').value.trim() || 'Invitado';
  const message = $('#chat-guest-message').value.trim();
  if (!message) { showToast('Escribe un mensaje'); return; }

  api.createGuestConversation({ guest_name: name, message })
    .then(conv => {
      chatState.currentConvId = conv.id;
      chatState.guestToken = conv.guest_token;
      chatState.messages = [];
      $('#chat-guest-form').style.display = 'none';
      $('#chat-conversation').style.display = 'flex';
      $('#chat-footer').style.display = 'flex';
      $('#chat-msg-area').innerHTML = '';

      // Add the first message
      addChatMessage({
        message: message,
        created_at: new Date().toISOString(),
        sender_name: name,
        is_admin: false,
      }, 'user');

      if (chatState.socket?.connected) {
        emitJoinChat();
      }
    })
    .catch(err => showToast(err.message || 'Error'));
}

function scrollChat() {
  const area = $('#chat-msg-area');
  if (area) area.scrollTop = area.scrollHeight;
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function startNewChat() {
  if (isLoggedIn()) {
    $('#chat-welcome').style.display = 'none';
    $('#chat-conversation').style.display = 'flex';
    $('#chat-footer').style.display = 'flex';
    $('#chat-msg-area').innerHTML = '';

    api.createConversation({ message: '¡Hola! Necesito ayuda.' }, state.token)
      .then(conv => {
        chatState.currentConvId = conv.id;
        chatState.guestToken = null;
        addChatMessage({
          message: '¡Hola! Necesito ayuda.',
          created_at: new Date().toISOString(),
          sender_name: state.user.name,
          is_admin: false,
        }, 'user');
        if (chatState.socket?.connected) {
          emitJoinChat();
        }
      })
      .catch(err => showToast(err.message));
  } else {
    showChatGuestForm();
  }
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  const match = window.location.pathname.match(/^\/producto\/(.+)/);
  if (match) {
    showPage('product', { slug: match[1] });
    return;
  }
  updateCartUI();

  // Header scroll
  window.addEventListener('scroll', () => $('.header')?.classList.toggle('scrolled', window.scrollY > 50));

  // Mobile menu
  $('#mobile-menu-btn')?.addEventListener('click', () => $('#header-nav')?.classList.toggle('open'));
  $$('.header-nav a').forEach(a => a.addEventListener('click', () => $('#header-nav')?.classList.remove('open')));
  window.addEventListener('resize', () => {
    if (window.innerWidth > 992) $('#header-nav')?.classList.remove('open');
  });

  // Cart
  $('#cart-btn')?.addEventListener('click', () => {
    const overlay = $('#cart-overlay');
    const sidebar = $('#cart-sidebar');
    overlay.classList.add('open');
    sidebar.classList.add('open');
    
    // Trigger animation
    sidebar.style.animation = 'none';
    setTimeout(() => {
      sidebar.style.animation = '';
    }, 10);
    
    renderCartItems();
    updateCartFooter();
  });
  $('#cart-overlay')?.addEventListener('click', (e) => { 
    if (e.target === $('#cart-overlay')) {
      $('#cart-overlay').classList.remove('open'); 
      $('#cart-sidebar').classList.remove('open'); 
    }
  });
  $('#cart-close')?.addEventListener('click', () => { 
    $('#cart-overlay').classList.remove('open'); 
    $('#cart-sidebar').classList.remove('open'); 
  });
  $('#checkout-btn')?.addEventListener('click', openCheckout);

  // Coupon
  $('#apply-coupon')?.addEventListener('click', applyCoupon);

  // Order tracking
  $('#track-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const id = $('#track-id').value.trim();
    const email = $('#track-email').value.trim();
    if (!id || !email) return;
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    api.trackOrder(id, email)
      .then(o => renderTrackResult(o))
      .catch(err => { $('#track-result').innerHTML = `<div style="color:var(--danger);text-align:center;font-size:.9rem">${err.message}</div>`; })
      .finally(() => { btn.disabled = false; });
  });

  // Search
  $('#search-form')?.addEventListener('submit', e => {
    e.preventDefault();
    state.search = $('#search-input').value.trim();
    loadProducts();
  });

  // Checkout
  $('#checkout-close')?.addEventListener('click', closeCheckoutAndReset);
  $('#checkout-modal')?.addEventListener('click', e => { if (e.target === $('#checkout-modal')) closeCheckoutAndReset(); });
  $('#submit-order-btn')?.addEventListener('click', submitOrder);

  // Category pills
  $$('.pill').forEach(p => p.addEventListener('click', () => {
    state.category = p.dataset.cat;
    $$('.pill').forEach(x => x.classList.toggle('active', x.dataset.cat === state.category));
    loadProducts();
  }));

  // Live Chat
  $('#chat-btn')?.addEventListener('click', toggleChat);
  $('#chat-close')?.addEventListener('click', toggleChat);
  $('#chat-send')?.addEventListener('click', sendChatMessage);
  $('#chat-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') sendChatMessage(); });
  $('#chat-start-btn')?.addEventListener('click', startNewChat);
  $('#chat-guest-send')?.addEventListener('click', startNewChatFromGuest);
  $('#chat-guest-back')?.addEventListener('click', showChatWelcome);
  $('#chat-conv-back')?.addEventListener('click', showChatConversations);
  $('#chat-conv-new')?.addEventListener('click', startNewChat);

  // Update chat unread badge
  setInterval(() => {
    if (isLoggedIn() && state.token && !$('#chat-window')?.classList.contains('open')) {
      api.getConversations(state.token).then(convs => {
        const total = convs.reduce((s, c) => s + (c.unread_count || 0), 0);
        if (total > 0) {
          $('#chat-unread-badge').textContent = total;
          $('#chat-unread-badge').style.display = 'flex';
        } else {
          $('#chat-unread-badge').style.display = 'none';
        }
      }).catch(() => {});
    }
  }, 15000);

  // Page nav
  $$('.header-nav a[data-page]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    showPage(a.dataset.page);
  }));
  $$('.header-actions a[data-page]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    showPage(a.dataset.page);
  }));

  // Theme toggle + persistence
  const savedTheme = localStorage.getItem('theme') || 'light';
  const isDarkInit = savedTheme === 'dark';
  if (isDarkInit) document.documentElement.setAttribute('data-theme', 'dark');
  if ($('#theme-toggle i')) $('#theme-toggle i').className = isDarkInit ? 'fa-regular fa-sun' : 'fa-regular fa-moon';
  $('#theme-toggle')?.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
    $('#theme-toggle i').className = isDark ? 'fa-regular fa-moon' : 'fa-regular fa-sun';
  });

  // Observe reveal elements
  observeReveal();

  // Register service worker (PWA)
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/frontend/sw.js').catch(() => {});
    });
  }

  // Load initial products
  loadProducts();


});
