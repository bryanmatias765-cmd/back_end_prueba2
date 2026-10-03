# HardPC – Tienda de Hardware y Componentes PC (EVA-2 Backend)

API REST con **Django REST Framework + PostgreSQL**, autenticación **JWT con claims de rol**,
carro de compras persistente, órdenes con control transaccional de stock, filtros con
**django-filter** y documentación **Swagger/OpenAPI** (drf-spectacular).

## Instalación (siguiendo la receta DRF)

```powershell
python -m venv env
.\env\Scripts\activate
python.exe -m pip install --upgrade pip
pip install -r requirements.txt
```

### Base de datos: PostgreSQL propio del proyecto (automático)

No se usa WAMP ni hay que crear la base a mano. Con `DB_LOCAL_AUTO=True` en el `.env`,
`manage.py` llama a `bd_local.py`, que:

1. Busca los programas de PostgreSQL (`pg_ctl`, `initdb`) en el PATH, en `C:\Program Files\PostgreSQL\*\bin`,
   en `%USERPROFILE%\pgsql\bin` o en la carpeta indicada con `PG_BIN=` en el `.env`.
2. La primera vez crea el servidor de datos en `./pgdata` (usuario y clave del `.env`).
3. Lo enciende en el puerto `5433` (para no chocar con otro PostgreSQL del PC).
4. Crea la base `tienda_hardware` si no existe.

Solo hay que copiar `.env.example` como `.env`. Comandos útiles:

```powershell
python bd_local.py estado     # ¿está encendida?
python bd_local.py detener    # apagarla
```

> **Otras opciones** (mismo código, solo cambia el `.env`):
> - **PostgreSQL en la nube (Neon)**: poner `DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require`.
> - **Motor ya instalado** (PostgreSQL o MySQL): `DB_LOCAL_AUTO=False` y completar `DB_ENGINE`, `DB_HOST`, `DB_PORT`, etc.
3. Migrar, cargar datos de ejemplo y levantar el servidor:
   ```powershell
   python manage.py migrate
   python manage.py poblar_tienda
   python manage.py runserver
   ```

Usuarios de prueba: `admin / Admin12345!` (rol ADMIN) y `cliente / Cliente12345!` (rol CLIENTE).

## Rutas principales

| Ruta | Descripción |
|---|---|
| http://127.0.0.1:8000/ | Tienda (frontend) con footer del alumno |
| http://127.0.0.1:8000/panel/ | Panel de administración (solo rol ADMIN) |
| http://127.0.0.1:8000/api/docs/ | Swagger UI |
| http://127.0.0.1:8000/api/redoc/ | ReDoc |
| http://127.0.0.1:8000/api/ | API navegable de DRF |
| http://127.0.0.1:8000/admin/ | Panel de administración |

## Matriz de endpoints y permisos

| Rol | Método y ruta | Descripción |
|---|---|---|
| Público | `GET /api/productos/` `GET /api/productos/{id}/` | Catálogo con filtros |
| Público | `GET /api/categorias/` | Categorías |
| Público | `POST /api/auth/registro/` | Crear cuenta de cliente |
| Público | `POST /api/auth/login/` | Tokens access/refresh con claim `rol` |
| Público | `POST /api/auth/refresh/` | Renovar access token |
| Cliente | `POST /api/auth/logout/` | Invalida refresh (blacklist). El carro se conserva |
| Cliente | `GET / POST / DELETE /api/carro/` | Ver, agregar producto, vaciar carro |
| Cliente | `PATCH / DELETE /api/carro/items/{id}/` | Cambiar cantidad / quitar ítem |
| Cliente | `POST /api/ordenes/checkout/` | Carro → Orden PENDIENTE (precios congelados) |
| Cliente | `POST /api/ordenes/{id}/pagar/` | Valida y descuenta stock → PAGADO |
| Cliente | `GET /api/mis-ordenes/` | Historial de compras |
| Admin | `POST / PUT / PATCH / DELETE /api/productos/` y `/api/categorias/` | Gestión de inventario |
| Admin | `GET /api/ordenes/` | Todas las órdenes (filtro `?estado=`) |
| Admin | `PATCH /api/ordenes/{id}/estado/` | `{"estado": "ENTREGADO" \| "CANCELADO" \| "PAGADO"}` |
| Admin | `GET /api/admin/resumen/` | Indicadores del panel de administración |

## Panel de administración (`/panel/`)

Interfaz con el mismo diseño de la tienda, **solo para el rol ADMIN**: resumen con indicadores,
CRUD de productos y categorías, y gestión de estados de las órdenes.

- Visitantes y clientes **no ven** ningún enlace de administración: los enlaces tienen la clase
  `solo-admin` y `comun.js` solo los muestra si el claim `rol` del JWT es `ADMIN`.
- Si un cliente entra directo a `/panel/`, ve "Acceso restringido" y no se piden datos.
- La seguridad real está en el backend: cada endpoint de gestión usa el permiso
  `EsAdministrador`, que valida el token firmado y responde **403** a cualquier otro rol.

### Filtros del catálogo (django-filter)

`/api/productos/?categoria=1&marca=amd&precio_min=100000&precio_max=500000&en_stock=true&search=ryzen&ordering=-precio`

## Ciclo de la orden y stock

```
PENDIENTE ──pagar──► PAGADO ──► ENTREGADO
    │                  │
    └──► CANCELADO ◄───┘  (si estaba PAGADO, se repone el stock)
```

- Agregar al carro **no** descuenta stock.
- `Orden.cambiar_estado()` (api/models.py) usa `transaction.atomic()` + `select_for_update()`:
  al pasar a PAGADO valida todos los productos y, si alguno no alcanza, responde **409** sin
  descontar nada (rollback). Si alcanza, descuenta con `F('stock') - cantidad`.
- Cancelar una orden PAGADA devuelve las cantidades al catálogo.

## Estructura

```
tienda_hardware/     settings.py (PostgreSQL, DRF, JWT, Swagger, datos alumno), urls.py
api/
  models.py          Perfil(1:1 User, rol CHOICES), Categoria, Producto, Carro(1:1 User),
                     ItemCarro, Orden(estado CHOICES), DetalleOrden
  serializer.py      Serializadores + login JWT con claims de rol
  views.py           Vistas de catálogo, carro, checkout, pago y estados
  permissions.py     EsAdministrador, EsAdministradorOSoloLectura, EsDuenoDeLaOrden
  filters.py         Filtros django-filter
  signals.py         Crea Perfil y Carro al registrar un usuario
  tests.py           14 pruebas automáticas (python manage.py test api)
templates/           API navegable y Swagger con footer del alumno
```
