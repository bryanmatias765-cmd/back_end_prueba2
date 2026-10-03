import base64
import json

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Carro, Categoria, Orden, Perfil, Producto


# ===========================================================================
# PRUEBAS AUTOMÁTICAS DE LOS REQUISITOS DE LA EVALUACIÓN
# Ejecutar con:  python manage.py test api
# ===========================================================================
class BaseTienda(APITestCase):
    def setUp(self):
        self.cat = Categoria.objects.create(nombre='Procesadores')
        self.cpu = Producto.objects.create(categoria=self.cat, nombre='Ryzen 5', marca='AMD',
                                           sku='CPU-1', precio=100000, stock=5)
        self.gpu = Producto.objects.create(categoria=Categoria.objects.create(nombre='Tarjetas de Video'),
                                           nombre='RTX 4060', marca='NVIDIA', sku='GPU-1', precio=300000, stock=2)
        self.cliente = User.objects.create_user('cliente', 'c@x.cl', 'Cliente12345!')
        self.admin = User.objects.create_superuser('admin', 'a@x.cl', 'Admin12345!')

    def login(self, username, password):
        r = self.client.post('/api/auth/login/', {'username': username, 'password': password})
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + r.data['access'])
        return r.data


class JWTyRolesTests(BaseTienda):
    # El token contiene el claim "rol" en su payload.
    def test_login_incluye_claim_rol(self):
        data = self.login('cliente', 'Cliente12345!')
        payload = data['access'].split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(claims['rol'], 'CLIENTE')
        self.assertIn('refresh', data)
        self.assertEqual(self.login('admin', 'Admin12345!')['rol'], 'ADMIN')

    # La señal crea Perfil y Carro al crear el usuario.
    def test_senal_crea_perfil_y_carro(self):
        self.assertEqual(self.cliente.perfil.rol, Perfil.Rol.CLIENTE)
        self.assertTrue(Carro.objects.filter(usuario=self.cliente).exists())

    # Catálogo público; escritura solo ADMIN.
    def test_permisos_catalogo(self):
        self.assertEqual(self.client.get('/api/productos/').status_code, 200)
        self.assertEqual(self.client.get('/api/categorias/').status_code, 200)
        nuevo = {'categoria': self.cat.id, 'nombre': 'X', 'marca': 'Y', 'sku': 'Z', 'precio': 10, 'stock': 1}
        self.assertEqual(self.client.post('/api/productos/', nuevo).status_code, 401)
        self.login('cliente', 'Cliente12345!')
        self.assertEqual(self.client.post('/api/productos/', nuevo).status_code, 403)
        self.login('admin', 'Admin12345!')
        self.assertEqual(self.client.post('/api/productos/', nuevo).status_code, 201)

    def test_carro_requiere_autenticacion(self):
        self.assertEqual(self.client.get('/api/carro/').status_code, 401)


class CarroTests(BaseTienda):
    # Agregar dos veces el mismo producto suma cantidades (sin duplicados)
    # y NO descuenta stock.
    def test_agregar_sin_duplicar_ni_descontar(self):
        self.login('cliente', 'Cliente12345!')
        self.client.post('/api/carro/', {'producto': self.cpu.id, 'cantidad': 1})
        r = self.client.post('/api/carro/', {'producto': self.cpu.id, 'cantidad': 2})
        self.assertEqual(len(r.data['items']), 1)
        self.assertEqual(r.data['items'][0]['cantidad'], 3)
        self.cpu.refresh_from_db()
        self.assertEqual(self.cpu.stock, 5)

    # El carro persiste tras logout (refresh en blacklist) y nuevo login.
    def test_persistencia_post_logout(self):
        tokens = self.login('cliente', 'Cliente12345!')
        self.client.post('/api/carro/', {'producto': self.gpu.id, 'cantidad': 2})
        r = self.client.post('/api/auth/logout/', {'refresh': tokens['refresh']})
        self.assertEqual(r.status_code, 205)
        self.client.credentials()
        self.login('cliente', 'Cliente12345!')
        r = self.client.get('/api/carro/')
        self.assertEqual(r.data['items'][0]['producto']['sku'], 'GPU-1')
        self.assertEqual(r.data['items'][0]['cantidad'], 2)

    def test_modificar_y_eliminar_item(self):
        self.login('cliente', 'Cliente12345!')
        r = self.client.post('/api/carro/', {'producto': self.cpu.id, 'cantidad': 1})
        item_id = r.data['items'][0]['id']
        r = self.client.patch(f'/api/carro/items/{item_id}/', {'cantidad': 4})
        self.assertEqual(r.data['items'][0]['cantidad'], 4)
        r = self.client.delete(f'/api/carro/items/{item_id}/')
        self.assertEqual(r.data['items'], [])


