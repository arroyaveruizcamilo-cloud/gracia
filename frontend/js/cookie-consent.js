/* ===== COOKIE CONSENT BANNER ===== */
(function() {
  const STORAGE_KEY = 'gracia_cookie_consent';
  const CONSENT_VERSION = '1.0';

  function getConsent() {
    try {
      const data = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (data && data.version === CONSENT_VERSION) return data;
    } catch {}
    return null;
  }

  function saveConsent(preferences) {
    const data = { version: CONSENT_VERSION, timestamp: new Date().toISOString(), ...preferences };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    applyConsent(data);
  }

  function applyConsent(data) {
    if (!data) return;
    if (data.analytics) {
      loadGA();
    }
    if (data.marketing) {
      loadMetaPixel();
    }
  }

  function loadGA() {
    if (window._gaLoaded) return;
    const gaId = window.__GA_ID__;
    if (!gaId || !gaId.startsWith('G-')) return;
    window._gaLoaded = true;
    const s = document.createElement('script');
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${gaId}`;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', gaId, { anonymize_ip: true });
  }

  function loadMetaPixel() {
    if (window._fbqLoaded) return;
    const pid = window.__META_PIXEL_ID__;
    if (!pid || pid.length !== 15) return;
    window._fbqLoaded = true;
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', pid);
    fbq('track', 'PageView');
  }

  function createBannerHTML() {
    return `
      <div class="cookie-banner" id="cookie-banner">
        <div class="cookie-banner-inner">
          <div class="cookie-banner-text">
            <p>Utilizamos cookies para mejorar tu experiencia, medir el trafico del sitio y personalizar el contenido. Puedes aceptar todas, rechazar las opcionales, o configurar tus preferencias. <a href="/legal/privacidad">Politica de Privacidad</a></p>
          </div>
          <div class="cookie-banner-actions">
            <button class="cookie-btn cookie-btn-reject" id="cookie-reject">Rechazar</button>
            <button class="cookie-btn cookie-btn-settings" id="cookie-settings-btn">Configurar</button>
            <button class="cookie-btn cookie-btn-accept" id="cookie-accept-all">Aceptar Todas</button>
          </div>
        </div>
      </div>
      <div class="cookie-settings-overlay" id="cookie-settings-overlay">
        <div class="cookie-settings-modal">
          <h3>Configuracion de Cookies</h3>
          <p>Gestiona que tipos de cookies quieres permitir. Las cookies estrictamente necesarias no se pueden desactivar porque son esenciales para el funcionamiento del sitio.</p>
          <div class="cookie-option">
            <div class="cookie-option-info">
              <h4>Necesarias</h4>
              <span>Carrito, sesion, seguridad</span>
            </div>
            <label class="cookie-toggle">
              <input type="checkbox" checked disabled>
              <span class="slider"></span>
            </label>
          </div>
          <div class="cookie-option">
            <div class="cookie-option-info">
              <h4>Analytics</h4>
              <span>Google Analytics — mide visitas y comportamiento</span>
            </div>
            <label class="cookie-toggle">
              <input type="checkbox" id="cookie-analytics-toggle">
              <span class="slider"></span>
            </label>
          </div>
          <div class="cookie-option">
            <div class="cookie-option-info">
              <h4>Marketing</h4>
              <span>Meta Pixel — publicidad personalizada</span>
            </div>
            <label class="cookie-toggle">
              <input type="checkbox" id="cookie-marketing-toggle">
              <span class="slider"></span>
            </label>
          </div>
          <div class="cookie-settings-actions">
            <button class="cookie-btn cookie-btn-reject" id="cookie-settings-close">Cancelar</button>
            <button class="cookie-btn cookie-btn-accept" id="cookie-save-prefs">Guardar Preferencias</button>
          </div>
        </div>
      </div>
    `;
  }

  function init() {
    const existing = getConsent();
    if (existing) {
      applyConsent(existing);
      return;
    }

    document.body.insertAdjacentHTML('beforeend', createBannerHTML());

    requestAnimationFrame(() => {
      setTimeout(() => {
        const banner = document.getElementById('cookie-banner');
        if (banner) banner.classList.add('visible');
      }, 1500);
    });

    document.getElementById('cookie-accept-all').addEventListener('click', () => {
      saveConsent({ necessary: true, analytics: true, marketing: true });
      hideBanner();
    });

    document.getElementById('cookie-reject').addEventListener('click', () => {
      saveConsent({ necessary: true, analytics: false, marketing: false });
      hideBanner();
    });

    document.getElementById('cookie-settings-btn').addEventListener('click', () => {
      const overlay = document.getElementById('cookie-settings-overlay');
      if (overlay) overlay.classList.add('visible');
    });

    document.getElementById('cookie-settings-close').addEventListener('click', () => {
      document.getElementById('cookie-settings-overlay').classList.remove('visible');
    });

    document.getElementById('cookie-settings-overlay').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) {
        e.currentTarget.classList.remove('visible');
      }
    });

    document.getElementById('cookie-save-prefs').addEventListener('click', () => {
      const analytics = document.getElementById('cookie-analytics-toggle').checked;
      const marketing = document.getElementById('cookie-marketing-toggle').checked;
      saveConsent({ necessary: true, analytics, marketing });
      document.getElementById('cookie-settings-overlay').classList.remove('visible');
      hideBanner();
    });
  }

  function hideBanner() {
    const banner = document.getElementById('cookie-banner');
    if (banner) {
      banner.classList.remove('visible');
      setTimeout(() => banner.remove(), 500);
    }
  }

  // Expose for re-opening settings from footer
  window.openCookieSettings = function() {
    const consent = getConsent();
    document.body.insertAdjacentHTML('beforeend', createBannerHTML());
    const overlay = document.getElementById('cookie-settings-overlay');
    const banner = document.getElementById('cookie-banner');
    if (banner) banner.classList.remove('visible');
    if (overlay) overlay.classList.add('visible');
    if (consent) {
      const a = document.getElementById('cookie-analytics-toggle');
      const m = document.getElementById('cookie-marketing-toggle');
      if (a) a.checked = consent.analytics;
      if (m) m.checked = consent.marketing;
    }
    overlay.addEventListener('click', (e) => {
      if (e.target === e.currentTarget) e.currentTarget.classList.remove('visible');
    });
    document.getElementById('cookie-settings-close').addEventListener('click', () => {
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 300);
    });
    document.getElementById('cookie-accept-all').addEventListener('click', () => {
      saveConsent({ necessary: true, analytics: true, marketing: true });
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 300);
    });
    document.getElementById('cookie-reject').addEventListener('click', () => {
      saveConsent({ necessary: true, analytics: false, marketing: false });
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 300);
    });
    document.getElementById('cookie-save-prefs').addEventListener('click', () => {
      const a = document.getElementById('cookie-analytics-toggle').checked;
      const m = document.getElementById('cookie-marketing-toggle').checked;
      saveConsent({ necessary: true, analytics: a, marketing: m });
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 300);
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
