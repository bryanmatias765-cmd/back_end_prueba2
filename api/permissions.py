from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Perfil


# ===========================================================================
# LECTURA DEL ROL DEL USUARIO
# 1. Si la petición viene con JWT, request.auth es el token ya validado
#    (firma y expiración) y se lee directamente el claim "rol".
# 2. Si viene por sesión (API navegable / admin) no hay token, así que se
#    consulta el Perfil en la base de datos.
# Un superusuario siempre se considera ADMIN.
# ===========================================================================
def obtener_rol(request):
    user = request.user
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return Perfil.Rol.ADMIN

    token = request.auth
    if token is not None and hasattr(token, 'get') and token.get('rol'):
        return token.get('rol')

    perfil = getattr(user, 'perfil', None)
    return perfil.rol if perfil else Perfil.Rol.CLIENTE


# ===========================================================================
# PERMISO: SOLO ADMINISTRADOR
# Para gestión de inventario y cambio de estado de órdenes.
# ===========================================================================
class EsAdministrador(BasePermission):
    message = 'Solo un Administrador de TI puede realizar esta acción.'

    def has_permission(self, request, view):
        return obtener_rol(request) == Perfil.Rol.ADMIN


# ===========================================================================
# PERMISO: LECTURA PÚBLICA / ESCRITURA SOLO ADMINISTRADOR
# GET, HEAD y OPTIONS (métodos seguros) los puede usar cualquiera, incluso
# sin token (catálogo público). POST/PUT/PATCH/DELETE exigen rol ADMIN.
# ===========================================================================
class EsAdministradorOSoloLectura(BasePermission):
    message = 'El catálogo es de solo lectura; modificarlo requiere rol ADMIN.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return obtener_rol(request) == Perfil.Rol.ADMIN


# ===========================================================================
# PERMISO A NIVEL DE OBJETO: DUEÑO DE LA ORDEN
# Un cliente solo puede ver/pagar sus propias órdenes.
# ===========================================================================
class EsDuenoDeLaOrden(BasePermission):
    message = 'Esta orden no te pertenece.'

    def has_object_permission(self, request, view, obj):
        return obj.usuario_id == request.user.id
