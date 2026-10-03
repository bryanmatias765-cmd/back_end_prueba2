/* ==========================================================================
   HARDPC STORE - FRONTEND DE LA TIENDA (JavaScript puro)
   Usa las funciones de comun.js (api, claims, tokens, modales).
   Catálogo, detalle, login/registro, carro persistente, checkout, pago y
   "Mis compras". La gestión (productos, categorías, órdenes) está en el
   Panel de Administración (/panel/), visible solo con rol ADMIN.
   ========================================================================== */
(() => {
  'use strict';

  // Datos propios de la tienda que se suman al estado de sesión de comun.js
  Object.assign(estado, {
    categorias: [],
    filtros: new URLSearchParams(),
    pagina: 1,
    heroSlide: 0,
    heroSlides: [],
  });

  /* ========================================================================
     CATEGORÍAS (GET /api/categorias/ - público)
     ======================================================================== */
  async function cargarCategorias() {
    estado.categorias = await api('categorias/', { auth: false });
    $('#fCategoria').innerHTML = '<option value="">Todas</option>' +
      estado.categorias.map(c => `<option value="${c.id}">${esc(c.nombre)} (${c.total_productos})</option>`).join('');
    $('#listaCategoriasMenu').innerHTML =
      '<button data-cat="">Todas</button>' +
      estado.categorias.map(c => `<button data-cat="${c.id}">${esc(c.nombre)}</button>`).join('');
  }

  /* ========================================================================
     PRODUCTOS (GET /api/productos/ - público, con django-filter)
     ======================================================================== */
  async function cargarProductos() {
    const params = new URLSearchParams(estado.filtros);
    const orden = $('#ordenar').value;
    if (orden) params.set('ordering', orden);
    if (estado.pagina > 1) params.set('page', estado.pagina);
    const qs = params.toString();
    $('#paramFiltros').textContent = 'GET /api/productos/' + (qs ? '?' + qs : '');

    const grilla = $('#grilla');
    try {
      const data = await api('productos/' + (qs ? '?' + qs : ''), { auth: !!estado.access });
      $('#contador').textContent = `${data.count} producto${data.count === 1 ? '' : 's'} encontrados`;
      grilla.innerHTML = data.results.length ? data.results.map(tarjeta).join('')
        : '<div class="vacio">No encontramos productos con esos filtros.</div>';
      pintarPaginacion(data);
    } catch (e) {
      grilla.innerHTML = `<div class="vacio">No se pudo cargar el catálogo: ${esc(e.message)}</div>`;
    }
  }

  function tarjeta(p) {
    return `<article class="card">
      <div class="img" data-ver="${p.id}">${imagen(p)}</div>
      <div class="marca">${esc(p.marca)}</div>
      <h4 data-ver="${p.id}">${esc(p.nombre)}</h4>
      <div class="sku">SKU: ${esc(p.sku)} · ${esc(p.categoria_nombre)}</div>
      <div class="precio">${clp(p.precio)}</div>
      ${stockTxt(p.stock)}${p.activo ? '' : ' <span class="stock sin">(inactivo)</span>'}
      <div class="acciones">
        <button class="btn btn-naranja" data-agregar="${p.id}" ${p.stock <= 0 ? 'disabled' : ''}>Agregar al carro</button>
      </div>
    </article>`;
  }

  function pintarPaginacion(data) {
    const pag = $('#paginacion');
    const total = Math.ceil(data.count / 12);
    if (total <= 1) { pag.innerHTML = ''; return; }
    pag.innerHTML = `
      <button class="btn btn-borde" data-pag="${estado.pagina - 1}" ${data.previous ? '' : 'disabled'}>‹ Anterior</button>
      <span style="align-self:center">Página ${estado.pagina} de ${total}</span>
      <button class="btn btn-borde" data-pag="${estado.pagina + 1}" ${data.next ? '' : 'disabled'}>Siguiente ›</button>`;
  }

  function aplicarFiltros() {
    const fd = new FormData($('#formFiltros'));
    const p = new URLSearchParams();
    for (const [k, v] of fd.entries()) if (v) p.set(k, v);
    const busqueda = $('#inputBuscar').value.trim();
    if (busqueda) p.set('search', busqueda);
    estado.filtros = p;
    estado.pagina = 1;
    const cat = estado.categorias.find(c => String(c.id) === p.get('categoria'));
    $('#tituloCatalogo').textContent = busqueda ? `Resultados para "${busqueda}"` : cat ? cat.nombre : 'Te recomendamos';
    cargarProductos();
  }

  /* ========================================================================
     DETALLE DE PRODUCTO (GET /api/productos/{id}/)
     ======================================================================== */
  async function verProducto(id) {
    try {
      const p = await api(`productos/${id}/`, { auth: !!estado.access });
      abrirModal(`
        <div class="modal ancho">
          <div class="modal-cab"><h3>${esc(p.categoria_nombre)}</h3><button class="cerrar" data-cerrar>×</button></div>
          <div class="modal-cuerpo detalle">
            <div class="img">${imagen(p)}</div>
            <div>
              <div class="marca" style="color:var(--naranja-osc);font-weight:800">${esc(p.marca)}</div>
              <h2>${esc(p.nombre)}</h2>
              <p>${esc(p.descripcion)}</p>
              <div class="precio">${clp(p.precio)}</div>
              ${stockTxt(p.stock)}
              <table class="tabla-ficha">
                <tr><td>SKU</td><td>${esc(p.sku)}</td></tr>
                <tr><td>Marca</td><td>${esc(p.marca)}</td></tr>
                <tr><td>Categoría</td><td>${esc(p.categoria_nombre)}</td></tr>
                <tr><td>Stock físico</td><td>${p.stock} unidades</td></tr>
              </table>
              <div class="fila">
                <input type="number" id="cantDetalle" min="1" max="${p.stock}" value="1" style="width:90px;padding:10px;border:1px solid #ccc;border-radius:8px">
                <button class="btn btn-naranja" style="flex:1" id="btnAgregarDetalle" ${p.stock <= 0 ? 'disabled' : ''}>Agregar al carro</button>
              </div>
              <div class="nota">El stock no se descuenta al agregar al carro: se valida y descuenta al confirmar el pago.</div>
            </div>
          </div>
        </div>`);
      $('#btnAgregarDetalle').onclick = () => agregarAlCarro(p.id, Number($('#cantDetalle').value) || 1);
    } catch (e) { toast(e.message, true); }
  }

  /* ========================================================================
     LOGIN / REGISTRO (POST /api/auth/login/, /api/auth/registro/)
     ======================================================================== */
  function modalLogin(tab = 'login', despues = null) {
    abrirModal(`
      <div class="modal">
        <div class="modal-cab"><h3>Mi cuenta HardPC</h3><button class="cerrar" data-cerrar>×</button></div>
        <div class="modal-cuerpo">
          <div class="tabs"><button data-tab="login">Ingresar</button><button data-tab="registro">Crear cuenta</button></div>
          <form id="formLogin">
            <div class="campo"><label>Usuario</label><input name="username" required autocomplete="username"></div>
            <div class="campo"><label>Contraseña</label><input name="password" type="password" required autocomplete="current-password"></div>
            <div class="error-form"></div>
            <button class="btn btn-naranja btn-bloque">Ingresar</button>
            <div class="nota">Demo: <b>cliente</b> / Cliente12345! · <b>admin</b> / Admin12345!</div>
          </form>
          <form id="formRegistro" class="oculto">
            <div class="fila">
              <div class="campo"><label>Nombre</label><input name="first_name"></div>
              <div class="campo"><label>Apellido</label><input name="last_name"></div>
            </div>
            <div class="campo"><label>Usuario</label><input name="username" required></div>
            <div class="campo"><label>Email</label><input name="email" type="email"></div>
            <div class="campo"><label>Contraseña</label><input name="password" type="password" required autocomplete="new-password"></div>
            <div class="error-form"></div>
            <button class="btn btn-naranja btn-bloque">Crear cuenta de cliente</button>
          </form>
        </div>
      </div>`);

    const cambiarTab = t => {
      $$('[data-tab]').forEach(b => b.classList.toggle('activo', b.dataset.tab === t));
      $('#formLogin').classList.toggle('oculto', t !== 'login');
      $('#formRegistro').classList.toggle('oculto', t !== 'registro');
    };
    $$('[data-tab]').forEach(b => b.onclick = () => cambiarTab(b.dataset.tab));
    cambiarTab(tab);

    const login = async (username, password) => {
      const t = await api('auth/login/', { method: 'POST', body: { username, password }, auth: false });
      guardarTokens(t.access, t.refresh);
      cerrarModal();
      pintarCuenta();
      await actualizarBadge();
      cargarProductos();
      toast(`¡Hola ${t.username}! Rol (claim JWT): ${t.rol}`);
      if (despues) despues();
    };

    $('#formLogin').onsubmit = async ev => {
      ev.preventDefault();
      const f = Object.fromEntries(new FormData(ev.target));
      try { await login(f.username, f.password); } catch (e) { $('.error-form', ev.target).textContent = e.message; }
    };
    $('#formRegistro').onsubmit = async ev => {
      ev.preventDefault();
      const f = Object.fromEntries(new FormData(ev.target));
      try {
        await api('auth/registro/', { method: 'POST', body: f, auth: false });
        await login(f.username, f.password);
      } catch (e) { $('.error-form', ev.target).textContent = e.message; }
    };
  }

  /* ------------------------------------------------------------------------
     LOGOUT: invalida el refresh (blacklist). El carro NO se borra: al volver
     a ingresar se recupera desde PostgreSQL.
     ------------------------------------------------------------------------ */
  async function logout() {
    await cerrarSesion();
    pintarCuenta();
    actualizarBadge();
    cargarProductos();
    toast('Sesión cerrada. Tu carro queda guardado para la próxima vez.');
  }

  /* ------------------------------------------------------------------------
     MENÚ DE CUENTA
     Se arma según los claims del token. La opción "Panel de administración"
     solo aparece si rol == ADMIN; además se muestran/ocultan todos los
     enlaces con clase "solo-admin" (barra superior y footer).
     ------------------------------------------------------------------------ */
  function pintarCuenta() {
    const c = claims();
    const menu = $('#menuCuenta');
    menu.classList.add('oculto');
    mostrarEnlacesAdmin();
    if (!c) { $('#btnCuenta').textContent = 'Hola, ingresa ▾'; return; }
    $('#btnCuenta').textContent = `Hola, ${c.username} ▾`;
    menu.innerHTML = `
      <div class="info"><b>${esc(c.username)}</b>${esc(c.email || '')}<br>
        <span class="chip-rol">rol: ${esc(c.rol)}</span></div>
      ${c.rol === 'ADMIN' ? '<button onclick="location.href=\'/panel/\'">⚙ Panel de administración</button>' : ''}
      <button data-accion="mis-compras">Mis compras</button>
      <button id="menuCarro">Mi carro</button>
      <button id="btnLogout">Cerrar sesión</button>`;
    $('#btnLogout').onclick = logout;
    $('#menuCarro').onclick = abrirCarro;
  }

  /* ========================================================================
     CARRO PERSISTENTE (GET/POST/DELETE /api/carro/, PATCH/DELETE items)
     ======================================================================== */
  async function agregarAlCarro(productoId, cantidad = 1) {
    if (!estado.access) return modalLogin('login', () => agregarAlCarro(productoId, cantidad));
    try {
      const carro = await api('carro/', { method: 'POST', body: { producto: productoId, cantidad } });
      pintarBadge(carro);
      cerrarModal();
      toast('Producto agregado al carro 🛒');
    } catch (e) { toast(e.message, true); }
  }

  function pintarBadge(carro) {
    const b = $('#badgeCarro');
    const n = carro ? carro.cantidad_items : 0;
    b.textContent = n;
    b.classList.toggle('oculto', !n);
  }
  async function actualizarBadge() {
    if (!estado.access) return pintarBadge(null);
    try { pintarBadge(await api('carro/')); } catch { pintarBadge(null); }
  }

  async function abrirCarro() {
    $('#menuCuenta').classList.add('oculto');
    if (!estado.access) return modalLogin('login', abrirCarro);
    let carro;
    try { carro = await api('carro/'); } catch (e) { return toast(e.message, true); }
    pintarBadge(carro);
    const items = carro.items.map(it => `
      <div class="item-carro">
        <div class="mini">${imagen(it.producto)}</div>
        <div>
          <h5>${esc(it.producto.nombre)}</h5>
          <small>${clp(it.producto.precio)} c/u · stock ${it.producto.stock}</small>
          <div class="cantidad">
            <button data-cant="${it.id}" data-valor="${it.cantidad - 1}" ${it.cantidad <= 1 ? 'disabled' : ''}>−</button>
            <b>${it.cantidad}</b>
            <button data-cant="${it.id}" data-valor="${it.cantidad + 1}">+</button>
          </div>
          <button class="quitar" data-quitar="${it.id}">Eliminar</button>
        </div>
        <b>${clp(it.subtotal)}</b>
      </div>`).join('');

    abrirModal(`
      <aside class="drawer">
        <div class="modal-cab"><h3>Mi carro (${carro.cantidad_items})</h3><button class="cerrar" data-cerrar>×</button></div>
        <div class="modal-cuerpo">
          ${items || '<div class="vacio">Tu carro está vacío.</div>'}
          <div class="nota">Tu carro se guarda en la base de datos (PostgreSQL): sigue aquí aunque cierres sesión o entres desde otro dispositivo.</div>
        </div>
        <div class="pie-drawer">
          <div class="total"><span>Total</span><span>${clp(carro.total)}</span></div>
          <button class="btn btn-naranja btn-bloque" id="btnCheckout" ${carro.items.length ? '' : 'disabled'}>Ir a pagar (Checkout)</button>
          <button class="btn btn-borde btn-bloque" id="btnVaciar" ${carro.items.length ? '' : 'disabled'}>Vaciar carro</button>
        </div>
      </aside>`, true);

    $$('[data-cant]').forEach(b => b.onclick = () => cambiarCantidad(b.dataset.cant, Number(b.dataset.valor)));
    $$('[data-quitar]').forEach(b => b.onclick = async () => {
      try { await api(`carro/items/${b.dataset.quitar}/`, { method: 'DELETE' }); abrirCarro(); } catch (e) { toast(e.message, true); }
    });
    $('#btnVaciar').onclick = async () => { await api('carro/', { method: 'DELETE' }); abrirCarro(); };
    $('#btnCheckout').onclick = checkout;
  }

  async function cambiarCantidad(itemId, cantidad) {
    try { await api(`carro/items/${itemId}/`, { method: 'PATCH', body: { cantidad } }); abrirCarro(); }
    catch (e) { toast(e.message, true); }
  }

  /* ========================================================================
     CHECKOUT Y PAGO
     1. POST /api/ordenes/checkout/  -> Orden PENDIENTE con precios congelados
     2. POST /api/ordenes/{id}/pagar/ -> valida stock y lo descuenta (PAGADO)
     ======================================================================== */
  async function checkout() {
    try {
      const orden = await api('ordenes/checkout/', { method: 'POST' });
      pintarBadge(null);
      abrirModal(`
        <div class="modal">
          <div class="modal-cab"><h3>Orden #${orden.id} creada</h3><button class="cerrar" data-cerrar>×</button></div>
          <div class="modal-cuerpo">
            <p>Tu orden quedó en estado <span class="estado PENDIENTE">PENDIENTE</span> con los precios congelados.</p>
            <div class="total"><span>Total a pagar</span><span>${clp(orden.total)}</span></div>
            <div class="nota">Al confirmar el pago se verifica el stock de cada producto. Si alcanza, se descuenta y la orden pasa a PAGADO; si no, el pago se rechaza.</div>
            <button class="btn btn-naranja btn-bloque" id="btnPagarAhora">Pagar ahora (simulado)</button>
            <button class="btn btn-borde btn-bloque" data-cerrar>Pagar más tarde</button>
          </div>
        </div>`);
      $('#btnPagarAhora').onclick = () => pagar(orden.id);
    } catch (e) { toast(e.message, true); }
  }

  async function pagar(id) {
    try {
      await api(`ordenes/${id}/pagar/`, { method: 'POST' });
      toast(`Orden #${id} pagada ✔ Stock descontado.`);
      cargarProductos();
      misCompras();
    } catch (e) { toast(e.message, true); if (!$('.modal.ancho')) misCompras(); }
  }

  /* ========================================================================
     MIS COMPRAS (GET /api/mis-ordenes/) - historial del cliente
     Las órdenes PENDIENTES muestran el botón "Pagar".
     ======================================================================== */
  function tablaOrden(o) {
    const filas = o.detalles.map(d => `<tr><td>${esc(d.nombre_producto)}</td><td>${esc(d.sku)}</td><td>${d.cantidad}</td><td>${clp(d.precio_unitario)}</td><td>${clp(d.subtotal)}</td></tr>`).join('');
    const acciones = o.estado === 'PENDIENTE' ? `<button class="btn btn-naranja" data-pagar="${o.id}">Pagar</button>` : '';
    return `<div class="orden">
      <div class="orden-cab">
        <h5>Orden #${o.id} <small style="color:#888;font-weight:400">${new Date(o.creada).toLocaleString('es-CL')}</small></h5>
        <span class="estado ${o.estado}">${o.estado}</span>
      </div>
      <table><tr><th>Producto</th><th>SKU</th><th>Cant.</th><th>Precio congelado</th><th>Subtotal</th></tr>${filas}</table>
      <div class="orden-cab"><b>Total: ${clp(o.total)}</b><div class="acciones">${acciones}</div></div>
    </div>`;
  }

  async function misCompras() {
    $('#menuCuenta').classList.add('oculto');
    if (!estado.access) return modalLogin('login', misCompras);
    try {
      const data = await api('mis-ordenes/');
      abrirModal(`
        <div class="modal ancho">
          <div class="modal-cab"><h3>Mis compras</h3><button class="cerrar" data-cerrar>×</button></div>
          <div class="modal-cuerpo">${data.results.map(tablaOrden).join('') || '<div class="vacio">Aún no tienes órdenes.</div>'}</div>
        </div>`);
      $$('[data-pagar]').forEach(b => b.onclick = () => pagar(b.dataset.pagar));
    } catch (e) { toast(e.message, true); }
  }


  /* ========================================================================
     BANNER / CARRUSEL: diapositivas armadas con productos reales de la API
     ======================================================================== */
  async function cargarHero() {
    const temas = [
      { titulo: 'Arma tu', grande: 'PC Gamer', cat: 'Tarjetas de Video' },
      { titulo: 'Potencia tu', grande: 'CPU', cat: 'Procesadores' },
      { titulo: 'Más velocidad', grande: 'RAM + SSD', cat: 'Memorias RAM' },
    ];
    for (const t of temas) {
      try {
        const d = await api(`productos/?categoria_nombre=${encodeURIComponent(t.cat)}&en_stock=true&ordering=-precio`, { auth: false });
        if (d.results.length) estado.heroSlides.push({ ...t, productos: d.results.slice(0, 3) });
      } catch { /* sin productos para ese tema */ }
    }
    if (!estado.heroSlides.length) {
      const d = await api('productos/', { auth: false });
      estado.heroSlides.push({ titulo: 'Arma tu', grande: 'PC Gamer', productos: d.results.slice(0, 3) });
    }
    $('#heroPuntos').innerHTML = estado.heroSlides.map((_, i) => `<button data-slide="${i}" aria-label="Diapositiva ${i + 1}"></button>`).join('');
    mostrarSlide(0);
    setInterval(() => mostrarSlide(estado.heroSlide + 1), 7000);
  }

  function mostrarSlide(i) {
    const n = estado.heroSlides.length;
    if (!n) return;
    estado.heroSlide = (i + n) % n;
    const s = estado.heroSlides[estado.heroSlide];
    $('#heroTitulo').textContent = s.titulo;
    $('#heroGrande').textContent = s.grande;
    $('#heroCards').innerHTML = s.productos.map(p => `
      <div class="hero-card" data-ver="${p.id}">
        <div class="img">${imagen(p)}</div>
        <h4>${esc(p.marca)}®</h4>
        <small>${esc(p.nombre)}</small>
        <div class="precio-tag"><span class="p"><sup>$</sup>${Number(p.precio).toLocaleString('es-CL')}</span><span class="t">${esc(p.categoria_nombre.split(' ')[0])}</span></div>
      </div>`).join('');
    $$('#heroPuntos button').forEach((b, k) => b.classList.toggle('activo', k === estado.heroSlide));
  }

  /* ========================================================================
     EVENTOS
     ======================================================================== */
  function eventos() {
    $('#formBuscar').onsubmit = ev => { ev.preventDefault(); aplicarFiltros(); };
    $('#formFiltros').onsubmit = ev => { ev.preventDefault(); aplicarFiltros(); };
    $('#formFiltros').onreset = () => setTimeout(() => { $('#inputBuscar').value = ''; aplicarFiltros(); });
    $('#ordenar').onchange = () => { estado.pagina = 1; cargarProductos(); };
    $('#heroPrev').onclick = () => mostrarSlide(estado.heroSlide - 1);
    $('#heroNext').onclick = () => mostrarSlide(estado.heroSlide + 1);
    $('#btnCarro').onclick = abrirCarro;
    $('#linkCarroFooter').onclick = ev => { ev.preventDefault(); abrirCarro(); };
    $('#btnCategorias').onclick = () => {
      const p = $('#panelCategorias');
      p.classList.toggle('oculto');
      $('#btnCategorias').setAttribute('aria-expanded', String(!p.classList.contains('oculto')));
    };
    $('#btnCuenta').onclick = ev => {
      ev.stopPropagation();
      if (!estado.access) return modalLogin();
      $('#menuCuenta').classList.toggle('oculto');
    };

    // Delegación de eventos para elementos creados dinámicamente
    document.addEventListener('click', ev => {
      const t = ev.target.closest('[data-ver],[data-agregar],[data-pag],[data-cat],[data-accion],[data-slide],[data-cerrar]');
      if (!ev.target.closest('.cuenta')) $('#menuCuenta').classList.add('oculto');
      if (ev.target.classList.contains('fondo')) return cerrarModal();
      if (!t) return;
      if (t.dataset.cerrar !== undefined) return cerrarModal();
      if (t.dataset.ver) return verProducto(t.dataset.ver);
      if (t.dataset.agregar) return agregarAlCarro(Number(t.dataset.agregar));
      if (t.dataset.pag) { estado.pagina = Number(t.dataset.pag); cargarProductos(); return window.scrollTo({ top: $('main').offsetTop - 100, behavior: 'smooth' }); }
      if (t.dataset.slide) return mostrarSlide(Number(t.dataset.slide));
      if (t.dataset.cat !== undefined) {
        $('#fCategoria').value = t.dataset.cat;
        $('#panelCategorias').classList.add('oculto');
        aplicarFiltros();
        return window.scrollTo({ top: $('main').offsetTop - 100, behavior: 'smooth' });
      }
      if (t.dataset.accion === 'mis-compras') { ev.preventDefault(); return misCompras(); }
    });
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape') cerrarModal(); });
  }

  /* ========================================================================
     INICIO
     ======================================================================== */
  window.alCambiarSesion = pintarCuenta;
  eventos();
  pintarCuenta();
  actualizarBadge();
  cargarCategorias().catch(e => toast('No se pudo conectar con la API: ' + e.message, true));
  cargarProductos();
  cargarHero().catch(() => {});
})();
