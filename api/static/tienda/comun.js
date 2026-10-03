/* ==========================================================================
   HARDPC STORE - FUNCIONES COMUNES (tienda y panel de administración)
   - Sesión JWT: guarda access/refresh en localStorage y lee los claims.
   - api(): cliente HTTP que envía "Authorization: Bearer <access>" y, si el
     access expiró (401), lo renueva con el refresh y reintenta.
   - Utilidades de formato, íconos de productos, modales y mensajes.
   Se carga ANTES que tienda.js / panel.js, por eso todo queda global.
   ========================================================================== */
'use strict';

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const clp = n => '$' + Number(n).toLocaleString('es-CL');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ------------------------------------------------------------------------
   ESTADO DE LA SESIÓN (tokens JWT)
   Solo se guardan los tokens en el navegador; el carro vive en la BD.
   ------------------------------------------------------------------------ */
const estado = {
  access: localStorage.getItem('access'),
  refresh: localStorage.getItem('refresh'),
};

/* ------------------------------------------------------------------------
   JWT: decodificar el payload (parte central del token, en base64url)
   para leer los claims personalizados: rol, username, email.
   OJO: esto solo sirve para MOSTRAR u OCULTAR opciones en pantalla. La
   seguridad real está en el backend (permisos DRF validan el token firmado).
   ------------------------------------------------------------------------ */
function claims() {
  if (!estado.access) return null;
  try {
    const b64 = estado.access.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(decodeURIComponent(escape(atob(b64))));
  } catch { return null; }
}
const esAdmin = () => claims()?.rol === 'ADMIN';

function guardarTokens(access, refresh) {
  estado.access = access;
  if (refresh) estado.refresh = refresh;
  localStorage.setItem('access', access);
  if (refresh) localStorage.setItem('refresh', refresh);
}
function borrarTokens() {
  estado.access = estado.refresh = null;
  localStorage.removeItem('access');
  localStorage.removeItem('refresh');
}

/* ------------------------------------------------------------------------
   CLIENTE HTTP DE LA API
   - Agrega el header Authorization si hay token.
   - Ante un 401 intenta renovar con /api/auth/refresh/ una sola vez.
   - Si el refresh también venció: cierra la sesión local, avisa a la página
     (window.alCambiarSesion) y reintenta como anónimo.
   ------------------------------------------------------------------------ */
async function api(ruta, { method = 'GET', body, auth = true, reintento = true } = {}) {
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json' };
  if (auth && estado.access) headers.Authorization = 'Bearer ' + estado.access;
  const resp = await fetch('/api/' + ruta, { method, headers, body: body ? JSON.stringify(body) : undefined });

  if (resp.status === 401 && auth && estado.refresh && reintento) {
    const r = await fetch('/api/auth/refresh/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: estado.refresh }),
    });
    if (r.ok) {
      const t = await r.json();
      guardarTokens(t.access, t.refresh);
      return api(ruta, { method, body, auth, reintento: false });
    }
    borrarTokens();
    window.alCambiarSesion?.();
    return api(ruta, { method, body, auth: false, reintento: false });
  }

  const data = resp.status === 204 ? null : await resp.json().catch(() => null);
  if (!resp.ok) {
    const err = new Error(mensajeError(data) || `Error ${resp.status}`);
    err.status = resp.status;
    throw err;
  }
  return data;
}

function mensajeError(data) {
  if (!data) return '';
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  return Object.entries(data).map(([k, v]) => `${k}: ${[].concat(v).join(' ')}`).join('\n');
}

/* ------------------------------------------------------------------------
   LOGOUT: invalida el refresh en el servidor (blacklist) y borra los tokens.
   ------------------------------------------------------------------------ */
async function cerrarSesion() {
  try { await api('auth/logout/', { method: 'POST', body: { refresh: estado.refresh } }); } catch { /* ya inválido */ }
  borrarTokens();
}

function toast(msg, error = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast' + (error ? ' error' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add('oculto'), 3500);
}

/* ------------------------------------------------------------------------
   MODALES
   ------------------------------------------------------------------------ */
function abrirModal(html, esDrawer = false) {
  $('#capaModal').innerHTML = `<div class="fondo" ${esDrawer ? 'style="padding:0"' : ''}>${html}</div>`;
}
function cerrarModal() { $('#capaModal').innerHTML = ''; }

