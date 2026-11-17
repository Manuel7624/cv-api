"""Comprueba, contra la web publicada, si alguien podría saltarse el límite de
mensajes por IP inventándose la IP en las cabeceras.

Uso (después de desplegar, desde tu ordenador):
    python scripts/check_client_ip.py https://tu-web.onrender.com

Envía 6 mensajes cortos al chat (el límite es de 5 por minuto y por IP), cada uno
con una IP inventada distinta en CF-Connecting-IP y X-Forwarded-For:
- Si el 6.º da 429, el servidor no se cree las IPs inventadas: correcto.
- Si los 6 pasan, se pueden falsificar y hay que cambiar cómo se lee la IP.
Gasta 6 de tus 30 mensajes diarios (y 6 del tope global). Solo usa la librería
estándar de Python.
"""
import json
import sys
import time
import urllib.error
import urllib.request

MESSAGES = 6


def send(base_url: str, number: int) -> int:
    fake_ip = f"203.0.113.{number + 10}"  # rango reservado para documentación
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat",
        data=json.dumps({"message": "hola"}).encode(),
        headers={
            "Content-Type": "application/json",
            "CF-Connecting-IP": fake_ip,
            "X-Forwarded-For": fake_ip,
            "True-Client-IP": fake_ip,
            "X-Real-IP": fake_ip,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        print("Uso: python scripts/check_client_ip.py https://tu-web.onrender.com")
        sys.exit(1)
    base_url = sys.argv[1]
    codes = []
    for number in range(MESSAGES):
        code = send(base_url, number)
        codes.append(code)
        print(f"Mensaje {number + 1} con IP inventada 203.0.113.{number + 10}: {code}")
        time.sleep(0.5)

    print()
    if codes[-1] == 429 and all(code == 200 for code in codes[:-1]):
        print("CORRECTO: el 6.º mensaje se ha bloqueado aunque cada uno decía venir de otra IP.")
        print("El servidor usa tu IP real, no la que se envía en las cabeceras.")
        print("Comprobación extra: en el minuto siguiente, envía una pregunta desde el móvil")
        print("con datos móviles (no con el wifi de casa). Si responde, cada visitante tiene su")
        print("propio límite. Si también da 429, todos comparten el mismo límite: avísame.")
    elif all(code == 200 for code in codes):
        print("PROBLEMA: los 6 mensajes han pasado. Las IPs de las cabeceras se pueden")
        print("falsificar y alguien podría saltarse el límite por IP (el tope global de")
        print("mensajes al día sigue protegiendo el gasto). Hay que cambiar cómo se lee la IP.")
    else:
        print("Resultado no esperado. Puede que ya hubieras enviado mensajes en el último")
        print(f"minuto o que el límite no esté en 5 por minuto. Códigos: {codes}")
        print("Espera un minuto y vuelve a probar.")


if __name__ == "__main__":
    main()
