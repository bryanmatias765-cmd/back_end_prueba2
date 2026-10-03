from django.apps import AppConfig


# ===========================================================================
# CONFIGURACIÓN DE LA APP "api"
# ready() importa las señales para que Django las registre al iniciar.
# ===========================================================================
class ApiConfig(AppConfig):
    name = 'api'
    verbose_name = 'Tienda de Hardware'

    def ready(self):
        from . import signals  # noqa: F401
