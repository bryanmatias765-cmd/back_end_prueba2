from django.contrib import admin, messages

from .models import (
    Carro, Categoria, DetalleOrden, ItemCarro, Orden, Perfil, Producto,
    StockInsuficiente, TransicionInvalida,
)


# ===========================================================================
# PANEL DE ADMINISTRACIÓN DE DJANGO
# Se registran todos los modelos para poder revisarlos desde /admin/.
# ===========================================================================
@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'telefono')
    list_filter = ('rol',)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'sku', 'categoria', 'precio', 'stock', 'activo')
    list_filter = ('categoria', 'marca', 'activo')
    search_fields = ('nombre', 'sku', 'marca')
    list_editable = ('precio', 'stock', 'activo')


class ItemCarroInline(admin.TabularInline):
    model = ItemCarro
    extra = 0


@admin.register(Carro)
class CarroAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'actualizado')
    inlines = [ItemCarroInline]


class DetalleOrdenInline(admin.TabularInline):
    model = DetalleOrden
    extra = 0
    readonly_fields = ('producto', 'nombre_producto', 'sku', 'precio_unitario', 'cantidad')
    can_delete = False


# ===========================================================================
# ADMIN DE ÓRDENES
# El campo "estado" es de solo lectura en el formulario: para cambiarlo se
# usan las ACCIONES, que llaman a Orden.cambiar_estado(). Así el panel admin
# respeta exactamente la misma lógica de stock que la API.
# ===========================================================================
@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'estado', 'total', 'creada', 'pagada_en')
    list_filter = ('estado', 'creada')
    search_fields = ('usuario__username',)
    readonly_fields = ('usuario', 'estado', 'total', 'creada', 'pagada_en')
    inlines = [DetalleOrdenInline]
    actions = ['marcar_pagado', 'marcar_entregado', 'marcar_cancelado']

    def _cambiar(self, request, queryset, estado):
        for orden in queryset:
            try:
                orden.cambiar_estado(estado)
                self.message_user(request, f'Orden #{orden.pk} -> {estado}')
            except (StockInsuficiente, TransicionInvalida) as e:
                self.message_user(request, f'Orden #{orden.pk}: {e}', level=messages.ERROR)

    @admin.action(description='Marcar como PAGADO (descuenta stock)')
    def marcar_pagado(self, request, queryset):
        self._cambiar(request, queryset, Orden.Estado.PAGADO)

    @admin.action(description='Marcar como ENTREGADO')
    def marcar_entregado(self, request, queryset):
        self._cambiar(request, queryset, Orden.Estado.ENTREGADO)

    @admin.action(description='Marcar como CANCELADO (repone stock si estaba pagada)')
    def marcar_cancelado(self, request, queryset):
        self._cambiar(request, queryset, Orden.Estado.CANCELADO)
