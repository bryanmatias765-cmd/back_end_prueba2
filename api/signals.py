from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Carro, Perfil


# ===========================================================================
# SEÑAL post_save SOBRE EL USUARIO
# Cada vez que se crea un usuario nuevo (registro, createsuperuser o admin):
#   1. Se crea su Perfil. Si es superusuario/staff queda con rol ADMIN,
#      en cualquier otro caso queda como CLIENTE.
#   2. Se crea su Carro (relación 1 a 1), que vivirá en PostgreSQL mientras
#      exista el usuario. Así el carro existe desde el primer login.
# ===========================================================================
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_perfil_y_carro(sender, instance, created, **kwargs):
    if not created:
        return
    rol = Perfil.Rol.ADMIN if (instance.is_superuser or instance.is_staff) else Perfil.Rol.CLIENTE
    Perfil.objects.get_or_create(usuario=instance, defaults={'rol': rol})
    Carro.objects.get_or_create(usuario=instance)
