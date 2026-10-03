"""
PostgreSQL LOCAL DEL PROYECTO (sin WAMP, sin instaladores).

Usa los programas de PostgreSQL (initdb / pg_ctl) para tener un servidor
propio del proyecto:
  - Los datos viven en la carpeta ./pgdata (ignorada por git).
  - Escucha en el puerto DB_PORT (por defecto 5433) para no chocar con otro
    PostgreSQL que ya exista en el PC.
  - manage.py llama a asegurar_bd() antes de cada comando, así que
    "python manage.py runserver" enciende la base automáticamente.

Uso manual:
    python bd_local.py            -> prepara y enciende la base
    python bd_local.py detener    -> apaga el servidor
    python bd_local.py estado     -> muestra si está encendido
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

DATOS = BASE_DIR / 'pgdata'
LOG = BASE_DIR / 'pgdata.log'
PUERTO = os.getenv('DB_PORT', '5433')
USUARIO = os.getenv('DB_USER', 'postgres')
CLAVE = os.getenv('DB_PASSWORD', 'postgres')
NOMBRE_BD = os.getenv('DB_NAME', 'tienda_hardware')


# ===========================================================================
# BUSCAR LOS PROGRAMAS DE POSTGRESQL
# Orden: variable PG_BIN del .env -> PATH -> instalaciones típicas en Windows.
# ===========================================================================
def buscar_bin():
    candidatos = [os.getenv('PG_BIN', '')]
    en_path = shutil.which('pg_ctl')
    if en_path:
        candidatos.append(str(Path(en_path).parent))
    candidatos.append(str(Path.home() / 'pgsql' / 'bin'))
    candidatos += sorted(glob.glob(r'C:\Program Files\PostgreSQL\*\bin'), reverse=True)
    for carpeta in candidatos:
        if carpeta and (Path(carpeta) / ('pg_ctl.exe' if os.name == 'nt' else 'pg_ctl')).exists():
            return Path(carpeta)
    sys.exit(
        'No se encontró PostgreSQL (pg_ctl). Instálalo o indica la carpeta "bin" '
        'en el .env con PG_BIN=...'
    )


def ejecutar(*args, **kw):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, **kw)


def esta_encendido(bin_dir):
    # pg_ctl status devuelve 0 si el servidor de ESTA carpeta de datos está corriendo.
    return DATOS.exists() and ejecutar(bin_dir / 'pg_ctl', 'status', '-D', DATOS).returncode == 0


# ===========================================================================
# 1. CREAR EL "CLUSTER" (solo la primera vez)
#    initdb crea la carpeta pgdata con el usuario y contraseña del .env,
#    codificación UTF8 y autenticación por contraseña (scram-sha-256).
# ===========================================================================
def inicializar(bin_dir):
    if (DATOS / 'PG_VERSION').exists():
        return
    print('[bd_local] Creando base PostgreSQL del proyecto en ./pgdata ...')
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
        f.write(CLAVE)
        archivo_clave = f.name
    try:
        r = ejecutar(bin_dir / 'initdb', '-D', DATOS, '-U', USUARIO, f'--pwfile={archivo_clave}',
                     '-E', 'UTF8', '--no-locale', '--auth=scram-sha-256')
    finally:
        os.remove(archivo_clave)
    if r.returncode != 0:
        sys.exit('[bd_local] initdb falló:\n' + r.stdout + r.stderr)


# ===========================================================================
# 2. ENCENDER EL SERVIDOR en el puerto configurado (si no está encendido)
# ===========================================================================
def encender(bin_dir):
    if esta_encendido(bin_dir):
        return
    print(f'[bd_local] Encendiendo PostgreSQL en el puerto {PUERTO} ...')
    # La salida NO se captura: el servidor queda corriendo en segundo plano y,
    # si heredara las tuberías de Python, este proceso esperaría para siempre.
    # Todo lo que informa PostgreSQL queda en el archivo pgdata.log.
    r = subprocess.run(
        [str(bin_dir / 'pg_ctl'), 'start', '-D', str(DATOS), '-l', str(LOG), '-w', '-o', f'-p {PUERTO}'],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if r.returncode != 0:
        sys.exit(f'[bd_local] No se pudo encender PostgreSQL. Revisa {LOG}')


# ===========================================================================
# 3. CREAR LA BASE DE DATOS del proyecto si todavía no existe
# ===========================================================================
def crear_bd():
    import psycopg

    with psycopg.connect(host='127.0.0.1', port=PUERTO, user=USUARIO, password=CLAVE,
                         dbname='postgres', autocommit=True) as con:
        existe = con.execute('SELECT 1 FROM pg_database WHERE datname = %s', (NOMBRE_BD,)).fetchone()
        if not existe:
            print(f'[bd_local] Creando base de datos "{NOMBRE_BD}" ...')
            try:
                con.execute(f'CREATE DATABASE "{NOMBRE_BD}" ENCODING \'UTF8\'')
            except (psycopg.errors.DuplicateDatabase, psycopg.errors.UniqueViolation):
                pass  # otro proceso la creó al mismo tiempo: ya existe, todo bien


def asegurar_bd():
    bin_dir = buscar_bin()
    inicializar(bin_dir)
    encender(bin_dir)
    crear_bd()


def detener():
    bin_dir = buscar_bin()
    if esta_encendido(bin_dir):
        ejecutar(bin_dir / 'pg_ctl', 'stop', '-D', DATOS, '-m', 'fast')
        print('[bd_local] PostgreSQL detenido.')
    else:
        print('[bd_local] PostgreSQL ya estaba detenido.')


if __name__ == '__main__':
    accion = sys.argv[1] if len(sys.argv) > 1 else 'iniciar'
    if accion == 'detener':
        detener()
    elif accion == 'estado':
        print('encendido' if esta_encendido(buscar_bin()) else 'detenido')
    else:
        asegurar_bd()
        print(f'[bd_local] Listo: PostgreSQL en 127.0.0.1:{PUERTO}, base "{NOMBRE_BD}".')
