from django.conf import settings


# ===========================================================================
# CONTEXT PROCESSOR: DATOS DEL ALUMNO
# Inyecta la variable "alumno" (nombre, sección, año) en TODAS las
# plantillas HTML, para mostrarla en el footer de la tienda y de la API
# navegable de DRF. Los datos se editan en settings.ALUMNO.
# ===========================================================================
def datos_alumno(request):
    return {'alumno': settings.ALUMNO}
