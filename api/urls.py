from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from api import views

# ===========================================================================
# ROUTER DE DRF
# DefaultRouter genera automáticamente las rutas de cada ViewSet
# (listado, detalle y acciones extra como checkout, pagar y estado).
# ===========================================================================
router = routers.DefaultRouter()
router.register(r'productos', views.ProductoViewSet, basename='producto')
router.register(r'categorias', views.CategoriaViewSet, basename='categoria')
router.register(r'ordenes', views.OrdenViewSet, basename='orden')
router.register(r'mis-ordenes', views.MisOrdenesViewSet, basename='mis-ordenes')

# ===========================================================================
# RUTAS DE LA API (todas cuelgan de /api/)
# ===========================================================================
urlpatterns = [
    # --- Autenticación JWT ---
    path('auth/registro/', views.RegistroView.as_view(), name='registro'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/perfil/', views.PerfilView.as_view(), name='perfil'),

    # --- Carro persistente ---
    path('carro/', views.CarroView.as_view(), name='carro'),
    path('carro/items/<int:pk>/', views.CarroItemView.as_view(), name='carro-item'),

    # --- Panel de administración (solo ADMIN) ---
    path('admin/resumen/', views.ResumenAdminView.as_view(), name='admin-resumen'),

    # --- Endpoints del router ---
    path('', include(router.urls)),
]
