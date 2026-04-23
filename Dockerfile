# 1. Traemos un sistema operativo base que ya tiene Python 3.13 instalado. 
# La palabra "slim" significa que es una versión ligera (pesa menos megas).
FROM python:3.13-slim

# 2. Configuraciones técnicas de Python para que funcione mejor en Docker:
# Evita que Python cree esos molestos archivos .pyc ocultos.
ENV PYTHONDONTWRITEBYTECODE 1
# Obliga a Python a mostrar los "print" y errores en la consola al instante.
ENV PYTHONUNBUFFERED 1

# 3. Le decimos a Docker: "Creá una carpeta llamada /app adentro del contenedor 
# y a partir de ahora, trabajá siempre posicionado ahí adentro".
WORKDIR /app

# 4. Copiamos TU archivo requirements.txt desde tu Windows hacia la carpeta /app del contenedor.
COPY requirements.txt /app/

# 5. Le ordenamos al contenedor que instale todas las librerías de ese archivo (Django, Pillow, etc).
RUN pip install --no-cache-dir -r requirements.txt

# 6. Finalmente, copiamos absolutamente TODAS tus carpetas de código (Contenedor, static, etc) 
# hacia adentro del contenedor.
COPY . /app/