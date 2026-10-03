from rest_framework.pagination import PageNumberPagination


# ===========================================================================
# PAGINACIÓN DE LA API
# 12 resultados por página por defecto (grilla de la tienda). El cliente
# puede pedir más con ?page_size=N (máximo 100), lo que usa el panel admin.
# ===========================================================================
class PaginacionTienda(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100
