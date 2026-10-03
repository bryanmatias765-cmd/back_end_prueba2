#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tienda_hardware.settings')

    # -----------------------------------------------------------------------
    # BASE DE DATOS LOCAL AUTOMÁTICA
    # Con DB_LOCAL_AUTO=True en el .env, antes de cualquier comando se
    # enciende el PostgreSQL propio del proyecto (ver bd_local.py).
    # -----------------------------------------------------------------------
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
    if os.getenv('DB_LOCAL_AUTO') == 'True' and not os.getenv('DATABASE_URL'):
        import bd_local
        bd_local.asegurar_bd()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