class OrdenStockTests(BaseTienda):
    def crear_orden(self, cantidad_cpu=2):
        self.login('cliente', 'Cliente12345!')
        self.client.post('/api/carro/', {'producto': self.cpu.id, 'cantidad': cantidad_cpu})
        r = self.client.post('/api/ordenes/checkout/')
        self.assertEqual(r.status_code, 201)
        return r.data

    # Checkout: orden PENDIENTE, precio congelado, carro vacío, stock intacto.
    def test_checkout_congela_precio(self):
        orden = self.crear_orden()
        self.assertEqual(orden['estado'], 'PENDIENTE')
        self.cpu.precio = 999999
        self.cpu.save()
        r = self.client.get(f'/api/mis-ordenes/{orden["id"]}/')
        self.assertEqual(r.data['detalles'][0]['precio_unitario'], '100000')
        self.assertEqual(r.data['total'], '200000')
        self.assertEqual(self.client.get('/api/carro/').data['items'], [])
        self.cpu.refresh_from_db()
        self.assertEqual(self.cpu.stock, 5)

    # Pago: descuenta stock y pasa a PAGADO.
    def test_pagar_descuenta_stock(self):
        orden = self.crear_orden()
        r = self.client.post(f'/api/ordenes/{orden["id"]}/pagar/')
        self.assertEqual(r.data['estado'], 'PAGADO')
        self.cpu.refresh_from_db()
        self.assertEqual(self.cpu.stock, 3)

    # Stock insuficiente al pagar: 409 y no se descuenta nada.
    def test_pago_rechazado_sin_stock(self):
        orden = self.crear_orden(cantidad_cpu=4)
        Producto.objects.filter(pk=self.cpu.pk).update(stock=1)
        r = self.client.post(f'/api/ordenes/{orden["id"]}/pagar/')
        self.assertEqual(r.status_code, 409)
        self.cpu.refresh_from_db()
        self.assertEqual(self.cpu.stock, 1)
        self.assertEqual(Orden.objects.get(pk=orden['id']).estado, 'PENDIENTE')

    # Cancelar una orden PAGADA repone el stock; solo ADMIN puede hacerlo.
    def test_cancelar_repone_stock(self):
        orden = self.crear_orden()
        self.client.post(f'/api/ordenes/{orden["id"]}/pagar/')
        r = self.client.patch(f'/api/ordenes/{orden["id"]}/estado/', {'estado': 'CANCELADO'})
        self.assertEqual(r.status_code, 403)
        self.login('admin', 'Admin12345!')
        r = self.client.patch(f'/api/ordenes/{orden["id"]}/estado/', {'estado': 'CANCELADO'})
        self.assertEqual(r.data['estado'], 'CANCELADO')
        self.cpu.refresh_from_db()
        self.assertEqual(self.cpu.stock, 5)

    def test_transicion_invalida(self):
        orden = self.crear_orden()
        self.login('admin', 'Admin12345!')
        r = self.client.patch(f'/api/ordenes/{orden["id"]}/estado/', {'estado': 'ENTREGADO'})
        self.assertEqual(r.status_code, 400)


class PanelAdminTests(BaseTienda):
    # El resumen del panel solo responde a ADMIN.
    def test_resumen_solo_admin(self):
        self.assertEqual(self.client.get('/api/admin/resumen/').status_code, 401)
        self.login('cliente', 'Cliente12345!')
        self.assertEqual(self.client.get('/api/admin/resumen/').status_code, 403)
        self.login('admin', 'Admin12345!')
        r = self.client.get('/api/admin/resumen/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['productos'], 2)

    # Clientes no pueden ver todas las órdenes ni gestionar categorías.
    def test_cliente_no_gestiona(self):
        self.login('cliente', 'Cliente12345!')
        self.assertEqual(self.client.post('/api/categorias/', {'nombre': 'X'}).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/productos/{self.cpu.id}/').status_code, 403)

    # No se puede borrar una categoría con productos (409).
    def test_borrar_categoria_con_productos(self):
        self.login('admin', 'Admin12345!')
        self.assertEqual(self.client.delete(f'/api/categorias/{self.cat.id}/').status_code, 409)

    # La tienda pública no expone enlaces directos al /admin/ de Django y el
    # enlace al panel parte oculto (solo se muestra con rol ADMIN).
    def test_enlaces_admin_ocultos(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('href="/admin/"', html)
        self.assertIn('class="solo-admin oculto"', html)
        self.assertEqual(self.client.get('/panel/').status_code, 200)


class FiltrosYDocsTests(BaseTienda):
    def test_filtros_productos(self):
        r = self.client.get('/api/productos/?precio_min=200000')
        self.assertEqual([p['sku'] for p in r.data['results']], ['GPU-1'])
        r = self.client.get(f'/api/productos/?categoria={self.cat.id}')
        self.assertEqual(r.data['count'], 1)
        r = self.client.get('/api/productos/?marca=nvi&en_stock=true')
        self.assertEqual(r.data['count'], 1)
        r = self.client.get('/api/productos/?search=ryzen')
        self.assertEqual(r.data['results'][0]['sku'], 'CPU-1')

    def test_swagger_y_footer(self):
        r = self.client.get('/api/docs/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        self.assertContains(self.client.get('/'), 'footer-alumno')
