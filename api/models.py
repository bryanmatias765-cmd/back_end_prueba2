from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


# ===========================================================================
# EXCEPCIONES DE NEGOCIO
# Se lanzan desde los métodos de Orden y las vistas las traducen a
# respuestas HTTP (409 Conflict / 400 Bad Request).
# ===========================================================================
class StockInsuficiente(Exception):
    """El stock de uno o más productos no alcanza para pagar la orden."""


class TransicionInvalida(Exception):
    """Se intentó un cambio de estado no permitido (ej: CANCELADO -> PAGADO)."""


# ===========================================================================
# MODELO PERFIL (relación 1 a 1 con User)
# Extiende al usuario de Django con su ROL dentro de la tienda.
# El rol se guarda con CHOICES y luego viaja como "claim" dentro del JWT.
# Se crea automáticamente mediante una señal (ver api/signals.py).
# ===========================================================================
class Perfil(models.Model):
    class Rol(models.TextChoices):
        CLIENTE = 'CLIENTE', 'Cliente'
        ADMIN = 'ADMIN', 'Administrador de TI'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil'
    )
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.CLIENTE)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'perfil'
        verbose_name_plural = 'perfiles'

    def __str__(self):
        return f'{self.usuario.username} ({self.get_rol_display()})'


# ===========================================================================
# MODELO CATEGORÍA
# Agrupa los productos: Procesadores, Tarjetas de Video, RAM, etc.
# Relación 1:N con Producto.
# ===========================================================================
class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'categoría'

    def __str__(self):
        return self.nombre


