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

El chat responde en primera persona, como si fuera yo, y la web avisa de forma
visible de que es una IA que responde con mi información.

El navegador llama a `POST /chat` y es el backend quien habla con la IA, así que
las claves nunca llegan a la web. Se usa Gemini y, si falla o tarda más de 25
segundos, Groq. Para cambiar de proveedor o de modelo se edita la lista `PROVIDERS` de
`app/llm.py`.

Las claves `GROQ_API_KEY` y `GEMINI_API_KEY` van en `.env`, que no se sube a Git.
Si ningún proveedor responde, el chat da un mensaje amable con mi correo.

El chat solo conoce los datos del CV y las preguntas y respuestas de `EXTRA_INFO`
en `app/seed.py`, que admite cualquier número de elementos. Si algo no está, dice
que no lo sabe. Los elementos con `fixed_answer=True` son temas delicados (sueldo,
nota media): el chat responde con ese texto y nunca da cifras. Después de editar
ese archivo hay que borrar `cv.db` y reiniciar.

Límites: 5 mensajes por minuto y 30 al día por IP, 300 al día en total, y 500
caracteres por pregunta. Los contadores están en memoria, así que se reinician
con el servicio.

Para entender preguntas de seguimiento ("¿y en Java?"), el navegador envía los
últimos 6 mensajes junto con la pregunta nueva. El servidor no guarda nada: al
recargar la página, la conversación empieza de cero. Como el navegador puede
manipular ese historial, el modelo solo lo usa para entender la pregunta.

El plan gratuito de Groq permite 8.000 tokens por minuto y cada pregunta usa unos
5.400, así que como reserva solo puede responder en torno a una pregunta por minuto.

Las reglas del chat (no inventar nada, qué responder sobre teléfono, edad,
tecnologías que no conoce o preguntas fuera de tema) están en `RULES`, en
`app/chat.py`.

## RAG: solo la información relacionada con cada pregunta

Enviar las 70 respuestas extra en cada pregunta cuesta unos 7.600 tokens. Con RAG
(`app/retrieval.py`) se envían siempre el CV, las reglas, las respuestas fijas y el
historial, pero de la información extra solo las 12 respuestas más parecidas a la
pregunta (y a las anteriores, para las de seguimiento). Así baja a unos 3.000 tokens.

- El parecido se mide con embeddings gratuitos de Gemini (`gemini-embedding-2`). Los
  de las respuestas se calculan una vez al arrancar; en cada pregunta solo se
  calcula el de la pregunta.
- Si la similitud es baja, si la búsqueda falla o si la IA contesta que no tiene la
  información, se repite la pregunta con toda la información (casos 3 y 4).
- Para desactivarlo, `ENABLED = False` en `app/retrieval.py`.
- El plan gratuito de embeddings permite 1.000 textos al día y 100 por minuto, y cada
  arranque gasta 70. Si se agota, el RAG se desactiva solo y el chat sigue
  funcionando con toda la información.

## Orden de respaldo del chat

1. RAG con Gemini.
2. RAG con Groq.
3. Sin embeddings: Gemini con toda la información.
4. Sin embeddings y con Gemini caído: Groq. Como no admite toda la información
   (límite de 8.000 tokens por petición), recibe las respuestas más relacionadas,
   ordenadas por palabras clave en el propio servidor (`app/keywords.py`), tantas
   como quepan. Sus instrucciones insisten en que, si no encuentra el dato, diga
   que no lo sabe.
5. Si todo falla: un mensaje amable con mi correo.

Cada proveedor declara su límite (`max_request_tokens` en `app/llm.py`), así que el
orden se ajusta solo si se cambia de proveedor.

## Seguridad de la web

- Los datos y las respuestas del chat se pintan siempre con `textContent`, nunca
  como HTML, y un test comprueba que el JavaScript no usa `innerHTML`.
- Todas las respuestas llevan cabeceras de seguridad, y la web una política de
  contenido (CSP) que solo permite scripts y peticiones de la propia web. `/docs`
  no la lleva porque Swagger se carga desde un CDN.
- Las instrucciones del chat solo contienen datos públicos del CV: ni claves ni
  teléfono.

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
├── llm.py       Proveedores de IA (Gemini y Groq)
├── retrieval.py  RAG: busca la información extra relacionada
├── keywords.py  Búsqueda por palabras clave (solo para el caso 4)
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
