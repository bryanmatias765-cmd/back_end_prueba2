from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Carro, Categoria, DetalleOrden, ItemCarro, Orden, Perfil, Producto
from .permissions import obtener_rol


# ===========================================================================
# JWT: SERIALIZADOR DE LOGIN CON CLAIMS PERSONALIZADOS
# get_token() agrega al PAYLOAD del token (access y refresh) los claims:
#   - rol:      CLIENTE o ADMIN (leído desde el Perfil)
#   - username / email
# validate() además devuelve rol y username en el cuerpo de la respuesta
# para que el frontend no tenga que decodificar el token.
# ===========================================================================
class LoginTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        perfil, _ = Perfil.objects.get_or_create(usuario=user)
        token['rol'] = Perfil.Rol.ADMIN if user.is_superuser else perfil.rol
        token['username'] = user.username
        token['email'] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        data['rol'] = self.get_token(self.user)['rol']
        return data


# ===========================================================================
# REGISTRO DE CLIENTES
# Crea el usuario con contraseña encriptada (create_user). La señal
# post_save le crea automáticamente su Perfil (rol CLIENTE) y su Carro.
# ===========================================================================
class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password')

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


# ===========================================================================
# DATOS DEL USUARIO AUTENTICADO (/api/auth/perfil/)
# ===========================================================================
class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'rol')

    def get_rol(self, obj) -> str:
        return obtener_rol(self.context['request'])


# ===========================================================================
# CATÁLOGO: CATEGORÍAS Y PRODUCTOS
# ProductoSerializer expone el nombre de la categoría (solo lectura) y recibe
# el id de la categoría al crear/editar.
# ===========================================================================
class CategoriaSerializer(serializers.ModelSerializer):
    total_productos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Categoria
        fields = ('id', 'nombre', 'descripcion', 'total_productos')


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = Producto
        fields = (
            'id', 'categoria', 'categoria_nombre', 'nombre', 'marca', 'sku',
            'descripcion', 'precio', 'stock', 'imagen_url', 'activo', 'creado',
        )
        read_only_fields = ('creado',)

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return value


# ===========================================================================
# CARRO DE COMPRAS
# - ItemCarroSerializer: muestra el ítem con datos del producto y subtotal.
# - AgregarItemSerializer: valida lo que llega en POST /api/carro/.
# - ActualizarItemSerializer: valida la nueva cantidad en PATCH.
# - CarroSerializer: el carro completo con sus ítems y el total.
# ===========================================================================
class ItemCarroSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = ItemCarro
        fields = ('id', 'producto', 'cantidad', 'subtotal', 'agregado')


class AgregarItemSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(activo=True))
    cantidad = serializers.IntegerField(min_value=1, default=1)


class ActualizarItemSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=1)


class CarroSerializer(serializers.ModelSerializer):
    items = ItemCarroSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)
    cantidad_items = serializers.SerializerMethodField()

    class Meta:
        model = Carro
        fields = ('id', 'usuario', 'items', 'cantidad_items', 'total', 'actualizado')

    def get_cantidad_items(self, obj) -> int:
        return sum(item.cantidad for item in obj.items.all())


# ===========================================================================
# ÓRDENES
# - DetalleOrdenSerializer: líneas con el precio CONGELADO del checkout.
# - OrdenSerializer: orden completa (historial).
# - CambioEstadoSerializer: valida el estado recibido en PATCH .../estado/
#   contra las CHOICES del modelo.
# ===========================================================================
class DetalleOrdenSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = DetalleOrden
        fields = ('id', 'producto', 'nombre_producto', 'sku', 'precio_unitario', 'cantidad', 'subtotal')


class OrdenSerializer(serializers.ModelSerializer):
    detalles = DetalleOrdenSerializer(many=True, read_only=True)
    usuario = serializers.CharField(source='usuario.username', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Orden
        fields = (
            'id', 'usuario', 'estado', 'estado_display', 'total',
            'creada', 'pagada_en', 'actualizada', 'detalles',
        )


class CambioEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=Orden.Estado.choices)
