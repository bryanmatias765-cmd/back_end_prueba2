from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import render
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .filters import CategoriaFilter, OrdenFilter, ProductoFilter
from .models import (
    Carro, Categoria, DetalleOrden, ItemCarro, Orden, Perfil, Producto,
    StockInsuficiente, TransicionInvalida,
)
from .permissions import EsAdministrador, EsAdministradorOSoloLectura, EsDuenoDeLaOrden, obtener_rol
from .serializer import (
    ActualizarItemSerializer, AgregarItemSerializer, CambioEstadoSerializer,
    CarroSerializer, CategoriaSerializer, LoginTokenSerializer, OrdenSerializer,
    ProductoSerializer, RegistroSerializer, UsuarioSerializer,
)


# ===========================================================================
# VISTA HTML DE LA TIENDA (frontend)
# Renderiza la página principal; el catálogo, carro y órdenes se cargan con
# JavaScript consumiendo esta misma API con JWT. El footer muestra los
# datos del alumno (context processor "datos_alumno").
# ===========================================================================
def tienda(request):
    return render(request, 'tienda/index.html')


# ===========================================================================
# VISTA HTML DEL PANEL DE ADMINISTRACIÓN (/panel/)
# Mismo diseño de la tienda. La página es solo la "cáscara": al cargar, el
# JavaScript revisa el claim "rol" del JWT y, si no es ADMIN, muestra
# "Acceso restringido" y no pide datos. Aunque alguien forzara la página,
# TODOS los datos y acciones pasan por endpoints protegidos con el permiso
# EsAdministrador, que valida el token firmado en el servidor (403 si no).
# ===========================================================================
def panel_admin(request):
    return render(request, 'tienda/panel.html')


# ===========================================================================
# AUTENTICACIÓN JWT
# - LoginView:    POST usuario+contraseña -> tokens access/refresh con rol.
# - RegistroView: crea un CLIENTE nuevo (público).
# - LogoutView:   pone el refresh token en lista negra. El carro NO se toca:
#                 sigue guardado en PostgreSQL para el próximo login.
# - PerfilView:   datos del usuario autenticado.
# ===========================================================================
class LoginView(TokenObtainPairView):
    serializer_class = LoginTokenSerializer


class RegistroView(generics.CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'refresh': {'type': 'string'}}}},
        responses={205: None},
    )
    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh')).blacklist()
        except TokenError:
            return Response({'detail': 'Refresh token inválido o ya revocado.'}, status=400)
        return Response({'detail': 'Sesión cerrada. Tu carro sigue guardado.'},
                        status=status.HTTP_205_RESET_CONTENT)


class PerfilView(generics.RetrieveAPIView):
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


