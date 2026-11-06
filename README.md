# CV API · Manuel Sastre

API REST desarrollada con **Python y FastAPI** que sirve mi currículum
(perfil, experiencia, proyectos, formación y habilidades). Es la base de mi
web-CV personal.

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

Documentación interactiva (Swagger): `http://127.0.0.1:8000/docs`

## Ejecutarla en local (Windows)

Requisitos: Python 3.12.

```powershell
py -V:3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/` para ver la web y `http://127.0.0.1:8000/docs` para
probar la API.

## Base de datos

Al arrancar, la aplicación crea las tablas y, si la base está vacía, carga los
datos de `app/seed.py`. Por defecto usa el archivo `cv.db`, que no se sube a Git.
Para usar otra base, define la variable de entorno `DATABASE_URL`.

Si cambias los datos de `app/seed.py`, borra `cv.db` y reinicia para que se
vuelvan a cargar.

## Con Docker

```bash
docker compose up --build
```

La web queda en `http://localhost:8000`.

## Despliegue

El archivo `render.yaml` describe el servicio para Render: usa el `Dockerfile` y
comprueba `/health`. En el plan gratuito el disco no es persistente, así que
`cv.db` se vuelve a crear desde `app/seed.py` en cada arranque.

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
- Chatbot que responda sobre mi perfil usando esta API.

## Autor

Manuel Sastre · [GitHub](https://github.com/Manuel7624)
