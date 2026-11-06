# CV API · Manuel Sastre

API REST desarrollada con **Python y FastAPI** que sirve mi currículum
(perfil, experiencia, proyectos, formación y habilidades). Es la base de mi
web-CV personal.

> Estado: en desarrollo. Los datos se guardan en SQLite; el siguiente paso de
> la base de datos es pasar a PostgreSQL.

## Endpoints

| Método | Ruta          | Descripción                      |
|--------|---------------|----------------------------------|
| GET    | `/health`     | Comprobación de estado           |
| GET    | `/profile`    | Perfil y contacto                |
| GET    | `/experience` | Experiencia y prácticas          |
| GET    | `/projects`   | Proyectos                        |
| GET    | `/education`  | Formación                        |
| GET    | `/skills`     | Habilidades técnicas             |

Documentación interactiva (Swagger): `http://127.0.0.1:8000/docs`

## Ejecutarla en local (Windows)

Requisitos: Python 3.12.

```powershell
py -V:3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/docs` en el navegador.

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

La API queda en `http://localhost:8000`.

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
└── seed.py      Datos iniciales del currículum
tests/           Pruebas automáticas
Dockerfile       Imagen del servicio
```

## Próximos pasos

- Pasar la base de datos de SQLite a PostgreSQL.
- Chatbot que responda sobre mi perfil usando esta API.
- Despliegue en la nube con integración continua.

## Autor

Manuel Sastre · [GitHub](https://github.com/Manuel7624)
