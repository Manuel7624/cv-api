# Imagen base ligera de Python
FROM python:3.12-slim

# Evita archivos .pyc y muestra los logs al instante. La base de datos del CV va en
# /code/data, la única carpeta en la que puede escribir la aplicación.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////code/data/cv.db

WORKDIR /code

# Primero las dependencias: así Docker las guarda en caché si no cambian.
# pip se actualiza porque el de la imagen base tiene vulnerabilidades conocidas.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.3 \
    && pip install --no-cache-dir -r requirements.txt

# Usuario sin privilegios: si alguien lograra ejecutar código en la aplicación, no
# sería root. El código es de root y solo se puede leer; la aplicación solo puede
# escribir en /code/data.
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir /code/data \
    && chown app:app /code/data

# Después el código
COPY app ./app

USER app

EXPOSE 8000

# 0.0.0.0 para que sea accesible desde fuera del contenedor.
# El puerto lo fija la plataforma de despliegue con PORT; en local, 8000.
# --no-access-log: sin una línea por petición, que en Render podría llevar la IP real.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
