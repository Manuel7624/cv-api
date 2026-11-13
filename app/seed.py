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
    "title": "Junior Backend Developer",
    "location": "Zaragoza, España",
    "summary": (
        "Técnico Superior en Desarrollo de Aplicaciones Multiplataforma, con "
        "prácticas en una empresa de software (Python, Docker y GitLab) y un "
        "proyecto propio en Android con Java y SQLite. Busco mi primera "
        "oportunidad como desarrollador backend junior y seguir creciendo en "
        "Python."
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
        "period": "26 de enero – 15 de mayo de 2026",
        "highlights": [
            "Refactorización y optimización de workers en Python para mejorar "
            "su estructura y legibilidad; comprobación mediante pruebas de "
            "sus respuestas y comportamiento esperado. Apoyo de Codex con un "
            "prompt base adaptado a cada worker.",
            "Dockerización de los workers que aún no estaban contenerizados y "
            "subida de los cambios a nuevas ramas en GitLab.",
            "Puesta en marcha en local de la API (versión anterior) de la "
            "plataforma, junto con el frontend y una base de datos de pruebas, "
            "para familiarizarme con su arquitectura y funcionamiento; "
            "nociones de Kafka.",
            "Control de versiones con Git y GitLab (clonado, ramas, commits y "
            "push) y uso básico de la consola.",
        ],
    },
    {
        "role": "Azafato",
        "company": "The Wave 2026, Zaragoza",
        "kind": "Trabajo temporal",
        "period": "14 – 16 de abril de 2026",
        "highlights": [
            "Preparación y reorganización del escenario principal entre "
            "intervenciones.",
            "Atención e información a los asistentes durante el evento.",
        ],
    },
]