# ===========================================================================
# CATÁLOGO: CATEGORÍAS (PÚBLICO lectura / ADMIN escritura)
# Se anota cuántos productos activos tiene cada categoría.
# ===========================================================================
class CategoriaViewSet(viewsets.ModelViewSet):
    serializer_class = CategoriaSerializer
    permission_classes = [EsAdministradorOSoloLectura]
    filterset_class = CategoriaFilter
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre']
    pagination_class = None

    def get_queryset(self):
        return Categoria.objects.annotate(
            total_productos=Count('productos', filter=Q(productos__activo=True))
        )

    # La FK Producto.categoria usa PROTECT: no se puede borrar una categoría
    # que todavía tiene productos. Se responde 409 con un mensaje claro.
    def destroy(self, request, *args, **kwargs):
        categoria = self.get_object()
        if categoria.productos.exists():
            return Response(
                {'detail': f'La categoría "{categoria.nombre}" tiene productos asociados; '
                           'muévelos o elimínalos primero.'},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


# ===========================================================================
# CATÁLOGO: PRODUCTOS (PÚBLICO lectura / ADMIN escritura)
# - Público y clientes solo ven productos activos; el ADMIN ve todos.
# - Filtros django-filter (ProductoFilter) + búsqueda + ordenamiento.
# - DELETE hace "baja lógica" si el producto ya tiene ventas (PROTECT).
# ===========================================================================
class ProductoViewSet(viewsets.ModelViewSet):
    serializer_class = ProductoSerializer
    permission_classes = [EsAdministradorOSoloLectura]
    filterset_class = ProductoFilter
    search_fields = ['nombre', 'marca', 'sku', 'descripcion', 'categoria__nombre']
    ordering_fields = ['precio', 'nombre', 'stock', 'creado']

    def get_queryset(self):
        qs = Producto.objects.select_related('categoria')
        if obtener_rol(self.request) != Perfil.Rol.ADMIN:
            qs = qs.filter(activo=True)
        return qs

    def perform_destroy(self, instance):
        if DetalleOrden.objects.filter(producto=instance).exists():
            instance.activo = False
            instance.save(update_fields=['activo'])
        else:
            instance.delete()


# ===========================================================================
# CARRO DE COMPRAS PERSISTENTE (solo usuarios autenticados)
# El carro se obtiene SIEMPRE por el usuario del token:
#     Carro.objects.get_or_create(usuario=request.user)
# Por eso, tras logout/login o desde otro dispositivo, se recupera el mismo
# carro con sus ítems desde PostgreSQL.
#   GET    /api/carro/               -> ver carro
#   POST   /api/carro/               -> agregar producto {producto, cantidad}
#   DELETE /api/carro/               -> vaciar carro
#   PATCH  /api/carro/items/{id}/    -> cambiar cantidad
#   DELETE /api/carro/items/{id}/    -> quitar ítem
# NINGUNA de estas operaciones descuenta stock.
# ===========================================================================
def obtener_carro(user):
    carro, _ = Carro.objects.get_or_create(usuario=user)
    return Carro.objects.prefetch_related(
        Prefetch('items', queryset=ItemCarro.objects.select_related('producto__categoria'))
    ).get(pk=carro.pk)


class CarroView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CarroSerializer)
    def get(self, request):
        return Response(CarroSerializer(obtener_carro(request.user)).data)

    # -----------------------------------------------------------------------
    # AGREGAR AL CARRO
    # Si el producto ya está en el carro NO se duplica: se suma la cantidad.
    # Se valida contra el stock actual solo como aviso al cliente; el
    # descuento real y la validación definitiva ocurren al PAGAR.
    # -----------------------------------------------------------------------
    @extend_schema(request=AgregarItemSerializer, responses=CarroSerializer)
    def post(self, request):
        serializer = AgregarItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        producto = serializer.validated_data['producto']
        cantidad = serializer.validated_data['cantidad']

        carro, _ = Carro.objects.get_or_create(usuario=request.user)
        item, creado = ItemCarro.objects.get_or_create(
            carro=carro, producto=producto, defaults={'cantidad': 0}
        )
        nueva_cantidad = item.cantidad + cantidad
        if nueva_cantidad > producto.stock:
            if creado:
                item.delete()
            return Response(
                {'detail': f'Solo hay {producto.stock} unidades disponibles de {producto.nombre}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.cantidad = nueva_cantidad
        item.save()
        carro.save()  # actualiza la fecha "actualizado"
        return Response(CarroSerializer(obtener_carro(request.user)).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=CarroSerializer)
    def delete(self, request):
        carro = obtener_carro(request.user)
        carro.items.all().delete()
        return Response(CarroSerializer(obtener_carro(request.user)).data)


class CarroItemView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_item(self, request, pk):
        # Solo se busca dentro del carro del usuario autenticado.
        return ItemCarro.objects.select_related('producto').filter(
            pk=pk, carro__usuario=request.user
        ).first()

    @extend_schema(request=ActualizarItemSerializer, responses=CarroSerializer)
    def patch(self, request, pk):
        item = self._get_item(request, pk)
        if item is None:
            return Response({'detail': 'Ítem no encontrado en tu carro.'}, status=404)
        serializer = ActualizarItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cantidad = serializer.validated_data['cantidad']
        if cantidad > item.producto.stock:
            return Response(
                {'detail': f'Solo hay {item.producto.stock} unidades disponibles.'}, status=400
            )
        item.cantidad = cantidad
        item.save(update_fields=['cantidad'])
        return Response(CarroSerializer(obtener_carro(request.user)).data)

    @extend_schema(responses=CarroSerializer)
    def delete(self, request, pk):
        item = self._get_item(request, pk)
        if item is None:
            return Response({'detail': 'Ítem no encontrado en tu carro.'}, status=404)
        item.delete()
        return Response(CarroSerializer(obtener_carro(request.user)).data)


# ===========================================================================
# ÓRDENES
#   GET   /api/ordenes/                -> ADMIN ve todas; cliente, solo las suyas
#   POST  /api/ordenes/checkout/       -> CLIENTE: carro -> orden PENDIENTE
#   POST  /api/ordenes/{id}/pagar/     -> CLIENTE dueño: confirma pago (PAGADO)
#   PATCH /api/ordenes/{id}/estado/    -> ADMIN: ENTREGADO / CANCELADO / PAGADO
# ===========================================================================
class OrdenViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrdenSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrdenFilter
    search_fields = ['usuario__username', 'detalles__nombre_producto', 'detalles__sku']
    ordering_fields = ['creada', 'total', 'estado']

    def get_queryset(self):
        # Swagger genera el esquema sin un usuario real: queryset vacío.
        if getattr(self, 'swagger_fake_view', False):
            return Orden.objects.none()
        qs = Orden.objects.select_related('usuario').prefetch_related('detalles').distinct()
        if obtener_rol(self.request) == Perfil.Rol.ADMIN:
            return qs
        return qs.filter(usuario=self.request.user)

    # -----------------------------------------------------------------------
    # CHECKOUT
    # Dentro de una transacción atómica:
    #   1. Bloquea el carro del usuario (evita doble checkout simultáneo).
    #   2. Crea la Orden en estado PENDIENTE.
    #   3. Copia cada ítem a DetalleOrden CONGELANDO el precio actual.
    #   4. Calcula el total y vacía el carro (el carro "se liquida").
    # El stock todavía NO se descuenta: eso ocurre al pasar a PAGADO.
    # -----------------------------------------------------------------------
    @extend_schema(request=None, responses={201: OrdenSerializer})
    @action(detail=False, methods=['post'])
    def checkout(self, request):
        with transaction.atomic():
            carro, _ = Carro.objects.get_or_create(usuario=request.user)
            carro = Carro.objects.select_for_update().get(pk=carro.pk)
            items = list(carro.items.select_related('producto'))
            if not items:
                return Response({'detail': 'Tu carro está vacío.'}, status=400)

            orden = Orden.objects.create(usuario=request.user)
            detalles = [
                DetalleOrden(
                    orden=orden,
                    producto=item.producto,
                    nombre_producto=item.producto.nombre,
                    sku=item.producto.sku,
                    precio_unitario=item.producto.precio,
                    cantidad=item.cantidad,
                )
                for item in items
            ]
            DetalleOrden.objects.bulk_create(detalles)
            orden.total = sum(d.precio_unitario * d.cantidad for d in detalles)
            orden.save(update_fields=['total'])
            carro.items.all().delete()

        return Response(OrdenSerializer(orden).data, status=status.HTTP_201_CREATED)

    # -----------------------------------------------------------------------
    # PAGAR (simulación de pasarela de pago)
    # Llama a Orden.cambiar_estado(PAGADO), que valida y descuenta el stock
    # de forma atómica. Si falta stock responde 409 y no se descuenta nada.
    # -----------------------------------------------------------------------
    @extend_schema(request=None, responses=OrdenSerializer)
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, EsDuenoDeLaOrden])
    def pagar(self, request, pk=None):
        orden = self.get_object()
        return self._aplicar_estado(orden, Orden.Estado.PAGADO)

    # -----------------------------------------------------------------------
    # CAMBIO DE ESTADO (solo ADMIN)
    # Body: {"estado": "ENTREGADO" | "CANCELADO" | "PAGADO"}
    # CANCELADO sobre una orden PAGADA repone el stock automáticamente.
    # -----------------------------------------------------------------------
    @extend_schema(request=CambioEstadoSerializer, responses=OrdenSerializer)
    @action(detail=True, methods=['patch'], permission_classes=[EsAdministrador])
    def estado(self, request, pk=None):
        orden = self.get_object()
        serializer = CambioEstadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._aplicar_estado(orden, serializer.validated_data['estado'])

    def _aplicar_estado(self, orden, nuevo_estado):
        try:
            orden.cambiar_estado(nuevo_estado)
        except StockInsuficiente as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        except TransicionInvalida as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrdenSerializer(orden).data)


