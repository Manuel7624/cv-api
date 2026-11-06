# Imagen base ligera de Python
FROM python:3.12-slim

# Evita archivos .pyc y muestra los logs al instante
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Primero las dependencias: así Docker las guarda en caché si no cambian
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Después el código
COPY app ./app

EXPOSE 8000

# 0.0.0.0 para que sea accesible desde fuera del contenedor.
# El puerto lo fija la plataforma de despliegue con PORT; en local, 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
