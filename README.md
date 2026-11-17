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
| POST   | `/chat/stream`| Igual, con la respuesta a trozos |

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

El navegador llama a `POST /chat/stream` y es el backend quien habla con la IA, así
que las claves nunca llegan a la web. Se usa Gemini 3.5 Flash-Lite; si falla o tarda
más de 10 segundos, Gemini 3.1 Flash-Lite (una versión estable anterior, con la misma
clave), y si también falla, Groq. Si un proveedor agota el tiempo de espera 2 veces
seguidas, se salta durante 5 minutos para no esperar 10 segundos en cada pregunta
(si todos se están saltando, se prueban todos). Para cambiar de proveedor o de modelo se edita la lista `PROVIDERS` de
`app/llm.py`.

**Streaming:** la respuesta llega a trozos (server-sent events: `data: {"text": "..."}`)
y la web la va mostrando según se genera, siempre con `textContent`, nunca como HTML.
Si un proveedor falla a mitad, o si el RAG acaba diciendo que no tiene el dato, se
envía `data: {"restart": true}`: la web borra lo recibido y sigue con la respuesta
nueva: quita el texto a medias y vuelve a mostrar los tres puntos. Mientras la
respuesta sigue llegando, un cursor parpadea detrás del texto, para que una respuesta
parada a medias (por ejemplo, si Gemini deja de enviar trozos y a los 10 s entra la
reserva) no parezca terminada; el lector de pantalla solo la anuncia al final. Con
RAG, los primeros 80 caracteres se retienen para comprobar si la respuesta es "no lo
tengo por aquí" o un rechazo por fuera de tema y, en ese caso, pasar al plan B sin
mostrarla.
`POST /chat` sigue devolviendo la respuesta completa de una vez (por ejemplo, para
probarla desde `/docs`).

**Logs:** cada pregunta deja una línea con el tiempo total, el tiempo hasta el primer
texto y el camino seguido (búsqueda RAG, cada proveedor con su resultado y duración,
plan B). No se registra la pregunta ni la IP. Ejemplo:
`Chat: 2.05 s en total, primer texto a 1.94 s | búsqueda RAG 0.75 s | RAG: | gemini ok (primer texto 1.03 s) 1.15 s`

**Orden de proveedores:** se comparó Gemini primero frente a Groq primero con
proveedores reales (44 preguntas por orden: normales, en ráfaga, de plan B y trampas).
Groq es más rápido cuando responde, pero su plan gratuito (8.000 tokens por minuto)
devolvió 429 en 32 de las 44 preguntas, y en sus respuestas contestó en inglés a una
pregunta en español y usó una frase fija equivocada. Con Gemini primero, la mediana
hasta el primer texto fue 1,94 s (frente a 2,17 s) y sin fallos, así que se mantiene.

Las claves `GROQ_API_KEY` y `GEMINI_API_KEY` van en `.env`, que no se sube a Git.
Si ningún proveedor responde, el chat da un mensaje amable con mi correo.

El chat solo conoce los datos del CV y las preguntas y respuestas de `EXTRA_INFO`
en `app/seed.py`, que admite cualquier número de elementos. Si algo no está, dice
que no lo sabe. Los elementos con `fixed_answer=True` son temas delicados (sueldo,
nota media): el chat responde con ese texto y nunca da cifras. Después de editar
ese archivo hay que borrar `cv.db` y reiniciar.

Límites (por defecto): 5 mensajes por minuto y 30 al día por IP, 300 al día en
total, y 500 caracteres por pregunta. Se cambian con variables de entorno, sin tocar
el código: `CHAT_MESSAGES_PER_MINUTE_PER_IP`, `CHAT_MESSAGES_PER_DAY_PER_IP`,
`CHAT_MESSAGES_PER_DAY_TOTAL` y `CHAT_MAX_MESSAGE_LENGTH` (ver `.env.example` y
`render.yaml`). Un valor no válido detiene el arranque.

Los contadores se consultan en memoria (el chat nunca espera a la base de datos),
pero sobreviven a los reinicios: en Render el servicio gratuito se duerme a los 15
minutos y arranca de cero, y sin esto cada reinicio daría otra vez todos los
mensajes. Cada mensaje permitido se guarda en PostgreSQL (`chat_limit_uses`) desde
el hilo de las estadísticas, y al arrancar se cargan los de las últimas 24 horas.
Nunca se guarda la IP: solo un hash HMAC-SHA256 con la sal secreta
`LIMITS_HASH_SALT` (Render la genera sola), que se borra cuando pasa 24 horas y ya no
cuenta para ningún límite. Sin la sal, los límites por IP empiezan de cero en cada
arranque, pero el tope global se conserva. Si la base de datos falla, todo sigue
funcionando en memoria.

Para entender preguntas de seguimiento ("¿y en Java?"), el navegador envía los
últimos 6 mensajes junto con la pregunta nueva. El servidor no guarda nada: al
recargar la página, la conversación empieza de cero. Como el navegador puede
manipular ese historial, el modelo solo lo usa para entender la pregunta.

El plan gratuito de Groq permite 8.000 tokens por minuto y cada pregunta usa unos
5.400, así que como reserva solo puede responder en torno a una pregunta por minuto.

Las reglas del chat (no inventar nada, qué responder sobre teléfono, edad,
tecnologías que no conoce, preguntas fuera de tema, saludos, texto sin sentido o
preguntas cortas con siglas como "¿SQL?") están en `RULES`, en
`app/chat.py`.

## RAG: solo la información relacionada con cada pregunta

Enviar las 70 respuestas extra en cada pregunta cuesta unos 7.600 tokens. Con RAG
(`app/retrieval.py`) se envían siempre el CV, las reglas, las respuestas fijas y el
historial, pero de la información extra solo las 12 respuestas más parecidas a la
pregunta (y a las anteriores, para las de seguimiento). Así baja a unos 3.000 tokens.

- El parecido se mide con embeddings gratuitos de Gemini (`gemini-embedding-2`). Los
  vectores de las respuestas están guardados en `app/embeddings.json`: al arrancar
  se leen de ahí y solo se calculan los de las respuestas nuevas o cambiadas. En cada
  pregunta solo se calcula el de la pregunta.
- Si cambias `EXTRA_INFO`, regenera los vectores con `python -m app.retrieval` (con
  las claves cargadas) y haz commit del archivo. Un test avisa si se te olvida.
- Si la búsqueda falla, o si la IA contesta que no tiene la información o rechaza la
  pregunta por no tratar de mí, se repite con toda la información (casos 3 y 4):
  puede que el dato estuviera en la parte que el RAG no envió.
- Si el parecido es bajo (saludos, texto sin sentido, preguntas que no tratan de mí),
  se envían igualmente las 12 más parecidas: esos mensajes se responden con las
  reglas en una sola llamada, sin pasar al plan B.
- Para desactivarlo, `ENABLED = False` en `app/retrieval.py`.
- El plan gratuito de embeddings permite 1.000 textos al día y 100 por minuto. Gracias
  a los vectores guardados, cada pregunta gasta uno y un arranque, ninguno. Si se
  agota, el chat sigue funcionando con el orden de respaldo.

## Orden de respaldo del chat

1. RAG con Gemini (y, si falla, con la reserva de Gemini).
2. RAG con Groq.
3. Sin embeddings: Gemini (o su reserva) con toda la información.
4. Sin embeddings y con los dos Gemini caídos: Groq. Como no admite toda la información
   (límite de 8.000 tokens por petición), recibe las respuestas más relacionadas,
   ordenadas por palabras clave en el propio servidor (`app/keywords.py`), tantas
   como quepan. Sus instrucciones insisten en que, si no encuentra el dato, diga
   que no lo sabe.
5. Si todo falla: un mensaje amable con mi correo.

Cada proveedor declara su límite (`max_request_tokens` en `app/llm.py`), así que el
orden se ajusta solo si se cambia de proveedor.

## Estadísticas de uso y registro de preguntas (privados)

`GET /admin/stats` muestra, por día (UTC) y en total: mensajes respondidos, los que
quedan del tope global, cuántos respondió cada proveedor, cuántas veces se usó el
RAG, el plan B y la búsqueda por palabras clave, tiempos medios, mensajes bloqueados
por cada límite y errores (por proveedor, 429, tiempo agotado, internos). No aparece
en `/docs`.

Debajo están las preguntas de los últimos 30 días, de 50 en 50: "Preguntas sin
respuesta o rechazadas" (para ver qué falta en mis datos) y "Últimas preguntas". De
cada una se guarda la pregunta, la respuesta, la fecha, el proveedor y si fue
respondida, rechazada (fuera de tema), sin información o sin respuesta por fallo de
los proveedores. Nunca la IP ni nada que identifique a quien pregunta. Las de más de
30 días se borran solas (como mucho una vez por hora) y nunca se muestran. La web
avisa debajo del chat de que las preguntas se guardan de forma anónima 30 días.

- Se protege con `ADMIN_TOKEN` (al menos 20 caracteres). El navegador pide usuario y
  contraseña: el usuario da igual y la contraseña es el token. Sin token, la página
  no existe (404).
- **Se guardan en PostgreSQL** (Neon, plan gratuito) si está definida
  `STATS_DATABASE_URL`, para que no se pierdan cuando Render reinicia o duerme el
  servicio (`app/stats_store.py`). Solo van a PostgreSQL los contadores (día, nombre,
  valor) y el registro de preguntas: el CV sigue en SQLite. El driver es `psycopg`.
- El chat nunca espera a la base de datos: apunta en memoria y un hilo aparte envía
  lo pendiente cada 5 segundos (y al apagar).
- Neon puede dormirse cuando no hay actividad (el plan gratuito cuenta las horas que
  está despierta): la aplicación solo se conecta cuando hay algo que guardar, la
  limpieza de lo antiguo va junto con un guardado (nunca sola) y los límites del
  chat se cargan con el primer mensaje, no al arrancar. Las visitas que no usan el
  chat (por ejemplo, un servicio que llame a `/health` para que Render no se duerma)
  no tocan Neon. Si Neon no responde o la cadena es
  incorrecta, la web y el chat siguen igual, lo pendiente se guarda en cuanto vuelva
  la conexión y la página avisa de que solo muestra los datos en memoria.
- Los errores de conexión se registran solo por su tipo, sin la cadena de conexión.
- Sin `STATS_DATABASE_URL`, las estadísticas viven solo en memoria y se pierden al
  reiniciar.

## La web

Una sola página (`app/static/index.html`, `styles.css`, `chat.js` y `contact.js`, sin
frameworks): cabecera con foto y enlaces, el chat, el resumen del perfil, cómo está
hecha la web y contacto. El móvil usa el mismo HTML; con `@media (max-width: 600px)`
la foto se pone al lado del nombre y los botones pasan debajo del chat.

- La fuente Plus Jakarta Sans está dentro de la web (`static/fonts`, licencia OFL),
  para no cargar nada de fuera y no tener que abrir la CSP.
- El chat crece hasta un máximo y después hace scroll por dentro; baja solo al último
  mensaje salvo que hayas subido a leer. Intro envía y Mayúsculas+Intro salta de línea.
- Accesibilidad: todo se usa con teclado y foco visible, zonas de toque de 44 px, el
  área de mensajes con `role="log"` y la respuesta anunciada entera al terminar (no
  palabra a palabra), y sin animaciones con `prefers-reduced-motion`.
- "Enviar un correo" (`contact.js`): un `mailto:` solo funciona si el ordenador
  tiene un programa de correo configurado, así que en el ordenador abre un menú con
  Gmail, Outlook, otra app de correo o copiar la dirección (con `aria-expanded`,
  flechas, Esc y clic fuera para cerrar). En el móvil (pantalla táctil y estrecha)
  abre directamente el `mailto:`. Sin JavaScript queda el enlace `mailto:`.
- Al compartir el enlace (LinkedIn, WhatsApp...) se ve `static/img/og-image.png`. Su
  URL tiene que ser completa: se toma de `PUBLIC_URL` si existe o de la petición.

## Seguridad de la web

- Los datos y las respuestas del chat se pintan siempre con `textContent`, nunca
  como HTML, y un test comprueba que el JavaScript no usa `innerHTML`.
- Todas las respuestas llevan cabeceras de seguridad, y la web una política de
  contenido (CSP) que solo permite scripts y peticiones de la propia web. `/docs`
  no la lleva porque Swagger se carga desde un CDN.
- Las instrucciones del chat solo contienen datos públicos del CV: ni claves ni
  teléfono.
- Cabeceras extra: `Permissions-Policy` (sin cámara, micrófono ni ubicación) y, solo
  en peticiones que llegan por HTTPS, `Strict-Transport-Security` (un año).
- Las peticiones de más de 32 KB se rechazan con 413 sin leerlas enteras, traigan o
  no `Content-Length` (`app/security.py`).
- `/admin/stats`: tras 10 contraseñas fallidas desde la misma IP en 15 minutos, esa
  IP queda bloqueada 15 minutos (429). La IP se guarda como hash con sal y solo en
  memoria.
- La conexión con PostgreSQL (Neon) exige siempre SSL, aunque la cadena no lo diga.
- El contenedor se ejecuta con un usuario sin privilegios (`app`), que solo puede
  escribir en `/code/data` (donde está `cv.db`), y uvicorn arranca sin el registro
  de cada petición (`--no-access-log`) para que la IP no acabe en los logs.
- Las versiones de `requirements.txt` son exactas y pip se actualiza en la imagen.
- `scripts/check_client_ip.py`: después de desplegar, comprueba contra la web
  publicada que no se puede saltar el límite por IP inventándose la IP en las
  cabeceras (`python scripts/check_client_ip.py https://tu-web.onrender.com`).

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
├── chat_limits.py  Valores de los límites (configurables por entorno)
├── stats.py     Estadísticas de uso del chat (en memoria y envío a PostgreSQL)
├── stats_store.py  Guardado de las estadísticas en PostgreSQL (Neon)
├── admin.py     Página privada de estadísticas
├── models.py    Tablas de la base de datos (SQLAlchemy)
├── database.py  Conexión con la base de datos
├── seed.py      Datos iniciales del currículum
└── static/      Web: HTML, CSS, JavaScript, fuente, imágenes y CV en PDF
tests/           Pruebas automáticas
Dockerfile       Imagen del servicio
render.yaml      Configuración del despliegue en Render
```

## Próximos pasos

- Pasar la base de datos de SQLite a PostgreSQL.
- Desplegar la web en Render.

## Autor

Manuel Sastre · [GitHub](https://github.com/Manuel7624)
