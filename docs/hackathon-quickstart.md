# Inicio rápido para el hackatón

Ensayo para Desarrollo de Software individual con Python 3.11+, FastAPI BaseKit,
SQLAlchemy, SQLite y Uvicorn. SQLite guarda los datos en un archivo local.

## Ensayar con el checkout local

Ejecuta esto desde la raíz de FastAPI BaseKit, en Bash. El ensayo se genera en
una carpeta temporal. Usa la copia local del paquete, incluidas las correcciones
al generador.

```bash
BASEKIT_DIR="$PWD"
PRACTICA_DIR="$(mktemp -d)"
python3 -m venv "$PRACTICA_DIR/.venv"
source "$PRACTICA_DIR/.venv/bin/activate"
python -m pip install "$BASEKIT_DIR[init]"

basekit init --no-input --output-dir "$PRACTICA_DIR" \
  --extra-context project_name=Practica \
  --extra-context orm=sqlalchemy \
  --extra-context database=sqlite \
  --extra-context include_docker=no \
  --extra-context include_alembic=no

cd "$PRACTICA_DIR/practica"
python -m pip install -r requirements.txt
cp .env.example .env
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ADMIN_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
python -m app.scripts.init
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En otra terminal, comprueba que la API responde con
`curl -fsS http://127.0.0.1:8000/health`. En el navegador, abre
[Swagger](http://127.0.0.1:8000/docs) y prueba `POST /api/v1/auth/login/` con
`admin@example.com` y el valor de `ADMIN_PASSWORD` de la terminal del ensayo.
El seed conserva el usuario si ya existe. Si lo vuelves a correr en la misma
base, conserva también la contraseña con la que lo creaste. Mantén la misma
clave JWT entre reinicios si necesitas conservar los tokens emitidos.

Con el entorno virtual activo, ejecuta `python -m pytest` en la carpeta
`practica` para comprobar el endpoint de salud.

Swagger carga sus archivos desde una CDN por defecto. Si falla esa conexión,
puedes comprobar la API con `curl` y consultar el contrato en `/openapi.json`.

## Qué confirmar en el Nodo S3

- Si los equipos tienen Python 3.11+, Git y acceso a PyPI o a un índice autorizado.
- Si permiten usar BaseKit como dependencia abierta y, por separado, si permiten
  generar el proyecto con `basekit init`. La guía requiere crear el código,
  la interfaz y la arquitectura específica del reto durante el evento.
- Si el generador no está permitido, escribe el proyecto allí e importa únicamente
  las dependencias autorizadas. Si BaseKit no está disponible, usa las herramientas
  habilitadas en el puesto. Declara en el README las librerías, APIs y recursos usados.

## Orden de trabajo durante el reto

1. Identifica el caso de uso principal y cómo lo vas a demostrar.
2. Levanta el servidor y guarda el primer commit en el GitLab del evento.
3. Implementa un flujo que puedas ejecutar completo con datos de prueba. Guarda
   commits conforme avances y verifica que los datos persistan.
4. Escribe en el README los pasos para arrancar, las dependencias y una prueba
   rápida de la demo. Evita subir `.env`, contraseñas o el archivo de SQLite.
5. Prueba el arranque desde una copia limpia del repositorio antes de entregar.
   El viernes 27 de noviembre cierra la entrega a las 6:00 p. m. Debes entregar
   el repositorio, el prototipo funcionando localmente y la presentación.

Para el pitch de cinco minutos, dedica 45 segundos al problema y al usuario,
tres minutos al flujo en vivo, 45 segundos a explicar la solución técnica y
30 segundos al impacto y los siguientes pasos.
