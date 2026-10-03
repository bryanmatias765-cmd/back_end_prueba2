from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from api.models import Categoria, Perfil, Producto

# ===========================================================================
# DATOS DE EJEMPLO DEL CATÁLOGO
# (categoría, nombre, marca, sku, precio CLP, stock, descripción)
# ===========================================================================
CATALOGO = [
    ('Procesadores', 'Ryzen 7 7800X3D', 'AMD', 'CPU-AMD-7800X3D', 389990, 12,
     '8 núcleos / 16 hilos, 3D V-Cache, socket AM5.'),
    ('Procesadores', 'Ryzen 5 7600', 'AMD', 'CPU-AMD-7600', 179990, 20,
     '6 núcleos / 12 hilos, socket AM5, incluye disipador.'),
    ('Procesadores', 'Core i7-14700K', 'Intel', 'CPU-INT-14700K', 419990, 8,
     '20 núcleos (8P+12E), socket LGA1700.'),
    ('Procesadores', 'Core i5-14400F', 'Intel', 'CPU-INT-14400F', 189990, 15,
     '10 núcleos, sin gráficos integrados, LGA1700.'),
    ('Tarjetas de Video', 'GeForce RTX 4070 Super 12GB', 'NVIDIA', 'GPU-NV-4070S', 699990, 6,
     '12GB GDDR6X, DLSS 3, ray tracing.'),
    ('Tarjetas de Video', 'GeForce RTX 4060 8GB', 'NVIDIA', 'GPU-NV-4060', 329990, 10,
     '8GB GDDR6, ideal para 1080p.'),
    ('Tarjetas de Video', 'Radeon RX 7800 XT 16GB', 'AMD', 'GPU-AMD-7800XT', 579990, 5,
     '16GB GDDR6, excelente para 1440p.'),
    ('Memorias RAM', 'Fury Beast 32GB (2x16) DDR5 6000', 'Kingston', 'RAM-KNG-32D5', 109990, 25,
     'Kit dual channel DDR5, CL36, perfil EXPO/XMP.'),
    ('Memorias RAM', 'Vengeance 16GB (2x8) DDR4 3200', 'Corsair', 'RAM-COR-16D4', 44990, 30,
     'Kit DDR4 de bajo perfil, CL16.'),
    ('Memorias RAM', 'Trident Z5 RGB 64GB DDR5 6400', 'G.Skill', 'RAM-GSK-64D5', 239990, 4,
     'Kit 2x32GB con iluminación RGB.'),
    ('Almacenamiento', 'SSD 990 PRO 2TB NVMe', 'Samsung', 'SSD-SAM-990P2T', 189990, 14,
     'PCIe 4.0, hasta 7.450 MB/s de lectura.'),
    ('Almacenamiento', 'SSD NV2 1TB NVMe', 'Kingston', 'SSD-KNG-NV21T', 54990, 40,
     'PCIe 4.0, hasta 3.500 MB/s.'),
    ('Placas Madre', 'B650 AORUS Elite AX', 'Gigabyte', 'MB-GIG-B650E', 229990, 7,
     'AM5, DDR5, WiFi 6E, PCIe 5.0 M.2.'),
    ('Placas Madre', 'PRO Z790-P WiFi', 'MSI', 'MB-MSI-Z790P', 249990, 3,
     'LGA1700, DDR5, WiFi 6E.'),
    ('Fuentes de Poder', 'RM850e 850W 80+ Gold', 'Corsair', 'PSU-COR-RM850E', 119990, 9,
     'Modular, ATX 3.0, conector 12VHPWR.'),
    ('Fuentes de Poder', 'MWE 650 Bronze V2', 'Cooler Master', 'PSU-CM-MWE650', 49990, 0,
     'Fuente 650W 80+ Bronze (sin stock para probar filtros).'),
]


# ===========================================================================
# COMANDO: python manage.py poblar_tienda
# Crea categorías, productos y dos usuarios de prueba:
#   admin   / Admin12345!    (rol ADMIN, superusuario)
#   cliente / Cliente12345!  (rol CLIENTE)
# Es idempotente: se puede ejecutar varias veces sin duplicar datos.
# ===========================================================================
class Command(BaseCommand):
    help = 'Carga datos de ejemplo en la tienda de hardware.'

    def handle(self, *args, **options):
        for cat_nombre, nombre, marca, sku, precio, stock, desc in CATALOGO:
            categoria, _ = Categoria.objects.get_or_create(nombre=cat_nombre)
            Producto.objects.update_or_create(
                sku=sku,
                defaults=dict(categoria=categoria, nombre=nombre, marca=marca,
                              precio=precio, stock=stock, descripcion=desc),
            )

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@hardpc.cl', 'Admin12345!')
        if not User.objects.filter(username='cliente').exists():
            User.objects.create_user('cliente', 'cliente@hardpc.cl', 'Cliente12345!',
                                     first_name='Cliente', last_name='Demo')
        Perfil.objects.filter(usuario__username='admin').update(rol=Perfil.Rol.ADMIN)

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {Categoria.objects.count()} categorías, {Producto.objects.count()} productos. '
            'Usuarios: admin/Admin12345!  cliente/Cliente12345!'
        ))