# ===========================================================================
# RESUMEN PARA EL PANEL DE ADMINISTRACIÓN (solo ADMIN)
#   GET /api/admin/resumen/
# Indicadores calculados con consultas agregadas (COUNT / SUM) en la BD:
# productos, stock bajo, clientes, órdenes por estado y ventas confirmadas
# (suma de órdenes PAGADAS o ENTREGADAS; las canceladas no cuentan).
# ===========================================================================
class ResumenAdminView(APIView):
    permission_classes = [EsAdministrador]

    @extend_schema(responses={200: {'type': 'object'}})
    def get(self, request):
        por_estado = dict(Orden.objects.values_list('estado').annotate(n=Count('id')))
        ventas = Orden.objects.filter(
            estado__in=[Orden.Estado.PAGADO, Orden.Estado.ENTREGADO]
        ).aggregate(total=Sum('total'))['total'] or 0
        return Response({
            'productos': Producto.objects.count(),
            'productos_activos': Producto.objects.filter(activo=True).count(),
            'sin_stock': Producto.objects.filter(activo=True, stock=0).count(),
            'stock_bajo': Producto.objects.filter(activo=True, stock__gt=0, stock__lte=5).count(),
            'categorias': Categoria.objects.count(),
            'clientes': Perfil.objects.filter(rol=Perfil.Rol.CLIENTE).count(),
            'ordenes': {e: por_estado.get(e, 0) for e in Orden.Estado.values},
            'ventas_confirmadas': ventas,
        })


# ===========================================================================
# MIS ÓRDENES (CLIENTE): historial de compras del usuario autenticado.
#   GET /api/mis-ordenes/        GET /api/mis-ordenes/{id}/
# ===========================================================================
class MisOrdenesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrdenSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrdenFilter
    ordering_fields = ['creada', 'total']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Orden.objects.none()
        return Orden.objects.filter(usuario=self.request.user).prefetch_related('detalles')