/* ------------------------------------------------------------------------
   ENLACES SOLO PARA ADMIN
   Todo elemento con la clase "solo-admin" se muestra únicamente si el
   claim "rol" del token es ADMIN (clientes y visitantes no lo ven).
   ------------------------------------------------------------------------ */
function mostrarEnlacesAdmin() {
  $$('.solo-admin').forEach(el => el.classList.toggle('oculto', !esAdmin()));
}

/* ------------------------------------------------------------------------
   ÍCONOS SVG POR CATEGORÍA (los productos de ejemplo no tienen foto)
   ------------------------------------------------------------------------ */
function icono(categoria = '') {
  const c = categoria.toLowerCase();
  const n = '#ff6a00', k = '#1a1a1a';
  if (c.includes('video')) return `<svg viewBox="0 0 100 100"><rect x="6" y="28" width="80" height="40" rx="5" fill="${k}"/><circle cx="32" cy="48" r="13" fill="${n}"/><circle cx="62" cy="48" r="13" fill="${n}"/><circle cx="32" cy="48" r="4" fill="${k}"/><circle cx="62" cy="48" r="4" fill="${k}"/><rect x="14" y="68" width="40" height="7" fill="${n}"/><rect x="86" y="34" width="8" height="28" fill="#555"/></svg>`;
  if (c.includes('ram') || c.includes('memoria')) return `<svg viewBox="0 0 100 100"><rect x="8" y="30" width="84" height="32" rx="3" fill="${k}"/><rect x="8" y="24" width="84" height="8" fill="${n}"/>${[16, 32, 48, 64].map(x => `<rect x="${x}" y="38" width="12" height="16" fill="#444"/>`).join('')}${Array.from({ length: 14 }, (_, i) => `<rect x="${12 + i * 5.6}" y="62" width="3" height="8" fill="${n}"/>`).join('')}</svg>`;
  if (c.includes('almacen')) return `<svg viewBox="0 0 100 100"><rect x="6" y="36" width="88" height="28" rx="4" fill="${k}"/><rect x="14" y="42" width="20" height="16" fill="${n}"/><rect x="40" y="42" width="14" height="16" fill="#444"/><rect x="58" y="42" width="14" height="16" fill="#444"/><circle cx="86" cy="50" r="4" fill="#666"/></svg>`;
  if (c.includes('placa')) return `<svg viewBox="0 0 100 100"><rect x="12" y="10" width="76" height="80" rx="4" fill="${k}"/><rect x="24" y="22" width="24" height="24" fill="${n}"/><rect x="56" y="20" width="5" height="34" fill="#555"/><rect x="66" y="20" width="5" height="34" fill="#555"/><rect x="22" y="58" width="56" height="6" fill="${n}"/><rect x="22" y="72" width="56" height="6" fill="#555"/></svg>`;
  if (c.includes('fuente')) return `<svg viewBox="0 0 100 100"><rect x="12" y="22" width="76" height="56" rx="5" fill="${k}"/><circle cx="44" cy="50" r="20" fill="#333" stroke="${n}" stroke-width="3"/><path d="M44 32v36M26 50h36M31 37l26 26M57 37 31 63" stroke="#555" stroke-width="2"/><path d="M76 38l-6 12h6l-6 12" stroke="${n}" stroke-width="3" fill="none"/></svg>`;
  return `<svg viewBox="0 0 100 100"><rect x="22" y="22" width="56" height="56" rx="6" fill="${k}"/><rect x="34" y="34" width="32" height="32" rx="3" fill="${n}"/>${[30, 42, 54, 66].map(p => `<rect x="${p}" y="10" width="4" height="12" fill="#666"/><rect x="${p}" y="78" width="4" height="12" fill="#666"/><rect x="10" y="${p}" width="12" height="4" fill="#666"/><rect x="78" y="${p}" width="12" height="4" fill="#666"/>`).join('')}</svg>`;
}
const imagen = p => p.imagen_url ? `<img src="${esc(p.imagen_url)}" alt="${esc(p.nombre)}">` : icono(p.categoria_nombre);

function stockTxt(s) {
  if (s <= 0) return '<span class="stock sin">Sin stock</span>';
  if (s <= 5) return `<span class="stock bajo">¡Últimas ${s} unidades!</span>`;
  return `<span class="stock ok">Stock disponible: ${s}</span>`;
}
