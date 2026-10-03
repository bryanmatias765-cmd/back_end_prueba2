from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from api.views import panel_admin, tienda

# ===========================================================================
# RUTAS PRINCIPALES DEL PROYECTO
#   /             -> tienda (frontend HTML con footer del alumno)
#   /panel/       -> panel de administración con el diseño de la tienda (ADMIN)
#   /admin/       -> admin nativo de Django (requiere usuario staff)
#   /api/         -> API REST (app "api")
#   /api/schema/  -> esquema OpenAPI 3 (YAML)
#   /api/docs/    -> Swagger UI
#   /api/redoc/   -> ReDoc
# Las rutas de documentación van ANTES de include('api.urls') para que el
# router no las capture.
# ===========================================================================
urlpatterns = [
    path('', tienda, name='tienda'),
    path('panel/', panel_admin, name='panel'),
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/', include('api.urls')),
]