PROJECTS = [
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
        "Python (prácticas y curso en Coddy)",
        "Java (grado y proyecto final)",
        "SQL (SQLite)",
    ],
    "tools": [
        "Docker",
        "Git",
        "GitLab",
        "Android Studio",
        "Visual Studio Code",
        "Consola",
        "Codex",
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
# fixed_answer=True marca un tema delicado (sueldo, nota media): el chat no da
# ninguna cifra y responde con ese texto.
EXTRA_INFO = [
    {
        "topic": "Temas que el chatbot NO debe responder con datos",
        "question": "Expectativas salariales, sueldo o rango salarial",
        "answer": "Es algo que prefiero hablar directamente, porque depende del puesto, la modalidad y las condiciones. Puedes escribirme a mi correo y lo comentamos.",
        "fixed_answer": True,
    },
    {
        "topic": "Temas que el chatbot NO debe responder con datos",
        "question": "Nota media o calificaciones del grado",
        "answer": "Más que en la nota, durante el grado me centré en aprender y en que mis proyectos funcionaran bien. El resultado se puede ver en Balancea, mi proyecto final, y en este mismo proyecto.",
        "fixed_answer": True,
    },
    {
        "topic": "Presentación",
        "question": "Háblame de ti",
        "answer": "Soy Manuel, Técnico Superior en Desarrollo de Aplicaciones Multiplataforma, de Zaragoza, y busco mi primer puesto como desarrollador backend junior. En mis prácticas en Brainy Inteligencia Semántica trabajé con Python, Docker y GitLab refactorizando varios workers que ya estaban dockerizados y dockerizando desde cero uno que no tenía nada de Docker, y mi proyecto final fue Balancea, una app Android de finanzas personales en Java con SQLite. Ahora estoy reforzando Python y he creado este proyecto: una API REST con FastAPI, base de datos, Docker y tests, que sirve esta web y este chat. Lo que más me gusta de programar es la lógica y resolver problemas, y tengo muchas ganas de seguir aprendiendo dentro de un equipo.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Cuáles son tus puntos fuertes?",
        "answer": "- **Resolución de problemas:** me gusta que un reto me haga pensar; analizo el problema desde varias perspectivas y valoro las posibles soluciones antes de actuar.\n- **Trabajo en equipo:** llevo toda la vida jugando a deportes de equipo y es algo que se me da bien.\n- **Adaptación y aprendizaje:** si hay algo que no entiendo en un trabajo nuevo, busco información, exploro y pregunto hasta entenderlo. Me pasó en las prácticas con las APIs y Docker, que no había visto en el grado.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Cuál es tu punto débil?",
        "answer": "Por naturaleza no soy la persona más organizada, así que en el trabajo me apoyo en métodos concretos. En las prácticas, por ejemplo, llevaba una lista con cada tarea dividida en fases y marcaba cada paso al completarlo, para tener siempre claro en qué punto estaba.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Por qué deberían contratarte?",
        "answer": "Porque, aunque soy junior, ya he trabajado en un entorno real con Python, Docker y Git, y he demostrado que aprendo rápido: en las prácticas tuve que entender APIs y Docker desde cero y acabé refactorizando varios workers que ya estaban dockerizados y dockerizando desde cero uno que no tenía nada de Docker. Además, he construido por mi cuenta este proyecto completo, desde la API hasta la web y el chat. También sé trabajar bien con herramientas de IA para programar: las uso paso a paso, explicando con claridad lo que necesito y revisando todo lo que generan, lo que me permite avanzar más rápido sin perder el control del código. Me adapto a la forma de trabajar de cada equipo, me tomo en serio la calidad de lo que entrego y tengo muchas ganas de crecer en la empresa.",
        "fixed_answer": False,
    },
    {
        "topic": "Presentación",
        "question": "¿Cuándo puedes empezar?",
        "answer": "De inmediato.",
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
        "answer": "En las prácticas me asignaban, por ejemplo, tres workers por semana. Los apuntaba en una lista y cada uno pasaba por tres fases: refactorización, comprobación y subida a Git. Marcaba cada fase al completarla, así veía el progreso de cada worker, y al terminar uno empezaba el siguiente.",
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
        "question": "¿Disponibilidad para viajar, horario o guardias?",
        "answer": "Puedo viajar de forma puntual. Mi preferencia sería un horario fijo de mañana, aunque lo hablaría según el puesto. Las guardias también las valoraría según el puesto y las condiciones.",
        "fixed_answer": False,
    },
    {
        "topic": "Más sobre cómo trabajo",
        "question": "¿Carnet de conducir?",
        "answer": "De momento no tengo carnet ni coche; me lo estoy sacando.",
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
        "answer": "Las vi en teoría en el grado. En Brainy no seguíamos Scrum de forma formal, pero trabajábamos de forma parecida: el responsable asignaba las tareas en una plataforma donde se veía su estado (en progreso, pausadas, terminadas), y teníamos dos reuniones semanales, los lunes para planificar la semana y los viernes para revisar cómo había ido.",
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
        "answer": "Empecé conociendo el funcionamiento general de la plataforma de Brainy. Mi primera prueba fue poner en marcha en mi portátil una versión anterior de su API, conectada a un frontal y a una base de datos de pruebas que me proporcionó la empresa, para entender cómo estaba construida. Después, mi trabajo principal fue refactorizar y optimizar varios workers en Python que ya estaban dockerizados, para que su código fuera más limpio y mantenible. Para cada worker preparaba una prueba (por ejemplo, enviarle un documento de ejemplo y verificar que lo procesaba correctamente), comprobaba que funcionaba y, cuando todo estaba bien, subía los cambios a una nueva rama en GitLab desde la terminal. Al final también dockericé desde cero un worker que no tenía nada de Docker, que fue el más complejo.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Qué fue lo más difícil y cómo lo resolviste?",
        "answer": "Dos cosas. Primero, poner en marcha la API en local: en el grado no habíamos visto qué es una API, así que al principio iba bastante perdido. Lo resolví con paciencia, explorando cada parte del proyecto hasta entender cómo encajaba todo. Segundo, dockerizar el último worker, que no tenía ni Dockerfile ni docker-compose. Fue el que más me costó (casi una semana); lo resolví comparándolo con los workers que ya estaban dockerizados para ver qué archivos y cambios le faltaban.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Cómo era el equipo?",
        "answer": "Éramos unas seis personas, cada una con su área (frontend, CI/CD, backend…). Mi tutor de prácticas era el responsable de la empresa, y en el día a día me guiaba la desarrolladora backend, que era quien más me enseñaba y a quien consultaba mis dudas. En los últimos meses ya recibía mis tareas directamente a través de la plataforma de gestión de tareas del equipo.",
        "fixed_answer": False,
    },
    {
        "topic": "Prácticas en Brainy Inteligencia Semántica",
        "question": "¿Qué es lo más importante que aprendiste?",
        "answer": "En lo técnico, entender qué es una API, cómo está compuesta y cómo funciona, además de Docker y una base de Python, que no se daban en el grado. Y fuera de lo técnico, cómo es trabajar de verdad en un entorno profesional, en una oficina y con compañeros.",
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
        "answer": "La mejora más importante, que además me señalaron en la defensa del proyecto, es poder eliminar o editar un movimiento si te equivocas al introducirlo. También guardaría las contraseñas cifradas en lugar de en texto plano, y añadiría copia de seguridad en la nube.",
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
        "answer": "Intento verlo desde otra perspectiva y repasar todas las posibles soluciones antes de actuar. Si sigo atascado, pregunto: en las prácticas consultaba a mi compañera de backend.",
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
        "question": "¿Qué te motiva en un trabajo?",
        "answer": "Crecer profesionalmente en la programación y seguir aprendiendo, porque es lo que me gusta.",
        "fixed_answer": False,
    },
    {
        "topic": "Cómo trabajo",
        "question": "¿Usas IA para programar?",
        "answer": "Sí. En las prácticas usaba Codex: adaptaba un prompt base a cada worker y después verificaba yo que el resultado funcionaba. Este proyecto (la web, la API y el chat) lo he desarrollado con ayuda de Claude Code. Mi forma de trabajar con IA es ir paso a paso: le explico claramente lo que quiero, reviso lo que hace y no la dejo trabajar sin control, para que no cometa errores.",
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
        "answer": "Quiero profundizar en lo que ya he empezado: diseño de APIs, Docker y Python. Además, me gustaría aprender bases de datos como PostgreSQL, testing, CI/CD y despliegue en la nube, y más adelante tecnologías como Kubernetes o Kafka.",
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
        "question": "¿Qué haces en tu tiempo libre?",
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
        "answer": "Sí, puedo facilitar referencias de mi etapa de prácticas en Brainy si una empresa las necesita. Para ello, lo mejor es escribirme al correo.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Puedes trabajar en España o en la Unión Europea?",
        "answer": "Sí. Tengo nacionalidad española, así que puedo trabajar en España y en cualquier país de la Unión Europea sin necesidad de visado ni permiso de trabajo.",
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
        "answer": "Es el primer proyecto que he desarrollado de principio a fin trabajando con un agente de IA como Claude Code. En Balancea ya me apoyé en la IA para partes concretas, como las gráficas o la interfaz. Lo más difícil fue al principio: preparar y configurar yo solo todo el entorno de trabajo (Visual Studio Code, Docker, Claude Code) y aprender a usar estas herramientas de forma independiente.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "Sobre este proyecto: ¿qué has aprendido?",
        "answer": "A trabajar con Claude Code dentro de Visual Studio Code, a usar Docker por mi cuenta y a construir paso a paso una aplicación completa: una API REST con FastAPI, una base de datos, una web que consume esa API y un chat conectado a modelos de IA.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué sabes hacer en Python?",
        "answer": "Tengo un nivel básico: estructuras como listas, tuplas y arrays, y la lógica del lenguaje, que estoy reforzando con el curso de Coddy. En las prácticas trabajé sobre código Python real: leía y entendía los workers, los refactorizaba con ayuda de IA y comprobaba que funcionaban. Sé leer y entender código Python, y sigo mejorando a la hora de escribirlo por mi cuenta.",
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
        "answer": "Mi nivel de frontend es básico, porque me centro en el backend. Tanto la interfaz de Balancea como la de esta web las hice con apoyo de IA. Si en un momento dado hiciera falta tocar algo de frontend, podría hacerlo con ese apoyo, aunque donde quiero crecer es en el backend.",
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
        "answer": "Sí. En las prácticas, al refactorizar cada worker creaba un script de prueba en Python que le enviaba un documento de ejemplo; lo ejecutaba desde la terminal y mostraba mensajes según iba completando cada paso, para comprobar que el worker funcionaba. En este proyecto hay tests automáticos con pytest. En el grado no llegamos a ver testing.",
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
        "answer": "Las APIs y Docker, que es donde más he trabajado en las prácticas y en este proyecto. Además, sé trabajar bien con herramientas de IA para programar, entendiendo y revisando lo que generan, lo que me permite avanzar más rápido.",
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
        "answer": "En Zaragoza capital.",
        "fixed_answer": False,
    },
    {
        "topic": "Nuevas preguntas y respuestas",
        "question": "¿Qué valoras más en una empresa?",
        "answer": "El buen ambiente de trabajo, poder seguir aprendiendo y la estabilidad.",
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
