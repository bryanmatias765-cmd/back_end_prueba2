/* ==========================================================================
   HARDPC STORE - PANEL DE ADMINISTRACIÓN (JavaScript puro)
   Usa las funciones de comun.js (api, claims, tokens, modales).

   CONTROL DE ACCESO:
   1. Al cargar se lee el claim "rol" del JWT guardado.
   2. Si no hay sesión o el rol NO es ADMIN -> se muestra "Acceso restringido"
      y no se consulta ningún dato de gestión.
   3. Si es ADMIN -> se muestra el panel. Cada petición igual es validada por
      el servidor con el permiso EsAdministrador (responde 403 si no es ADMIN),
      así que ocultar la interfaz es comodidad, no la barrera de seguridad.
   ========================================================================== */
(() => {
  'use strict';

  const ESTADOS = ['PENDIENTE', 'PAGADO', 'ENTREGADO', 'CANCELADO'];
  const SECCIONES = ['resumen', 'productos', 'categorias', 'ordenes'];
  const panel = { seccion: SECCIONES.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'resumen', categorias: [], prod: { pagina: 1, search: '', categoria: '' }, ord: { estado: '', search: '', pagina: 1 } };

  /* ========================================================================
     CONTROL DE ACCESO
     ======================================================================== */
  function verificarAcceso() {
    const c = claims();
    mostrarEnlacesAdmin();
    if (c?.rol === 'ADMIN') {
      $('#vistaAcceso').classList.add('oculto');
      $('#vistaPanel').classList.remove('oculto');
      pintarUsuario(c);
      irA(panel.seccion);
      return;
    }
    $('#vistaPanel').classList.add('oculto');
    $('#vistaAcceso').classList.remove('oculto');
    $('#panelUsuario').innerHTML = '<a href="/" class="btn btn-borde">Volver a la tienda</a>';
    $('#accesoMensaje').textContent = c
      ? `Tu cuenta "${c.username}" tiene rol ${c.rol}: no tiene permisos de administración. Ingresa con una cuenta de administrador.`
      : 'Esta sección es exclusiva para Administradores de TI. Inicia sesión con una cuenta de administrador.';
  }

  function pintarUsuario(c) {
    $('#panelUsuario').innerHTML = `
      <span class="panel-user">${esc(c.username)} <span class="chip-rol">rol: ${esc(c.rol)}</span></span>
      <a href="/" class="btn btn-borde">Ver tienda</a>
      <button class="btn btn-naranja" id="btnSalir">Cerrar sesión</button>`;
    $('#btnSalir').onclick = async () => { await cerrarSesion(); location.href = '/'; };
  }

  // Login dentro del panel: si el usuario que entra no es ADMIN, sigue bloqueado.
  $('#formLoginAdmin').onsubmit = async ev => {
    ev.preventDefault();
    const f = Object.fromEntries(new FormData(ev.target));
    const err = $('.error-form', ev.target);
    try {
      const t = await api('auth/login/', { method: 'POST', body: f, auth: false });
      guardarTokens(t.access, t.refresh);
      if (t.rol !== 'ADMIN') err.textContent = 'Ingresaste, pero tu cuenta no es de administrador.';
      verificarAcceso();
    } catch (e) { err.textContent = e.message; }
  };

  // Si el token vence o el servidor responde 403, se vuelve a la pantalla de acceso.
  async function apiAdmin(ruta, opciones) {
    try { return await api(ruta, opciones); }
    catch (e) {
      if (e.status === 401 || e.status === 403) verificarAcceso();
      throw e;
    }
  }

  /* ========================================================================
     NAVEGACIÓN ENTRE SECCIONES
     ======================================================================== */
  function irA(seccion) {
    panel.seccion = seccion;
    history.replaceState(null, '', '#' + seccion);  // la sección queda en la URL
    $$('[data-seccion]').forEach(b => b.classList.toggle('activo', b.dataset.seccion === seccion));
    const acciones = { resumen: vistaResumen, productos: vistaProductos, categorias: vistaCategorias, ordenes: vistaOrdenes };
    $('#panelContenido').innerHTML = '<div class="vacio">Cargando…</div>';
    acciones[seccion]().catch(e => { $('#panelContenido').innerHTML = `<div class="vacio">Error: ${esc(e.message)}</div>`; });
  }
  $$('[data-seccion]').forEach(b => b.onclick = () => irA(b.dataset.seccion));

  const titulo = (t, sub, extra = '') => `
    <div class="panel-titulo"><div><h2>${t}</h2><p>${sub}</p></div>${extra}</div>`;

  /* ========================================================================
     1. RESUMEN (GET /api/admin/resumen/)
     ======================================================================== */
  async function vistaResumen() {
    const [r, bajo, ultimas] = await Promise.all([
      apiAdmin('admin/resumen/'),
      apiAdmin('productos/?ordering=stock&page_size=6&activo=true'),
      apiAdmin('ordenes/?ordering=-creada&page_size=5'),
    ]);
    const kpi = (valor, etiqueta, clase = '') => `<div class="kpi ${clase}"><b>${valor}</b><span>${etiqueta}</span></div>`;
    $('#panelContenido').innerHTML = `
      ${titulo('Resumen', 'Estado general de la tienda')}
      <div class="kpis">
        ${kpi(clp(r.ventas_confirmadas), 'Ventas confirmadas (PAGADO + ENTREGADO)', 'destacado')}
        ${kpi(r.ordenes.PENDIENTE, 'Órdenes pendientes de pago')}
        ${kpi(r.ordenes.PAGADO, 'Órdenes pagadas por entregar')}
        ${kpi(r.ordenes.ENTREGADO, 'Órdenes entregadas')}
        ${kpi(r.ordenes.CANCELADO, 'Órdenes canceladas')}
        ${kpi(r.productos_activos, 'Productos activos')}
        ${kpi(r.stock_bajo, 'Con stock bajo (≤ 5)', r.stock_bajo ? 'alerta' : '')}
        ${kpi(r.sin_stock, 'Sin stock', r.sin_stock ? 'peligro' : '')}
        ${kpi(r.categorias, 'Categorías')}
        ${kpi(r.clientes, 'Clientes registrados')}
      </div>
      <div class="panel-dos">
        <div class="caja">
          <h3>Productos con menos stock</h3>
          <table class="tabla">
            <tr><th>Producto</th><th>SKU</th><th>Stock</th></tr>
            ${bajo.results.map(p => `<tr><td>${esc(p.nombre)}</td><td>${esc(p.sku)}</td><td>${badgeStock(p.stock)}</td></tr>`).join('')}
          </table>
        </div>
        <div class="caja">
          <h3>Últimas órdenes</h3>
          <table class="tabla">
            <tr><th>#</th><th>Cliente</th><th>Total</th><th>Estado</th></tr>
            ${ultimas.results.map(o => `<tr><td>${o.id}</td><td>${esc(o.usuario)}</td><td>${clp(o.total)}</td><td><span class="estado ${o.estado}">${o.estado}</span></td></tr>`).join('') || '<tr><td colspan="4">Sin órdenes todavía.</td></tr>'}
          </table>
        </div>
      </div>`;
  }

  const badgeStock = s => `<span class="stock ${s <= 0 ? 'sin' : s <= 5 ? 'bajo' : 'ok'}">${s}</span>`;

  /* ========================================================================
     2. PRODUCTOS - gestión de inventario
        GET /api/productos/ (con filtros) · POST · PUT /{id}/ · DELETE /{id}/
     ======================================================================== */
  async function cargarCategoriasPanel() {
    panel.categorias = await apiAdmin('categorias/');
  }

  async function vistaProductos() {
    await cargarCategoriasPanel();
    const f = panel.prod;
    const qs = new URLSearchParams({ page: f.pagina, page_size: 15, ordering: 'nombre' });
    if (f.search) qs.set('search', f.search);
    if (f.categoria) qs.set('categoria', f.categoria);
    const data = await apiAdmin('productos/?' + qs);
    const paginas = Math.max(1, Math.ceil(data.count / 15));

    $('#panelContenido').innerHTML = `
      ${titulo('Productos', `${data.count} productos en el catálogo`, '<button class="btn btn-naranja" id="btnNuevoProd">+ Nuevo producto</button>')}
      <form class="panel-filtros" id="filtrosProd">
        <input name="search" placeholder="Buscar por nombre, marca o SKU" value="${esc(f.search)}">
        <select name="categoria"><option value="">Todas las categorías</option>
          ${panel.categorias.map(c => `<option value="${c.id}" ${String(c.id) === f.categoria ? 'selected' : ''}>${esc(c.nombre)}</option>`).join('')}
        </select>
        <button class="btn btn-negro">Filtrar</button>
      </form>
      <div class="tabla-scroll"><table class="tabla">
        <tr><th>SKU</th><th>Producto</th><th>Marca</th><th>Categoría</th><th>Precio</th><th>Stock</th><th>Estado</th><th></th></tr>
        ${data.results.map(p => `
          <tr class="${p.activo ? '' : 'inactivo'}">
            <td><code>${esc(p.sku)}</code></td><td><b>${esc(p.nombre)}</b></td><td>${esc(p.marca)}</td>
            <td>${esc(p.categoria_nombre)}</td><td>${clp(p.precio)}</td><td>${badgeStock(p.stock)}</td>
            <td>${p.activo ? '<span class="estado PAGADO">Activo</span>' : '<span class="estado CANCELADO">Inactivo</span>'}</td>
            <td class="acciones-fila">
              <button class="btn btn-borde btn-chico" data-editar-prod="${p.id}">Editar</button>
              <button class="btn btn-borde btn-chico peligro" data-borrar-prod="${p.id}" data-nombre="${esc(p.nombre)}">Eliminar</button>
            </td>
          </tr>`).join('') || '<tr><td colspan="8">No hay productos con ese filtro.</td></tr>'}
      </table></div>
      <div class="paginacion">
        <button class="btn btn-borde" data-pag-prod="${f.pagina - 1}" ${data.previous ? '' : 'disabled'}>‹ Anterior</button>
        <span style="align-self:center">Página ${f.pagina} de ${paginas}</span>
        <button class="btn btn-borde" data-pag-prod="${f.pagina + 1}" ${data.next ? '' : 'disabled'}>Siguiente ›</button>
      </div>`;

    $('#filtrosProd').onsubmit = ev => {
      ev.preventDefault();
      const d = Object.fromEntries(new FormData(ev.target));
      Object.assign(panel.prod, { search: d.search.trim(), categoria: d.categoria, pagina: 1 });
      irA('productos');
    };
    $('#btnNuevoProd').onclick = () => formProducto();
    $$('[data-pag-prod]').forEach(b => b.onclick = () => { panel.prod.pagina = Number(b.dataset.pagProd); irA('productos'); });
    $$('[data-editar-prod]').forEach(b => b.onclick = async () => formProducto(await apiAdmin(`productos/${b.dataset.editarProd}/`)));
    $$('[data-borrar-prod]').forEach(b => b.onclick = () => confirmar(
      `¿Eliminar "${b.dataset.nombre}"? Si ya tiene ventas se desactivará en vez de borrarse.`,
      async () => {
        await apiAdmin(`productos/${b.dataset.borrarProd}/`, { method: 'DELETE' });
        toast('Producto eliminado / desactivado');
        irA('productos');
      }));
  }

  // Formulario para crear (POST) o editar (PUT) un producto.
  function formProducto(p = null) {
    const v = campo => esc(p?.[campo] ?? '');
    abrirModal(`
      <div class="modal ancho">
        <div class="modal-cab"><h3>${p ? 'Editar producto #' + p.id : 'Nuevo producto'}</h3><button class="cerrar" data-cerrar>×</button></div>
        <form class="modal-cuerpo form-grid" id="formProd">
          <div class="campo"><label>Nombre</label><input name="nombre" required value="${v('nombre')}"></div>
          <div class="campo"><label>Marca</label><input name="marca" required value="${v('marca')}"></div>
          <div class="campo"><label>Código SKU</label><input name="sku" required value="${v('sku')}"></div>
          <div class="campo"><label>Categoría</label><select name="categoria" required>
            ${panel.categorias.map(c => `<option value="${c.id}" ${p?.categoria === c.id ? 'selected' : ''}>${esc(c.nombre)}</option>`).join('')}
          </select></div>
          <div class="campo"><label>Precio unitario (CLP)</label><input name="precio" type="number" min="1" required value="${v('precio')}"></div>
          <div class="campo"><label>Stock físico</label><input name="stock" type="number" min="0" required value="${p ? p.stock : 0}"></div>
          <div class="campo completo"><label>URL de imagen (opcional)</label><input name="imagen_url" type="url" value="${v('imagen_url')}"></div>
          <div class="campo completo"><label>Descripción</label><textarea name="descripcion" rows="3">${v('descripcion')}</textarea></div>
          <label class="check completo"><input type="checkbox" name="activo" ${!p || p.activo ? 'checked' : ''}> Producto activo (visible en la tienda)</label>
          <div class="error-form completo"></div>
          <div class="completo fila-botones">
            <button type="button" class="btn btn-borde" data-cerrar>Cancelar</button>
            <button class="btn btn-naranja">${p ? 'Guardar cambios' : 'Crear producto'}</button>
          </div>
        </form>
      </div>`);
    $('#formProd').onsubmit = async ev => {
      ev.preventDefault();
      const d = Object.fromEntries(new FormData(ev.target));
      d.activo = ev.target.activo.checked;
      d.categoria = Number(d.categoria);
      try {
        await apiAdmin(p ? `productos/${p.id}/` : 'productos/', { method: p ? 'PUT' : 'POST', body: d });
        cerrarModal();
        toast(p ? 'Producto actualizado' : 'Producto creado');
        irA('productos');
      } catch (e) { $('.error-form', ev.target).textContent = e.message; }
    };
  }

  /* ========================================================================
     3. CATEGORÍAS  GET/POST /api/categorias/ · PUT/DELETE /api/categorias/{id}/
     ======================================================================== */
  async function vistaCategorias() {
    await cargarCategoriasPanel();
    $('#panelContenido').innerHTML = `
      ${titulo('Categorías', `${panel.categorias.length} categorías`, '<button class="btn btn-naranja" id="btnNuevaCat">+ Nueva categoría</button>')}
      <div class="tabla-scroll"><table class="tabla">
        <tr><th>Nombre</th><th>Descripción</th><th>Productos activos</th><th></th></tr>
        ${panel.categorias.map(c => `
          <tr><td><b>${esc(c.nombre)}</b></td><td>${esc(c.descripcion) || '<span style="color:#999">—</span>'}</td><td>${c.total_productos}</td>
            <td class="acciones-fila">
              <button class="btn btn-borde btn-chico" data-editar-cat="${c.id}">Editar</button>
              <button class="btn btn-borde btn-chico peligro" data-borrar-cat="${c.id}" data-nombre="${esc(c.nombre)}">Eliminar</button>
            </td></tr>`).join('')}
      </table></div>`;

    $('#btnNuevaCat').onclick = () => formCategoria();
    $$('[data-editar-cat]').forEach(b => b.onclick = () => formCategoria(panel.categorias.find(c => String(c.id) === b.dataset.editarCat)));
    $$('[data-borrar-cat]').forEach(b => b.onclick = () => confirmar(`¿Eliminar la categoría "${b.dataset.nombre}"?`, async () => {
      await apiAdmin(`categorias/${b.dataset.borrarCat}/`, { method: 'DELETE' });
      toast('Categoría eliminada');
      irA('categorias');
    }));
  }

  function formCategoria(c = null) {
    abrirModal(`
      <div class="modal">
        <div class="modal-cab"><h3>${c ? 'Editar categoría' : 'Nueva categoría'}</h3><button class="cerrar" data-cerrar>×</button></div>
        <form class="modal-cuerpo" id="formCat">
          <div class="campo"><label>Nombre</label><input name="nombre" required value="${esc(c?.nombre ?? '')}"></div>
          <div class="campo"><label>Descripción</label><textarea name="descripcion" rows="3">${esc(c?.descripcion ?? '')}</textarea></div>
          <div class="error-form"></div>
          <button class="btn btn-naranja btn-bloque">${c ? 'Guardar cambios' : 'Crear categoría'}</button>
        </form>
      </div>`);
    $('#formCat').onsubmit = async ev => {
      ev.preventDefault();
      const d = Object.fromEntries(new FormData(ev.target));
      try {
        await apiAdmin(c ? `categorias/${c.id}/` : 'categorias/', { method: c ? 'PUT' : 'POST', body: d });
        cerrarModal();
        toast(c ? 'Categoría actualizada' : 'Categoría creada');
        irA('categorias');
      } catch (e) { $('.error-form', ev.target).textContent = e.message; }
    };
  }

  /* ========================================================================
     4. ÓRDENES  GET /api/ordenes/?estado=... · PATCH /api/ordenes/{id}/estado/
        Transiciones permitidas (validadas también en el backend):
          PENDIENTE -> PAGADO (descuenta stock) | CANCELADO
          PAGADO    -> ENTREGADO | CANCELADO (repone stock)
     ======================================================================== */
  async function vistaOrdenes() {
    const f = panel.ord;
    const qs = new URLSearchParams({ page: f.pagina, page_size: 10, ordering: '-creada' });
    if (f.estado) qs.set('estado', f.estado);
    if (f.search) qs.set('search', f.search);
    const data = await apiAdmin('ordenes/?' + qs);
    const paginas = Math.max(1, Math.ceil(data.count / 10));

    $('#panelContenido').innerHTML = `
      ${titulo('Órdenes', `${data.count} órdenes${f.estado ? ' en estado ' + f.estado : ''}`)}
      <div class="tabs">${['', ...ESTADOS].map(e => `<button data-estado-filtro="${e}" class="${e === f.estado ? 'activo' : ''}">${e || 'Todas'}</button>`).join('')}</div>
      <form class="panel-filtros" id="filtrosOrd">
        <input name="search" placeholder="Buscar por cliente, producto o SKU" value="${esc(f.search)}">
        <button class="btn btn-negro">Buscar</button>
      </form>
      ${data.results.map(tarjetaOrden).join('') || '<div class="vacio">No hay órdenes.</div>'}
      <div class="paginacion">
        <button class="btn btn-borde" data-pag-ord="${f.pagina - 1}" ${data.previous ? '' : 'disabled'}>‹ Anterior</button>
        <span style="align-self:center">Página ${f.pagina} de ${paginas}</span>
        <button class="btn btn-borde" data-pag-ord="${f.pagina + 1}" ${data.next ? '' : 'disabled'}>Siguiente ›</button>
      </div>`;

    $$('[data-estado-filtro]').forEach(b => b.onclick = () => { Object.assign(panel.ord, { estado: b.dataset.estadoFiltro, pagina: 1 }); irA('ordenes'); });
    $('#filtrosOrd').onsubmit = ev => { ev.preventDefault(); Object.assign(panel.ord, { search: ev.target.search.value.trim(), pagina: 1 }); irA('ordenes'); };
    $$('[data-pag-ord]').forEach(b => b.onclick = () => { panel.ord.pagina = Number(b.dataset.pagOrd); irA('ordenes'); });
    $$('[data-cambiar]').forEach(b => b.onclick = () => confirmar(
      `¿Cambiar la orden #${b.dataset.orden} a ${b.dataset.cambiar}?${b.dataset.cambiar === 'CANCELADO' && b.dataset.actual === 'PAGADO' ? ' El stock se repondrá al catálogo.' : ''}${b.dataset.cambiar === 'PAGADO' ? ' Se validará y descontará el stock.' : ''}`,
      async () => {
        await apiAdmin(`ordenes/${b.dataset.orden}/estado/`, { method: 'PATCH', body: { estado: b.dataset.cambiar } });
        toast(`Orden #${b.dataset.orden} → ${b.dataset.cambiar}`);
        irA('ordenes');
      }));
  }

  function tarjetaOrden(o) {
    const filas = o.detalles.map(d => `<tr><td>${esc(d.nombre_producto)}</td><td>${esc(d.sku)}</td><td>${d.cantidad}</td><td>${clp(d.precio_unitario)}</td><td>${clp(d.subtotal)}</td></tr>`).join('');
    const btn = (nuevo, clase, texto) => `<button class="btn ${clase}" data-cambiar="${nuevo}" data-orden="${o.id}" data-actual="${o.estado}">${texto}</button>`;
    let acciones = '';
    if (o.estado === 'PENDIENTE') acciones = btn('PAGADO', 'btn-naranja', 'Marcar PAGADO') + btn('CANCELADO', 'btn-borde', 'Cancelar');
    if (o.estado === 'PAGADO') acciones = btn('ENTREGADO', 'btn-negro', 'Marcar ENTREGADO') + btn('CANCELADO', 'btn-borde', 'Cancelar (repone stock)');
    return `<div class="orden">
      <div class="orden-cab">
        <h5>Orden #${o.id} · ${esc(o.usuario)} <small style="color:#888;font-weight:400">${new Date(o.creada).toLocaleString('es-CL')}</small></h5>
        <span class="estado ${o.estado}">${o.estado}</span>
      </div>
      <table><tr><th>Producto</th><th>SKU</th><th>Cant.</th><th>Precio congelado</th><th>Subtotal</th></tr>${filas}</table>
      <div class="orden-cab"><b>Total: ${clp(o.total)}</b><div class="acciones">${acciones}</div></div>
    </div>`;
  }

  /* ========================================================================
     CONFIRMACIÓN GENÉRICA (para eliminar y cambiar estados)
     ======================================================================== */
  function confirmar(mensaje, accion) {
    abrirModal(`
      <div class="modal">
        <div class="modal-cab"><h3>Confirmar</h3><button class="cerrar" data-cerrar>×</button></div>
        <div class="modal-cuerpo">
          <p>${esc(mensaje)}</p>
          <div class="error-form"></div>
          <div class="fila-botones">
            <button class="btn btn-borde" data-cerrar>Cancelar</button>
            <button class="btn btn-naranja" id="btnConfirmar">Confirmar</button>
          </div>
        </div>
      </div>`);
    $('#btnConfirmar').onclick = async () => {
      try { await accion(); cerrarModal(); }
      catch (e) { $('#capaModal .error-form').textContent = e.message; }
    };
  }

  /* ========================================================================
     EVENTOS GENERALES E INICIO
     ======================================================================== */
  document.addEventListener('click', ev => {
    if (ev.target.classList.contains('fondo') || ev.target.closest('[data-cerrar]')) cerrarModal();
  });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') cerrarModal(); });

  window.alCambiarSesion = verificarAcceso;
  verificarAcceso();
})();
