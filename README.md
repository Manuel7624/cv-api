# CV API · Manuel Sastre

API REST desarrollada con **Python y FastAPI** que sirve mi currículum
(perfil, experiencia, proyectos, formación, habilidades e idiomas). Es la base
de mi web-CV personal, que incluye un chatbot sobre mi perfil.

> Estado: en desarrollo. Los datos se guardan en SQLite; el siguiente paso de
> la base de datos es pasar a PostgreSQL.

## Endpoints

| Método | Ruta          | Descripción                      |
|--------|---------------|----------------------------------|
| GET    | `/`           | Web del currículum               |
| GET    | `/health`     | Comprobación de estado           |
| GET    | `/profile`    | Perfil y contacto                |
| GET    | `/experience` | Experiencia y prácticas          |
| GET    | `/projects`   | Proyectos                        |
| GET    | `/education`  | Formación                        |
| GET    | `/skills`     | Habilidades técnicas             |
| GET    | `/languages`  | Idiomas                          |
| POST   | `/chat`       | Pregunta al chatbot              |

Documentación interactiva (Swagger): `http://127.0.0.1:8000/docs`

## Ejecutarla en local (Windows)

Requisitos: Python 3.12.

```powershell
py -V:3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload --reload-dir app --env-file .env
```

Abre `http://127.0.0.1:8000/` para ver la web y `http://127.0.0.1:8000/docs` para
probar la API.

## Base de datos

Al arrancar, la aplicación crea las tablas y, si la base está vacía, carga los
datos de `app/seed.py`. Por defecto usa el archivo `cv.db`, que no se sube a Git.
Para usar otra base, define la variable de entorno `DATABASE_URL`.

Si cambias los datos de `app/seed.py`, borra `cv.db` y reinicia para que se
vuelvan a cargar.

## Chatbot

El navegador llama a `POST /chat` y es el backend quien habla con la IA, así que
las claves nunca llegan a la web. Se usa Groq y, si falla o agota su límite,
Gemini. Para cambiar de proveedor o de modelo se edita la lista `PROVIDERS` de
`app/llm.py`.

Las claves `GROQ_API_KEY` y `GEMINI_API_KEY` van en `.env`, que no se sube a Git.
Si ningún proveedor responde, el chat da un mensaje amable con mi correo.

El chat solo conoce los datos del CV y las respuestas de `EXTRA_INFO` en
`app/seed.py`. Lo que esté a `None` no lo usa, y dice que no lo sabe. Después de
editar ese archivo hay que borrar `cv.db` y reiniciar.

Límites: 5 mensajes por minuto y 30 al día por IP, 300 al día en total, y 500
caracteres por pregunta. Los contadores están en memoria, así que se reinician
con el servicio. Cada pregunta se responde por separado y no se guarda.

## Con Docker

```bash
docker compose up --build
```

La web queda en `http://localhost:8000`. Las claves se cargan de `.env`.

## Despliegue

El archivo `render.yaml` describe el servicio para Render: usa el `Dockerfile` y
comprueba `/health`. En el plan gratuito el disco no es persistente, así que
`cv.db` se vuelve a crear desde `app/seed.py` en cada arranque. Las claves se
escriben en el panel de Render, no en el repositorio.

## Tests

```powershell
pytest
```

## Estructura

```
app/
├── main.py      Rutas de la API
├── schemas.py   Forma de las respuestas de la API (Pydantic)
├── crud.py      Consultas a la base de datos
├── chat.py      Reglas del chatbot y datos que recibe
├── llm.py       Proveedores de IA (Groq y Gemini)
├── rate_limit.py  Límites de mensajes
├── models.py    Tablas de la base de datos (SQLAlchemy)
├── database.py  Conexión con la base de datos
├── seed.py      Datos iniciales del currículum
└── static/      Web: HTML, CSS, JavaScript, foto y CV en PDF
tests/           Pruebas automáticas
Dockerfile       Imagen del servicio
render.yaml      Configuración del despliegue en Render
```

## Próximos pasos

- Pasar la base de datos de SQLite a PostgreSQL.
- Desplegar la web en Render.

## Autor

Manuel Sastre · [GitHub](https://github.com/Manuel7624)
