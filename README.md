# CV API · Manuel Sastre

API REST desarrollada con **Python y FastAPI** que sirve mi currículum
(perfil, experiencia, proyectos, formación y habilidades). Es la base de mi
web-CV personal.

> Estado: versión 0.1, esqueleto funcional. Los datos están en código; el
> siguiente paso es moverlos a una base de datos.

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

Requisitos: Python 3.12 o superior.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/docs` en el navegador.

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
├── schemas.py   Modelos de datos (Pydantic)
└── data.py      Datos del currículum
tests/           Pruebas automáticas
Dockerfile       Imagen del servicio
```

## Próximos pasos

- Guardar los datos en una base de datos (SQLite y después PostgreSQL).
- Chatbot que responda sobre mi perfil usando esta API.
- Despliegue en la nube con integración continua.

## Autor

Manuel Sastre · [GitHub](https://github.com/Manuel7624)