# ===========================================================================
# MODELO PRODUCTO (catálogo)
# Campos exigidos por el enunciado: nombre, marca, precio unitario, SKU,
# descripción y stock físico disponible.
# - categoria: FK con PROTECT (no se puede borrar una categoría con productos).
# - stock: PositiveIntegerField => PostgreSQL crea un CHECK (stock >= 0),
#   así la base de datos nunca permite stock negativo.
# ===========================================================================
class Producto(models.Model):
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='productos'
    )
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=80)
    sku = models.CharField('código SKU', max_length=40, unique=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField('precio unitario', max_digits=12, decimal_places=0)
    stock = models.PositiveIntegerField(default=0)
    imagen_url = models.URLField(blank=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} [{self.sku}]'


# ===========================================================================
# MODELO CARRO (relación 1 a 1 con User)
# Cada usuario tiene UN carro activo guardado en PostgreSQL. Como vive en la
# base de datos (y no en la sesión ni en el navegador), los ítems se
# conservan tras un logout o al entrar desde otro dispositivo.
# ===========================================================================
class Carro(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carro'
    )
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Carro de {self.usuario.username}'

    @property
    def total(self):
        # Total referencial calculado con el precio ACTUAL del catálogo.
        return sum((item.subtotal for item in self.items.all()), Decimal('0'))


# ===========================================================================
# MODELO ITEM DEL CARRO
# Relación N:1 con Carro y N:1 con Producto.
# UniqueConstraint (carro, producto): un producto aparece una sola vez por
# carro; si se vuelve a agregar se suma la cantidad (no hay duplicados).
# IMPORTANTE: agregar al carro NO descuenta stock.
# ===========================================================================
class ItemCarro(models.Model):
    carro = models.ForeignKey(Carro, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['agregado']
        constraints = [
            models.UniqueConstraint(fields=['carro', 'producto'], name='item_unico_por_carro'),
        ]

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'

    @property
    def subtotal(self):
        return self.producto.precio * self.cantidad


# ===========================================================================
# MODELO ORDEN (registro histórico de la compra)
# Se crea en el checkout a partir del carro. El atributo "estado" usa
# CHOICES y sigue el ciclo:
#     PENDIENTE -> PAGADO -> ENTREGADO
#         \           \
#          -> CANCELADO -> CANCELADO (repone stock)
# TRANSICIONES define qué cambios son válidos desde cada estado.
# ===========================================================================
class Orden(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de pago'
        PAGADO = 'PAGADO', 'Pagado'
        ENTREGADO = 'ENTREGADO', 'Entregado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    TRANSICIONES = {
        Estado.PENDIENTE: {Estado.PAGADO, Estado.CANCELADO},
        Estado.PAGADO: {Estado.ENTREGADO, Estado.CANCELADO},
        Estado.ENTREGADO: set(),
        Estado.CANCELADO: set(),
    }

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ordenes'
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    total = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    creada = models.DateTimeField(auto_now_add=True)
    pagada_en = models.DateTimeField(null=True, blank=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creada']
        verbose_name_plural = 'órdenes'

    def __str__(self):
        return f'Orden #{self.pk} - {self.usuario.username} - {self.estado}'

    # -----------------------------------------------------------------------
    # CAMBIO DE ESTADO (punto único de entrada)
    # 1. Abre una transacción atómica y bloquea la fila de la orden
    #    (select_for_update) para evitar que dos peticiones la procesen a la vez.
    # 2. Valida que la transición esté permitida.
    # 3. Si pasa a PAGADO   -> valida y descuenta stock.
    #    Si pasa a CANCELADO desde PAGADO -> repone el stock descontado.
    # Si algo falla se lanza una excepción y PostgreSQL hace ROLLBACK de todo.
    # -----------------------------------------------------------------------
    def cambiar_estado(self, nuevo_estado):
        with transaction.atomic():
            orden = Orden.objects.select_for_update().get(pk=self.pk)
            actual = orden.estado

            if nuevo_estado not in self.TRANSICIONES[actual]:
                raise TransicionInvalida(
                    f'No se puede pasar de {actual} a {nuevo_estado}.'
                )

            if nuevo_estado == self.Estado.PAGADO:
                orden._descontar_stock()
                orden.pagada_en = timezone.now()
            elif nuevo_estado == self.Estado.CANCELADO and actual == self.Estado.PAGADO:
                orden._reponer_stock()

            orden.estado = nuevo_estado
            orden.save(update_fields=['estado', 'pagada_en', 'actualizada'])

        # Refresca la instancia actual con lo guardado en la BD.
        self.refresh_from_db()
        return self

    # -----------------------------------------------------------------------
    # DESCUENTO ATÓMICO DE STOCK (solo al pasar a PAGADO)
    # - Bloquea las filas de los productos involucrados (select_for_update),
    #   ordenadas por id para evitar deadlocks entre órdenes concurrentes.
    # - Primero valida TODOS los productos; si alguno no alcanza, lanza
    #   StockInsuficiente y no se descuenta nada (rollback).
    # - Luego descuenta con F('stock') - cantidad: la resta la hace PostgreSQL.
    # -----------------------------------------------------------------------
    def _descontar_stock(self):
        detalles = list(self.detalles.all())
        ids = [d.producto_id for d in detalles]
        productos = {
            p.id: p
            for p in Producto.objects.select_for_update().filter(id__in=ids).order_by('id')
        }

        faltantes = []
        for d in detalles:
            producto = productos[d.producto_id]
            if producto.stock < d.cantidad:
                faltantes.append(
                    f'{producto.nombre}: solicitado {d.cantidad}, disponible {producto.stock}'
                )
        if faltantes:
            raise StockInsuficiente('Stock insuficiente -> ' + '; '.join(faltantes))

        for d in detalles:
            Producto.objects.filter(pk=d.producto_id).update(stock=F('stock') - d.cantidad)

    # -----------------------------------------------------------------------
    # REPOSICIÓN DE STOCK (al CANCELAR una orden que ya estaba PAGADA)
    # Devuelve al catálogo exactamente las cantidades de cada detalle.
    # -----------------------------------------------------------------------
    def _reponer_stock(self):
        for d in self.detalles.all():
            Producto.objects.filter(pk=d.producto_id).update(stock=F('stock') + d.cantidad)


# ===========================================================================
# MODELO DETALLE DE ORDEN
# Guarda cada línea de la orden. "precio_unitario" CONGELA el precio del
# producto al momento del checkout: si el catálogo cambia de precio después,
# la venta histórica no se ve afectada. También se copian nombre y SKU.
# producto usa PROTECT: no se puede borrar un producto que ya se vendió.
# ===========================================================================
class DetalleOrden(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    nombre_producto = models.CharField(max_length=150)
    sku = models.CharField(max_length=40)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=0)
    cantidad = models.PositiveIntegerField()

    class Meta:
        verbose_name = 'detalle de orden'
        verbose_name_plural = 'detalles de orden'

    def __str__(self):
        return f'{self.cantidad} x {self.nombre_producto}'

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad
