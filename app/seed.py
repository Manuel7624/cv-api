"""Datos iniciales del currículum y su carga en la base de datos.

Se cargan al arrancar la aplicación, solo si la base está vacía. Por eso, cambiar
algo aquí no actualiza una base ya creada: en local hay que borrar cv.db y
reiniciar.
Importante: solo se incluye lo que es verdad y se puede defender en entrevista.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

PROFILE = {
    "name": "Manuel Sastre",
    "title": "Backend Developer",
    "location": "Zaragoza, España",
    "summary": (
        "Técnico Superior en Desarrollo de Aplicaciones Multiplataforma, con "
        "prácticas en una empresa de software (Python, Docker y GitLab), un "
        "proyecto propio en Android con Java y SQLite, y una web personal con "
        "API propia (Python y FastAPI) y chat de IA."
    ),
    "availability": "Disponibilidad inmediata",
    "email": "manusastrenar@gmail.com",
    "github": "https://github.com/Manuel7624",
    "linkedin": "https://www.linkedin.com/in/manuel-sastre-naranjo",
}

EXPERIENCE = [
    {
        "role": "Prácticas de desarrollo (FCT)",
        "company": "Brainy Inteligencia Semántica",
        "kind": "Prácticas",
        "period": "Ene 2026 – May 2026",
        "highlights": [
            "Refactorización y optimización de workers en Python para mejorar "
            "su estructura y legibilidad. Apoyo de Codex con un prompt base "
            "adaptado a cada worker.",
            "Pruebas de integración manuales: creación de un script (.py) "
            "dentro de la refactorización, ejecutado desde consola con un "
            "documento de entrada para comprobar de principio a fin que el "
            "worker funcionaba, siguiendo el proceso mediante los logs en "
            "consola.",
            "Dockerización de los workers que aún no estaban contenerizados y "
            "subida de los cambios a nuevas ramas en GitLab.",
            "Control de versiones con Git y GitLab (clonado, ramas, commits y "
            "push) y uso básico de la consola.",
        ],
    },
    {
        "role": "Azafato",
        "company": "The Wave 2026, Zaragoza",
        "kind": "Trabajo temporal",
        "period": "Abr 2026",
        "highlights": [
            "Preparación y reorganización del escenario principal entre "
            "intervenciones.",
            "Atención e información a los asistentes durante el evento.",
        ],
    },
]

PROJECTS = [
    {
        "name": "CV con API y chat de IA",
        "description": "Web personal con API propia y chat de IA "
        "sobre mi perfil (https://manuel-sastre-cv.vercel.app).",
        "technologies": ["Python", "FastAPI", "SQLite", "PostgreSQL", "Docker", "pytest"],
        "repository": "https://github.com/Manuel7624/cv-api",
        "highlights": [
            "API REST propia con FastAPI que sirve mi CV desde una base de "
            "datos, con documentación Swagger, y una web publicada en Vercel y "
            "Render.",
            "Chat de IA que responde en primera persona sobre mi perfil: busca "
            "primero los datos relevantes (RAG) y responde solo con ellos, "
            "para no inventar. Usa varios proveedores (Gemini y Groq) con "
            "cambio automático si uno falla.",
            "Desarrollado con Claude Code siguiendo un flujo estructurado: "
            "definición de requisitos y reglas del proyecto, plan de "
            "implementación por tarea revisado por mí, desarrollo en pasos "
            "pequeños y validación con tests automáticos (pytest) y revisión "
            "manual.",
        ],
    },
    {
        "name": "Balancea",
        "description": "Aplicación móvil Android de finanzas personales "
        "(proyecto final de grado).",
        "technologies": ["Java", "Android Studio", "SQLite", "MPAndroidChart"],
        "repository": "https://github.com/Manuel7624/TFG_ManuelSastre",
        "highlights": [
            "Al registrarte indicas tu saldo y vas añadiendo gastos e "
            "ingresos, que actualizan el saldo.",
            "Gráficas de ingresos vs gastos mensuales y anuales, evolución "
            "mensual y desglose por categoría.",
            "Persistencia local con SQLite y acceso a datos centralizado en "
            "clases propias; código organizado en paquetes y documentado con "
            "JavaDoc.",
        ],
    },
]

EDUCATION = [
    {
        "title": "Técnico Superior en Desarrollo de Aplicaciones Multiplataforma",
        "institution": "Océano Atlántico",
        "period": "2024 – 2026",
        "status": "Completado",
    },
    {
        "title": "Curso de Python",
        "institution": "Coddy",
        "period": None,
        "status": "En curso",
    },
    {
        "title": "Bachillerato de Ciencias",
        "institution": "IES Tiempos Modernos",
        "period": "2022 – 2024",
        "status": "Completado",
    },
]

SKILLS = {
    "languages": [
        "Python (prácticas, curso en Coddy y proyecto propio)",
        "Java (grado y proyecto final)",
        "SQL (SQLite, PostgreSQL)",
    ],
    "backend": [
        "FastAPI",
        "APIs REST",
        "OpenAPI/Swagger",
        "SQLAlchemy",
        "Rate limiting",
        "Nociones de RAG",
    ],
    "tools": [
        "Docker",
        "Git",
        "GitHub",
        "GitLab",
        "Android Studio",
        "Visual Studio Code",
        "Consola",
        "Codex",
        "Claude Code",
    ],
    "concepts": [
        "Programación orientada a objetos",
        "APIs",
        "Nociones de Kafka",
        "Windows y Linux",
    ],
}

LANGUAGES = [
    {"name": "Español", "level": "nativo"},
    {"name": "Inglés", "level": "B2 (2022)"},
]

# Información extra para el chatbot, escrita por Manuel en primera persona.
# Se pueden añadir o quitar elementos libremente: el chat usa todos.
# fixed_answer=True marca un tema que prefiero hablar en persona (sueldo, nota
# media): el chat responde siempre con ese texto, sin cifras ni rangos.
EXTRA_INFO = [
    {
        "topic": "Temas con respuesta fija",
        "question": "Expectativas salariales: sueldo o rango salarial que busco ahora (no el de las prácticas)",
        "answer": "Es algo que prefiero hablar directamente, porque depende del puesto, la modalidad y las condiciones. Puedes escribirme a mi correo y lo comentamos.",
        "fixed_answer": True,
    },
    {
        "topic": "Temas con respuesta fija",
        "question": "Nota media o calificaciones del grado",
        "answer": "Más que en la nota, durante el grado me centré en aprender y en que mis proyectos funcionaran bien. El resultado se puede ver en Balancea, mi proyecto final, y en este mismo proyecto.",
        "fixed_answer": True,
    },
    {
        "topic": "Presentación",
        "question": "Háblame de ti",
        "answer": "Soy Manuel, Técnico Superior en Desarrollo de Aplicaciones Multiplataforma, de Zaragoza, y busco mi primer puesto como desarrollador backend junior. En mis prácticas en Brainy Inteligencia Semántica trabajé con Python, Docker y GitLab: refactoricé varios workers que ya estaban dockerizados y dockericé desde cero uno que no tenía nada de Docker. Mi proyecto final fue Balancea, una app Android de finanzas personales en Java con SQLite. Ahora estoy reforzando Python y he creado este proyecto: una API REST con FastAPI que sirve esta web y este chat. Me gusta la lógica y quiero seguir aprendiendo en un equipo.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Cuáles son tus puntos fuertes?",
        "answer": "Lo primero, la resolución de problemas: me gusta que un reto me haga pensar, analizo el problema desde varias perspectivas y valoro las posibles soluciones antes de actuar. También el trabajo en equipo: llevo toda la vida jugando a deportes de equipo y es algo que se me da bien. Y la adaptación y el aprendizaje: si hay algo que no entiendo en un trabajo nuevo, busco información, exploro y pregunto hasta entenderlo, como me pasó en las prácticas con las APIs y Docker, que no había visto en el grado.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Cuál es tu punto débil? Algo malo de ti, tus defectos, en qué fallas o qué mejorarías de ti",
        "answer": "Si tuviera que decir algo, sería la organización: no es lo que me sale de forma natural, así que la trabajo de forma consciente. En las prácticas, por ejemplo, llevaba una lista con cada tarea dividida en fases y marcaba cada paso al completarlo, para tener siempre claro en qué punto estaba.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Por qué deberían contratarte?",
        "answer": "Porque, aunque soy junior, ya he trabajado en un entorno real con Python, Docker y Git, y he demostrado que aprendo rápido, incluso con tecnologías que no había visto en el grado. En las prácticas usé Codex, y este proyecto completo (API REST, web y chat) lo he construido por mi cuenta con Claude Code. Trabajo con método: reviso los planes, decido yo y pruebo todo antes de darlo por bueno.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Cuándo puedes empezar? ¿Cuándo puedes incorporarte?",
        "answer": "De inmediato: tengo disponibilidad inmediata y busco un puesto a jornada completa.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Algún logro personal del que estés orgulloso?",
        "answer": "En el fútbol sala: juego al fútbol desde los 4 años, llevo toda la vida jugando de portero y cada temporada noto que mejoro. Ver ese progreso gracias a la constancia es algo de lo que estoy orgulloso.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Qué aprendiste como azafato en The Wave 2026?",
        "answer": "Fue un trabajo puntual de tres días, ajeno a la programación, pero me sirvió para coordinarme con el equipo de producción durante un evento en directo, cumplir tiempos ajustados entre intervenciones y atender e informar a los asistentes.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Has tenido algún conflicto en un equipo?",
        "answer": "Sí, en algún trabajo en equipo del grado. Intenté calmar la discusión y que cada uno pudiera explicar su opinión mientras los demás escuchaban, sin aferrarse a su propia idea. Así llegamos a un acuerdo.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Cómo llevas la presión o los plazos ajustados?",
        "answer": "Intento mantener la calma y priorizar. Me ayuda el mismo método que uso para organizarme: dividir el trabajo en fases y marcar cada paso al terminarlo, así veo claro cuánto queda y en qué centrarme primero.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Has hecho alguna vez más de lo que te pedían?",
        "answer": "Me considero algo perfeccionista: cuando una tarea me gusta y le he dedicado tiempo, quiero dejarla lo mejor posible aunque suponga un esfuerzo extra. En Balancea, por ejemplo, dediqué mucho tiempo a pulir detalles que por separado parecen pequeños, pero que en conjunto hacen que el proyecto se vea mucho mejor.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Cómo organizas tu trabajo del día?",
        "answer": "En las prácticas me asignaban, por ejemplo, tres workers por semana. Los apuntaba en una lista y cada uno pasaba por varias fases: analizarlo y adaptar a él el prompt base, refactorizarlo con Codex, revisar el resultado y comprobarlo con mi script de integración manual, y subirlo a una rama nueva en GitLab. Marcaba cada fase al completarla, así veía el progreso de cada worker, y al terminar uno empezaba el siguiente.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Cómo sería tu entorno de trabajo ideal?",
        "answer": "Un equipo en el que pueda preguntar y aprender de compañeros con más experiencia, como me pasó en las prácticas. En cuanto a modalidad: en Zaragoza acepto presencial, híbrido o remoto, aunque mi preferencia es híbrido o remoto. Fuera de Zaragoza, remoto.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Y tu jefe o responsable ideal?",
        "answer": "Alguien que me oriente al principio y me dé feedback constructivo, para poder mejorar y ganar autonomía poco a poco.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Qué te gustaría conseguir en tu primer mes?",
        "answer": "Entender cómo funciona la empresa y su parte tecnológica: la arquitectura, las tecnologías que usa y para qué sirve cada parte, aunque sea a un nivel básico al principio. Es lo que hice en Brainy y creo que es la mejor forma de empezar. Al terminar el primer mes, me gustaría estar adaptado y tener claro qué tengo que hacer y cómo.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Qué formación te gustaría recibir de la empresa?",
        "answer": "Sobre las tecnologías que use la empresa y que yo no conozca todavía. Aprendo también por mi cuenta, pero una formación de la empresa me ayudaría a ser útil antes, y la agradecería mucho.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Estás en otros procesos de selección?",
        "answer": "Estoy en búsqueda activa.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Disponibilidad para viajar? ¿Podrías viajar para reuniones?",
        "answer": "Puedo viajar de forma puntual para reuniones. Ir varios días a la semana a otra ciudad de forma habitual lo valoraría según las condiciones.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Horario o guardias?",
        "answer": "Mi preferencia sería un horario fijo de mañana, aunque lo hablaría según el puesto. Las guardias también las valoraría según el puesto y las condiciones.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Podrías salir de Zaragoza temporalmente, por ejemplo para una formación? (no es mudarse)",
        "answer": "Una formación temporal fuera de Zaragoza la valoraría según las condiciones. Lo que no contemplo es mudarme de forma permanente.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Podrías venir a una entrevista presencial? ¿Cuándo podrías hacer una entrevista en nuestras oficinas? ¿Puedes venir a la oficina? ¿Te viene bien una entrevista presencial? ¿Podrías hacer la entrevista en persona?",
        "answer": "Sí, puedo ir a entrevistas presenciales en Zaragoza. Si fuera en otra ciudad, lo hablamos y me organizo.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Tienes forma de moverte o desplazarte hasta el lugar de trabajo? (carnet, coche, transporte)",
        "answer": "Vivo en Zaragoza y mi preferencia es el trabajo híbrido o remoto. Ahora mismo me estoy sacando el carnet de conducir.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Carnet de conducir?",
        "answer": "Ahora mismo me estoy sacando el carnet de conducir.",
        "fixed_answer": False,
    },
    {
        "topic": "Más técnico",
        "question": "¿Qué nivel de SQL tienes?",
        "answer": "Básico: consultas de selección, inserción, actualización y borrado, con filtros. Lo aprendí en el grado y lo apliqué en Balancea, donde toda la persistencia va con SQLite, así que sé explicar cómo funciona. En este proyecto uso SQLAlchemy sobre SQLite.",
        "fixed_answer": False,
    },
    {
        "topic": "Más técnico",
        "question": "¿Has trabajado con metodologías ágiles?",
        "answer": "Las vi en teoría en el grado. En Brainy no seguíamos Scrum de forma formal, pero trabajábamos de forma parecida: tareas asignadas en una plataforma con su estado y reuniones semanales para planificar y revisar.",
        "fixed_answer": False,
    },
    {
        "topic": "Más técnico",
        "question": "¿Cómo te manejas con Linux y la terminal?",
        "answer": "A nivel básico: moverme entre carpetas, listar y gestionar archivos, y trabajar con Git (clonar repositorios, crear ramas, hacer commits y subir cambios), que es lo que usaba a diario en las prácticas. Si necesito un comando más complejo, busco la documentación o lo consulto.",
        "fixed_answer": False,
    },
    {
        "topic": "Más técnico",
        "question": "¿Cómo te mantienes al día en tecnología?",
        "answer": "Ahora estoy terminando un curso de Python en Coddy y desarrollando este proyecto. Además, sigo las ofertas de backend en LinkedIn para ver qué tecnologías pide el mercado (Java, Spring Boot, bases de datos…) y orientar lo que aprendo.",
        "fixed_answer": False,
    },
    {
        "topic": "Historia y formación",
        "question": "¿Por qué estudiaste DAM?",
        "answer": "La programación y la tecnología siempre me llamaron la atención. Al empezar DAM, en los primeros meses descubrí de verdad lo que era programar y me gustó tanto que tuve claro que quería dedicarme a ello.",
        "fixed_answer": False,
    },
    {
        "topic": "Historia y formación",
        "question": "¿Cómo empezaste a programar?",
        "answer": "Tuve un primer contacto muy básico en 4.º de la ESO, pero empecé a programar de verdad en primero de DAM, con Java, desde el primer \"Hello World\".",
        "fixed_answer": False,
    },
    {
        "topic": "Historia y formación",
        "question": "¿Por qué un grado superior y no la universidad?",
        "answer": "Hice Bachillerato de Ciencias porque entonces aún no tenía claro qué estudiar. Al terminarlo ya sabía que quería dedicarme a la programación, y elegí un grado superior porque es una formación más práctica y orientada a trabajar cuanto antes.",
        "fixed_answer": False,
    },
    {
        "topic": "Historia y formación",
        "question": "¿Qué es lo que más te gustó del grado?",
        "answer": "Programar en Java y desarrollar aplicaciones, sobre todo mi proyecto final, Balancea, que hice por mi cuenta. Lo que más disfruto es tener que pensar: los desafíos que se resuelven con lógica.",
        "fixed_answer": False,
    },
    {
        "topic": "Historia y formación",
        "question": "¿Qué echaste de menos en el grado?",
        "answer": "Me habría gustado ver más tecnologías de backend, como APIs, Docker o Python, que no se daban en el grado. Por eso las aprendí en las prácticas y las sigo reforzando por mi cuenta.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Qué hiciste en las prácticas?",
        "answer": "Empecé conociendo la plataforma de Brainy: puse en marcha en mi portátil una versión anterior de su API, con un frontal y una base de datos de pruebas, para entender cómo estaba construida. Después, mi trabajo principal fue refactorizar varios workers en Python que ya estaban dockerizados: adaptaba un prompt base a cada uno, hacía la refactorización con Codex, revisaba el resultado, lo comprobaba con un script de integración manual y subía los cambios a una rama nueva en GitLab. Al final también dockericé desde cero un worker que no tenía nada de Docker, que fue el más complejo.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Qué fue lo más difícil y cómo lo resolviste?",
        "answer": "Dos cosas. Primero, poner en marcha la API en local: en el grado no habíamos visto qué es una API, así que al principio iba bastante perdido. Lo resolví con paciencia, explorando cada parte del proyecto hasta entender cómo encajaba todo. Segundo, dockerizar desde cero el worker que me asignaron, que no tenía ni Dockerfile ni docker-compose. Fue el que más me costó (casi una semana); lo resolví comparándolo con los workers que ya estaban dockerizados para ver qué archivos y cambios le faltaban.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Cómo era el equipo?",
        "answer": "Un equipo pequeño, de unas seis personas, cada una con su área (frontend, CI/CD, backend…). Tenía un tutor y compañeros a los que consultar mis dudas, y en los últimos meses recibía las tareas a través de la plataforma del equipo.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Qué es lo más importante que aprendiste?",
        "answer": "En lo técnico, entender qué es una API, cómo está compuesta y cómo funciona, además de Docker y una base de Python, que no se daban en el grado. Y fuera de lo técnico, cómo es trabajar de verdad en un entorno profesional, en una oficina y con compañeros.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Qué fue lo más exigente de las prácticas? ¿Qué es lo que menos te gustó?",
        "answer": "Me llevo una experiencia muy positiva. Lo que más me costó al principio fue entender APIs y Docker desde cero, porque no los había visto en el grado, pero también fue con lo que más aprendí.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Hubo algo malo en las prácticas? (si insisten: \"pero dime algo malo\")",
        "answer": "Sinceramente, no tengo nada malo que destacar: fue una buena experiencia y aprendí mucho. Lo más exigente fue empezar con tecnologías que no conocía, y eso lo veo como algo positivo.",
        "fixed_answer": False,
    },
    {
        "topic": "Balancea (proyecto final)",
        "question": "¿Por qué una app de finanzas personales?",
        "answer": "Primero decidí las tecnologías que quería usar (Java, Android Studio y SQLite) y después barajé varias ideas que las aprovecharan. La de finanzas personales era la más adecuada y, además, me permitía añadir gráficas, que daban un nivel extra al proyecto.",
        "fixed_answer": False,
    },
    {
        "topic": "Balancea (proyecto final)",
        "question": "¿De qué estás más orgulloso?",
        "answer": "De que salió como lo había planeado: me dio tiempo a hacer todo lo previsto y la app funciona de verdad, cualquiera podría usarla para llevar sus finanzas. Sobre todo, de las gráficas y de la persistencia de los datos.",
        "fixed_answer": False,
    },
    {
        "topic": "Balancea (proyecto final)",
        "question": "¿Qué fue lo más difícil?",
        "answer": "Las gráficas. Usé la librería MPAndroidChart, algo totalmente nuevo para mí que no había visto ni en el grado ni en las prácticas. Lo saqué adelante con ayuda de la IA.",
        "fixed_answer": False,
    },
    {
        "topic": "Balancea (proyecto final)",
        "question": "¿Qué mejorarías?",
        "answer": "Poder editar o eliminar un movimiento, mejorar la seguridad de cómo se guardan las contraseñas y añadir copia en la nube.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Por qué backend?",
        "answer": "Lo que más me gusta de la programación es lo que no se ve: la lógica que hace que una aplicación funcione, cómo se procesan y se guardan los datos y cómo se comunican las partes entre sí. Disfruto de los problemas que exigen pensar, más que del diseño visual.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Qué haces cuando te atascas?",
        "answer": "Intento verlo desde otra perspectiva y repasar todas las posibles soluciones antes de actuar. Si sigo atascado, pregunto a un compañero, como hacía en las prácticas.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Qué quieres mejorar como profesional?",
        "answer": "Estoy empezando, así que quiero mejorar en todo. En concreto, entender bien código antiguo, que existe en todas las empresas, y conocer más tecnologías como Kubernetes o Kafka. Lo que más me atrae es Python y las APIs.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Cómo llevas el feedback?",
        "answer": "Muy bien, siempre que sea constructivo. Estoy empezando, y que me corrijan es la mejor forma de aprender.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Qué te motiva en un trabajo? ¿Qué te motiva?",
        "answer": "Crecer profesionalmente en la programación y seguir aprendiendo, porque es lo que me gusta. Me motivan los retos que me hacen pensar, sobre todo en backend y APIs, y trabajar en un equipo del que pueda aprender, como me pasó en las prácticas. Y ver que lo que construyo funciona de verdad, como Balancea.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Usas IA para programar?",
        "answer": "La uso con un método, no de cualquier manera. Primero entiendo el problema. Le doy a la IA contexto y reglas claras desde el principio y le pido un plan sin que toque nada. Reviso y ajusto ese plan, y las decisiones las tomo yo. La implementación se hace por pasos pequeños, y reviso lo que ha hecho y lo verifico con pruebas antes de guardarlo. La IA es una herramienta que dirijo y reviso, no la dejo trabajar sola. La usé en las prácticas (con Codex) y en este proyecto (con Claude Code).",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Cómo usabas la IA en las prácticas?",
        "answer": "Usaba Codex para refactorizar los workers. Había un prompt base, pero para cada worker primero analizaba el worker y adaptaba ese prompt a él. Después hacía la refactorización con Codex, revisaba lo que había generado y lo comprobaba con mi script de prueba. Si funcionaba, lo subía a una rama nueva en GitLab.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Cómo has usado la IA en este proyecto? ¿Lo ha hecho todo la IA?",
        "answer": "Lo he desarrollado con Claude Code, pero dirigiéndolo yo. Escribí un archivo de reglas para la IA, le pedí planes antes de cada cambio importante (la base de datos, la web, el chat, el RAG) y decidí yo cosas como qué datos personales no publicar o qué proveedores usar. Detecté y corregí contradicciones, y exigí pruebas con los proveedores reales antes de dar nada por bueno. La IA es una herramienta que dirijo y reviso, no la dejo trabajar sola.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "Si no existiera la IA, ¿sabrías hacer esta página? ¿Podrías hacer este proyecto sin IA?",
        "answer": "Con lo que sé de Java y Python habría podido hacer una versión más sencilla, pero habría tardado mucho más. Con Claude Code llegué a algo más completo, y entiendo lo que hay porque reviso cada plan y cada cambio antes de aceptarlo.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "Soft skills",
        "answer": "He jugado toda la vida a deportes de equipo, así que me gusta mucho trabajar en equipo. Ser portero de fútbol sala me ha enseñado a mantener la calma bajo presión, a comunicarme con el equipo y a asumir responsabilidad cuando algo sale mal. Me considero empático, con facilidad para ponerme en el lugar de los demás, y con muchas ganas de aprender.",
        "fixed_answer": False,
    },
    {
        "topic": "Lo que busco",
        "question": "¿Qué tipo de puesto buscas?",
        "answer": "Un puesto de desarrollador backend junior, preferiblemente con Python, aunque también estoy abierto a Java. Me interesa especialmente el desarrollo de APIs.",
        "fixed_answer": False,
    },
    {
        "topic": "Lo que busco",
        "question": "¿En qué sector te gustaría trabajar?",
        "answer": "No tengo un sector cerrado. Lo que me importa es trabajar en lo que me gusta: desarrollo backend, a ser posible con Python y APIs, en un equipo donde pueda aprender y aportar.",
        "fixed_answer": False,
    },
    {
        "topic": "Lo que busco",
        "question": "¿Dónde te ves en unos años?",
        "answer": "Como desarrollador backend con más experiencia, idealmente en Python, habiendo crecido dentro de un equipo hasta llegar a un perfil senior.",
        "fixed_answer": False,
    },
    {
        "topic": "Lo que busco",
        "question": "Disponibilidad y modalidad",
        "answer": "Disponibilidad inmediata y jornada completa. En Zaragoza acepto presencial, híbrido o remoto, aunque mi preferencia es híbrido o remoto. Fuera de Zaragoza, remoto. Ahora mismo no contemplo mudarme. Mi preferencia es estar contratado como empleado, aunque estoy abierto a escuchar otras fórmulas, como trabajar de contractor.",
        "fixed_answer": False,
    },
    {
        "topic": "Lo que busco",
        "question": "¿Qué tecnologías te gustaría aprender?",
        "answer": "Quiero profundizar en lo que ya he empezado: diseño de APIs, Docker, Python, bases de datos como PostgreSQL y testing, que ya uso en este proyecto. Además, más adelante me gustaría aprender tecnologías como Kubernetes o Kafka.",
        "fixed_answer": False,
    },
    {
        "topic": "Lo que busco",
        "question": "Inglés",
        "answer": "Nivel B2 certificado (2022). Entiendo bien el inglés y me veo capaz de leer documentación técnica y participar en reuniones. Lo que más quiero seguir practicando es la conversación fluida. También consumo contenido en inglés en mi tiempo libre.",
        "fixed_answer": False,
    },
    {
        "topic": "Personal",
        "question": "¿Qué haces en tu tiempo libre? ¿Cuáles son tus hobbies o aficiones?",
        "answer": "Juego al fútbol desde los 4 años y soy portero de fútbol sala. También me gusta estar con mis amigos, jugar a videojuegos y, sinceramente, programar y aprender cosas nuevas, porque es algo que me gusta.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué has hecho desde que terminaste las prácticas?",
        "answer": "Al terminar a la vez el grado y las prácticas, me tomé el verano para descansar. Desde septiembre me he dedicado por completo a mi búsqueda de empleo: estoy terminando el curso de Python, he creado este proyecto (la API, la web y el chat) y he preparado mis perfiles profesionales.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Por qué no te quedaste en Brainy?",
        "answer": "Terminé las prácticas con una valoración muy positiva de mi tutor y se habló de que continuara en la empresa, pero finalmente no se llegó a concretar una vacante para mí. Me llevo una muy buena experiencia y muchos aprendizajes.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Tienes referencias?",
        "answer": "Ahora mismo no tengo referencias que facilitar. Si quieres saber más de mi etapa de prácticas, escríbeme a manusastrenar@gmail.com.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Puedes trabajar en España o en la Unión Europea?",
        "answer": "Sí, puedo trabajar en España y en cualquier país de la UE sin visado ni permiso de trabajo.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Cuándo terminas el curso de Python? ¿Tendrás certificado?",
        "answer": "Me queda poco para terminarlo, y al acabar obtendré el certificado del curso.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Cómo te organizas trabajando en remoto?",
        "answer": "De la misma forma que en las prácticas: para cada tarea apunto primero los pasos que necesito para completarla y voy marcando cada uno al terminarlo. Así tengo siempre claro mi progreso y en qué tengo que centrarme, aunque no esté en una oficina.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "Sobre este proyecto: ¿qué fue lo más difícil?",
        "answer": "Es el primer proyecto que he desarrollado de principio a fin trabajando con un agente de IA como Claude Code. En Balancea solo usé la IA para las gráficas con MPAndroidChart; el resto lo programé yo. Lo más difícil fue al principio: preparar y configurar yo solo todo el entorno de trabajo (Visual Studio Code, Docker, Claude Code) y aprender a usar estas herramientas de forma independiente.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "Sobre este proyecto: ¿qué has aprendido?",
        "answer": "A trabajar con Claude Code dentro de Visual Studio Code, a usar Docker por mi cuenta y a construir paso a paso una aplicación completa: una API REST con FastAPI, una base de datos, una web que consume esa API y un chat conectado a modelos de IA.",
        "fixed_answer": False,
    },
    {
        "topic": "Más técnico",
        "question": "¿Qué tecnologías usa este proyecto? Tecnologías de esta web, la API y el chat",
        "answer": "Python con FastAPI para la API REST, SQLAlchemy con SQLite para los datos del CV, PostgreSQL (en Neon) para las estadísticas del chat, Docker, pytest para los tests (se ejecutan automáticamente en GitHub Actions), y Gemini y Groq con RAG para el chat. Está desplegado en Render.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué sabes hacer en Python?",
        "answer": "Tengo un nivel básico: estructuras como listas, tuplas y arrays, y la lógica del lenguaje, que estoy reforzando con el curso de Coddy. En las prácticas trabajé sobre código Python real: leía y entendía los workers, los refactorizaba con Codex, revisaba lo que generaba y comprobaba que funcionaban. Sé leer y entender código Python, y sigo mejorando a la hora de escribirlo por mi cuenta.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué nivel de Java tienes?",
        "answer": "Java fue mi lenguaje principal en el grado, con programación orientada a objetos, y con él desarrollé Balancea, que está en mi GitHub y es la mejor muestra de mi nivel. No lo he usado en los últimos meses, así que lo tendría que retomar, pero es el lenguaje con el que más he programado.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué sabes hacer con Docker?",
        "answer": "Sé leer y entender un Dockerfile y un docker-compose, y levantar y gestionar contenedores desde la terminal con docker compose. En las prácticas dockericé un worker que no tenía nada de Docker, y en este proyecto toda la aplicación funciona en un contenedor. Los archivos de configuración los escribo apoyándome en la IA y los reviso entendiendo qué hace cada parte.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Sabes HTML, CSS o JavaScript? ¿Harías frontend?",
        "answer": "Mi nivel de frontend es básico, porque me centro en el backend. La interfaz de esta web la hice con apoyo de IA; la de Balancea la programé yo casi toda a mano, con IA solo en las gráficas. Si en un momento dado hiciera falta tocar algo de frontend, podría hacerlo con ese apoyo, aunque donde quiero crecer es en el backend.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Conoces la programación orientada a objetos y patrones de diseño?",
        "answer": "Sí, la programación orientada a objetos es la base de lo que aprendí en el grado con Java, y Balancea está organizada así, con clases para los datos (usuario, movimiento), las pantallas y el acceso a la base de datos. También conozco la idea de MVC, que separa los datos (modelo), la interfaz (vista) y la lógica que los conecta (controlador): en Balancea tenía separados los modelos y el acceso a la base de datos de las pantallas, y en esta API separo las rutas, las consultas y los modelos de datos. Quiero seguir profundizando en patrones de diseño.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Has hecho tests?",
        "answer": "Sí. En las prácticas, al refactorizar cada worker creaba un script de prueba en Python que le enviaba un documento de entrada; lo ejecutaba desde la consola y seguía el proceso mediante los logs, para comprobar de principio a fin que el worker funcionaba. En este proyecto hay tests automáticos con pytest. En el grado no llegamos a ver testing.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Hiciste otros proyectos en el grado?",
        "answer": "Sí, en mi centro, Océano Atlántico, nos evaluaban sobre todo mediante proyectos: nos daban los objetivos que había que conseguir y cada uno lo desarrollaba. Balancea es el único que he publicado porque es el que planteé y desarrollé completamente por mi cuenta, desde la idea hasta el final.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Cuál es tu mayor punto fuerte técnico?",
        "answer": "Las APIs y Docker, que es donde más he trabajado en las prácticas y en este proyecto. Además, sé trabajar con herramientas de IA para programar con un método: pido un plan, decido yo, avanzo por pasos pequeños y reviso y pruebo lo que generan, lo que me permite avanzar más rápido.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué haces si cometes un error en el trabajo?",
        "answer": "Lo reconozco, me disculpo si ha afectado a algún compañero e intento solucionarlo cuanto antes y de la mejor manera posible.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué haces si te mandan una tarea que no sabes hacer?",
        "answer": "Primero investigo cómo se hace, buscando información y pidiendo a la IA que me lo explique. Con eso, intento entenderlo y desarrollarlo yo. Si aun así me atasco, me apoyo en la IA o pregunto a un compañero, como hacía en las prácticas.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Aceptarías unas prácticas, una beca o un contrato temporal?",
        "answer": "No busco prácticas ni becas. Busco un contrato laboral como empleado, a jornada completa, preferiblemente indefinido.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "Si estudiaste DAM, ¿por qué backend y no aplicaciones móviles?",
        "answer": "Porque en las prácticas descubrí el backend y es lo que más me ha gustado hasta ahora. Las aplicaciones móviles también me interesan: de hecho, Balancea es una app Android, y tengo pensado desarrollar otra app móvil por mi cuenta más adelante.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Dónde vives?",
        "answer": "En Zaragoza.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué valoras más en una empresa?",
        "answer": "El buen ambiente de trabajo, poder seguir aprendiendo y la estabilidad.",
        "fixed_answer": False,
    },
    {
        "topic": "Más técnico",
        "question": "¿Desde cuándo usas Python?",
        "answer": "Empecé con Python en las prácticas de Brainy, en enero de 2026, porque en el grado no se daba. En septiembre de 2026 empecé por mi cuenta el curso de Coddy para reforzarlo.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Cobrabas en las prácticas?",
        "answer": "No, eran las prácticas FCT del grado, que no son remuneradas.",
        "fixed_answer": False,
    },
    {
        "topic": "Experiencia",
        "question": "¿Cuánta experiencia tienes? ¿Qué experiencia tienes?",
        "answer": "Como perfil junior, mi experiencia profesional son mis prácticas en Brainy Inteligencia Semántica, del 26 de enero al 15 de mayo de 2026: refactoricé workers en Python, dockericé uno desde cero, trabajé con Git y GitLab y puse en marcha en local una versión anterior de su API para entender su arquitectura. Además, he desarrollado Balancea, mi proyecto final en Java, y este proyecto con API, web y chat.",
        "fixed_answer": False,
    },
    {
        "topic": "Experiencia",
        "question": "¿Cuánto tiempo llevas programando?",
        "answer": "Programo desde que empecé DAM en 2024, aunque tuve un primer contacto muy básico en 4.º de la ESO. Python lo empecé en las prácticas, en enero de 2026.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué tecnologías conoces? Lenguajes, herramientas y IA",
        "answer": "Lenguajes: Python (prácticas, este proyecto y el curso de Python en Coddy que estoy terminando), Java (grado y Balancea) y SQL básico. Herramientas: Docker, Git, GitLab, Android Studio, Visual Studio Code, la consola, Windows y Linux, y nociones de Kafka. En este proyecto uso FastAPI, API REST, SQLAlchemy, pytest y PostgreSQL en Neon. En IA, Codex en las prácticas y Claude Code en este proyecto.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Con qué tecnología has trabajado más? ¿Con cuál has trabajado más?",
        "answer": "Java es el lenguaje con el que más he programado, en el grado y en Balancea, aunque no lo uso desde hace unos meses. Desde enero de 2026 trabajo con Python: en las prácticas, en este proyecto y en el curso de Coddy. Docker, Git y GitLab los usé en las prácticas.",
        "fixed_answer": False,
    },
    {
        "topic": "Formación",
        "question": "¿Qué aprendiste en el grado?",
        "answer": "En el grado aprendí a programar en Java, con programación orientada a objetos, y a desarrollar aplicaciones Android con bases de datos SQLite, que apliqué en Balancea, mi proyecto final. Eché de menos ver más tecnologías de backend, como APIs, Docker o Python, que aprendí después en las prácticas.",
        "fixed_answer": False,
    },
    {
        "topic": "Proyectos",
        "question": "¿Dónde está el código de este proyecto? ¿Está tu código en GitHub?",
        "answer": "Sí. El código de este proyecto (la API, la web y el chat) está en GitHub, en github.com/Manuel7624/cv-api, y mi proyecto final, Balancea, en github.com/Manuel7624/TFG_ManuelSastre. Mi perfil es github.com/Manuel7624.",
        "fixed_answer": False,
    },
    {
        "topic": "Experiencia",
        "question": "¿Cuántos workers dockerizaste?",
        "answer": "Dockericé desde cero uno, el más complejo, que no tenía nada de Docker; no tengo una cifra exacta de más que darte. El resto de mi trabajo con workers fue refactorizar varios que ya estaban dockerizados.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Qué es el proyecto CV con API y chat de IA? ¿Qué es esta web?",
        "answer": "Es mi web personal, con una API REST propia hecha con FastAPI que sirve mi CV desde una base de datos y tiene documentación Swagger. Está publicada en Vercel y Render y el código está en github.com/Manuel7624/cv-api. La idea, el diseño y el plan son míos; la implementación la hago con Claude Code bajo mi dirección.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Cómo funciona el chat de IA? ¿Qué es el RAG? ¿Qué proveedores usa?",
        "answer": "Responde en primera persona sobre mi perfil. Primero busca los datos relevantes para la pregunta (RAG) y responde solo con ellos, para no inventar. Usa varios proveedores (Gemini y Groq) y cambia automáticamente si uno falla, y tiene límites de uso (rate limiting). De RAG tengo nociones.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Cómo validas este proyecto? ¿Usas pytest y PostgreSQL en él?",
        "answer": "Sí: más de 360 tests automáticos con pytest, una batería de preguntas para evaluar las respuestas del chat y revisión manual de cada cambio. PostgreSQL lo uso en este proyecto, junto a SQLite, y de SQL conozco ambos.",
        "fixed_answer": False,
    },
    {
        "topic": "Desarrollo con IA",
        "question": "¿Cómo desarrollas con agentes de IA? ¿Cómo usas la IA para programar?",
        "answer": "Desarrollo con agentes de IA: Claude Code en este proyecto y Codex en las prácticas. Defino los requisitos y las reglas del proyecto, reviso el plan de cada tarea, valido con pruebas y evalúo la calidad de las respuestas, manteniendo el control técnico de cada cambio.",
        "fixed_answer": False,
    },
    {
        "topic": "Desarrollo con IA",
        "question": "¿Sabes programar sin IA? ¿Programas tú o lo hace la IA?",
        "answer": "Sí. Balancea la programé yo casi toda a mano; solo usé IA para las gráficas con MPAndroidChart. En este proyecto la idea, el diseño y el plan son míos, y la implementación la hago con Claude Code bajo mi dirección, revisando cada cambio.",
        "fixed_answer": False,
    },
    {
        "topic": "Desarrollo con IA",
        "question": "¿Qué es CLAUDE.md y para qué lo usas? ¿Qué son las reglas del proyecto?",
        "answer": "Es el archivo de reglas del proyecto que le doy a Claude Code: los requisitos y las decisiones, para que la IA parta de un contexto claro. Con él y con un plan por tarea que yo reviso y ajusto, avanzamos en pasos pequeños.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Cómo compruebas que el chat no inventa? ¿Cómo evalúas las respuestas?",
        "answer": "El chat responde solo con los datos relevantes que recupera (RAG). Evalúo la calidad de sus respuestas con baterías de preguntas y reviso en el panel de administración las preguntas sin respuesta para mejorarlo.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Qué es el panel de administración y qué se ve ahí?",
        "answer": "Es un panel con contraseña donde veo estadísticas del chat: las últimas preguntas y respuestas, los límites de uso, las preguntas sin respuesta y los tiempos. Lo uso para revisar la IA y mejorarla. Es privado, así que no puedo dar su dirección ni su contraseña.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Qué es rate limiting y qué es la tolerancia a fallos en tu API?",
        "answer": "Rate limiting son límites de uso: limito los mensajes del chat para evitar abusos y controlar el gasto. La tolerancia a fallos es que, si un proveedor de IA (Gemini o Groq) falla, el chat pasa automáticamente a otro.",
        "fixed_answer": False,
    },
    {
        "topic": "Este proyecto",
        "question": "¿Qué base de datos usas y para qué? ¿Qué es SQLAlchemy?",
        "answer": "SQLite para los datos de mi CV, con SQLAlchemy, y PostgreSQL (en Neon) para las estadísticas del chat, sin SQLAlchemy. SQLAlchemy es una librería de Python que permite trabajar con la base de datos con clases y objetos en vez de escribir todo el SQL a mano.",
        "fixed_answer": False,
    },
    {
        "topic": "Contacto",
        "question": "¿Cómo te contacto? ¿Cómo puedo contactarte? ¿Dónde te escribo?",
        "answer": f"Puedes contactarme por correo en {PROFILE['email']} o por LinkedIn ({PROFILE['linkedin']}). Mi teléfono aparece en mi perfil de LinkedIn.",
        "fixed_answer": False,
    },
    {
        "topic": "Contacto",
        "question": "¿Por qué no pones tu teléfono en la web? ¿Por qué no está tu teléfono aquí?",
        "answer": "Prefiero no publicar mi teléfono en una web abierta, donde cualquiera puede copiarlo. Está en mi perfil de LinkedIn y también puedes pedírmelo por correo.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿En qué te diferencias de otros candidatos? ¿Qué te hace diferente? ¿Qué te distingue del resto? ¿Cuál es tu diferencial?",
        "answer": "Mi diferencial es el desarrollo asistido por IA con un flujo de trabajo estructurado: defino los requisitos y las reglas del proyecto, reviso el plan de cada tarea antes de implementarla y valido cada cambio con pruebas, manteniendo el control técnico. Esta web, con su API, su chat y más de 360 tests, está construida así y se puede probar ahora mismo. A eso le sumo la experiencia de unas prácticas en un equipo real, con Docker, Git y GitLab, y las ganas de seguir creciendo junto a compañeros con más experiencia.",
        "fixed_answer": False,
    },
]


def seed(session: Session) -> None:
    """Carga los datos iniciales si la base está vacía.

    Todo se guarda en un único commit: o se carga entero o no se carga nada, así
    que comprobar si existe el perfil basta para saber si ya está cargado.
    """
    if session.scalar(select(models.Profile.id)) is not None:
        return

    session.add(models.Profile(**PROFILE))

    for position, item in enumerate(EXPERIENCE):
        session.add(
            models.Experience(
                role=item["role"],
                company=item["company"],
                kind=item["kind"],
                period=item["period"],
                position=position,
                highlights=[
                    models.ExperienceHighlight(text=text, position=index)
                    for index, text in enumerate(item["highlights"])
                ],
            )
        )

    for position, item in enumerate(PROJECTS):
        session.add(
            models.Project(
                name=item["name"],
                description=item["description"],
                repository=item["repository"],
                position=position,
                highlights=[
                    models.ProjectHighlight(text=text, position=index)
                    for index, text in enumerate(item["highlights"])
                ],
                technologies=[
                    models.ProjectTechnology(name=name, position=index)
                    for index, name in enumerate(item["technologies"])
                ],
            )
        )

    for position, item in enumerate(EDUCATION):
        session.add(models.Education(**item, position=position))

    for category, names in SKILLS.items():
        for position, name in enumerate(names):
            session.add(models.Skill(category=category, name=name, position=position))

    for position, item in enumerate(LANGUAGES):
        session.add(models.Language(**item, position=position))

    for position, item in enumerate(EXTRA_INFO):
        session.add(models.ExtraInfo(**item, position=position))

    session.commit()
