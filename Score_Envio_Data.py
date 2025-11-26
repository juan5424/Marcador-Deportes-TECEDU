import socket
import json
import time
from consoles.sports import Football  

# =========================
# CONFIGURACIÓN PC1
# =========================

# Puerto serie donde está conectada la Daktronics (ajusta según la pc)
SERIAL_PORT = "COM4"          # EJEMPLO: "COM3", "COM4", etc.

# IP y puerto de la PC2 (transmisión)
UDP_IP = "10.13.14.220"       # IP de la PC2
UDP_PORT = 5005

# Crear socket UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 
last_home  = None
last_visit = None
last_clock = None
last_set   = None


def on_update(game_state: dict):
    """
    Callback que la clase Football llamará cada vez que reciba un nuevo estado
    del marcador desde la Daktronics.
    """
    global last_home, last_visit, last_clock, last_set

    try:
        # Los nombres de claves pueden variar según la librería, aquí usamos
        # los que has mencionado: home_score, visitor_score, clock, period.
        home = str(game_state.get("home_score", "0")).zfill(2)
        visit = str(game_state.get("visitor_score", "0")).zfill(2)
        clock = game_state.get("clock", "--:--")

        # Set / periodo / cuarto
        set_value = (
            game_state.get("set")
            or game_state.get("period")
            or game_state.get("quarter")
            or "--"
        )
        set_value = str(set_value)

    except Exception as e:
        print(f"[PC1] Error leyendo game_state: {e}")
        return

    # ¿Cambió algo?
    if (
        home == last_home
        and visit == last_visit
        and clock == last_clock
        and set_value == last_set
    ):
        # Nada nuevo, no mandamos
        return

    # Actualizar estado previo
    last_home  = home
    last_visit = visit
    last_clock = clock
    last_set   = set_value

    # Log en consola
    line = f"HOME {home} - {visit} VISIT  |  T: {clock}  |  SET: {set_value}"
    print("[PC1]", line)

    # Armar JSON para PC2
    payload = {
        "home": home,
        "guest": visit,   # usamos 'guest' porque así lo espera el receptor
        "clock": clock,
        "set": set_value,
    }

    try:
        msg = json.dumps(payload).encode("utf-8")
        sock.sendto(msg, (UDP_IP, UDP_PORT))
        # print("[PC1] UDP enviado:", payload)
    except Exception as e:
        print(f"[PC1] Error enviando UDP: {e}")


def main():
    print(f"[PC1] Iniciando lectura de Daktronics en {SERIAL_PORT}...")
    print(f"[PC1] Enviando datos a {UDP_IP}:{UDP_PORT} (UDP).")

    # Crear objeto Football de la librería de consola Daktronics
    football = Football(SERIAL_PORT)
    football.on_update = on_update  # Registramos el callback

    try:
        # Algunas implementaciones tienen .start(), otras ya inician sola la lectura
        start_method = getattr(football, "start", None)
        if callable(start_method):
            start_method()

        print("[PC1] Leyendo datos... Ctrl+C para salir.\n")
        while True:
            # El objeto Football se encarga del puerto serial;
            # aquí solo mantenemos el programa vivo.
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[PC1] Saliendo por Ctrl+C...")

    finally:
        # Cerrar Football si tiene método de cierre
        close_method = getattr(football, "close", None)
        if callable(close_method):
            try:
                close_method()
            except Exception:
                pass

        sock.close()
        print("[PC1] Socket UDP cerrado. Programa terminado.")


if __name__ == "__main__":
    main()
