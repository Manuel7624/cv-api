"""Límites del chatbot.

Los límites de mensajes y la longitud de las preguntas se pueden cambiar con
variables de entorno (en .env o en el panel de Render) sin tocar el código. Si
no se definen, se usan los valores de aquí. Un valor no válido detiene el
arranque con un mensaje claro, para no desplegar con un límite equivocado.
"""
import os


def positive_int_from_env(name: str, default: int) -> int:
    """Lee un número entero positivo de una variable de entorno."""
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} debe ser un número entero, no {value!r}") from None
    if number < 1:
        raise ValueError(f"{name} debe ser mayor que 0")
    return number


# Mensajes permitidos.
MESSAGES_PER_MINUTE_PER_IP = positive_int_from_env("CHAT_MESSAGES_PER_MINUTE_PER_IP", 5)
MESSAGES_PER_DAY_PER_IP = positive_int_from_env("CHAT_MESSAGES_PER_DAY_PER_IP", 30)
# Tope global: protege el cupo de los proveedores aunque lleguen muchas IP.
MESSAGES_PER_DAY_TOTAL = positive_int_from_env("CHAT_MESSAGES_PER_DAY_TOTAL", 300)

# Longitudes máximas, en caracteres.
MAX_MESSAGE_LENGTH = positive_int_from_env("CHAT_MAX_MESSAGE_LENGTH", 500)
MAX_ANSWER_LENGTH = 1200
# Mensajes anteriores que puede enviar el navegador (3 preguntas y 3 respuestas).
MAX_HISTORY_MESSAGES = 6
