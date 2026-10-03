import django_filters

from .models import Categoria, Orden, Producto


# ===========================================================================
# FILTROS DEL CATÁLOGO DE PRODUCTOS (django-filter)
# Parámetros disponibles en GET /api/productos/:
#   ?categoria=3              -> por id de categoría
#   ?categoria_nombre=ram     -> por nombre de categoría (contiene, sin mayúsc.)
#   ?marca=amd                -> por marca (contiene, sin mayúsculas)
#   ?precio_min=100000        -> precio >= valor
#   ?precio_max=500000        -> precio <= valor
#   ?en_stock=true            -> solo productos con stock > 0
#   ?activo=true              -> activos/inactivos (útil para el ADMIN)
# Se combinan con ?search= (búsqueda de texto) y ?ordering= (orden).
# ===========================================================================
class ProductoFilter(django_filters.FilterSet):
    categoria_nombre = django_filters.CharFilter(field_name='categoria__nombre', lookup_expr='icontains')
    marca = django_filters.CharFilter(field_name='marca', lookup_expr='icontains')
    precio_min = django_filters.NumberFilter(field_name='precio', lookup_expr='gte')
    precio_max = django_filters.NumberFilter(field_name='precio', lookup_expr='lte')
    en_stock = django_filters.BooleanFilter(method='filtrar_en_stock')

    class Meta:
        model = Producto
        fields = ['categoria', 'categoria_nombre', 'marca', 'precio_min', 'precio_max', 'en_stock', 'activo']

    def filtrar_en_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(stock__gt=0)
        if value is False:
            return queryset.filter(stock=0)
        return queryset


# ===========================================================================
# FILTROS DE CATEGORÍAS: ?nombre=tarjeta
# ===========================================================================
class CategoriaFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Categoria
        fields = ['nombre']


# ===========================================================================
# FILTROS DE ÓRDENES
#   ?estado=PAGADO                       -> por estado (CHOICES)
#   ?desde=2026-01-01&hasta=2026-12-31   -> rango de fechas de creación
#   ?total_min=... &total_max=...        -> rango de monto
# ===========================================================================
class OrdenFilter(django_filters.FilterSet):
    estado = django_filters.ChoiceFilter(choices=Orden.Estado.choices)
    desde = django_filters.DateFilter(field_name='creada', lookup_expr='date__gte')
    hasta = django_filters.DateFilter(field_name='creada', lookup_expr='date__lte')
    total_min = django_filters.NumberFilter(field_name='total', lookup_expr='gte')
    total_max = django_filters.NumberFilter(field_name='total', lookup_expr='lte')

    class Meta:
        model = Orden
        fields = ['estado', 'desde', 'hasta', 'total_min', 'total_max']
