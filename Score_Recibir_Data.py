import socket
import json
import re
from pathlib import Path

# =========================
# CONFIGURACIÓN UDP (PC2)
# =========================
UDP_IP = "0.0.0.0"    # Escucha en todas las interfaces
UDP_PORT = 5005       # Debe coincidir con el emisor de PC1

# Carpeta base donde estarán los TXT para OBS
BASE_DIR = Path(r"C:\obs\scoreboard")

FILE_HOME   = BASE_DIR / "home.txt"           # Marcador local
FILE_VISIT  = BASE_DIR / "visit.txt"          # Marcador visita
FILE_TIMER  = BASE_DIR / "timer.txt"          # Reloj
FILE_SET    = BASE_DIR / "set.txt"            # Set actual (número)
FILE_LINE   = BASE_DIR / "line.txt"           # Línea completa (opcional)
FILE_JSON   = BASE_DIR / "raw.json"           # Último JSON recibido (debug)

FILE_LOCAL_SET_WIN = BASE_DIR / "local_set_win.txt"   # Trigger set ganado local
FILE_VISIT_SET_WIN = BASE_DIR / "visit_set_win.txt"   # Trigger set ganado visita

# Crear carpeta si no existe
BASE_DIR.mkdir(parents=True, exist_ok=True)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"[PC2] Escuchando UDP en puerto {UDP_PORT}...")
print(f"[PC2] Archivos para OBS en: {BASE_DIR}\n")

# Valores anteriores para evitar escrituras innecesarias
last_home      = None
last_visit     = None
last_timer     = None
last_set_num   = None   # número (1,2,3...)
last_set_raw   = None   # texto original ("2nd", "3rd"...)

# Flags para controlar que solo se dispare UNA vez por set
local_set_win_fired = False
visit_set_win_fired = False

# Inicializar triggers en "0"
FILE_LOCAL_SET_WIN.write_text("0", encoding="utf-8")
FILE_VISIT_SET_WIN.write_text("0", encoding="utf-8")

while True:
    data, addr = sock.recvfrom(4096)

    try:
        payload = json.loads(data.decode("utf-8", errors="ignore"))

        # ----------- Extraer valores del JSON -----------
        home = str(
            payload.get("home", payload.get("home_score", "0"))
        ).zfill(2)

        visit = str(
            payload.get("guest", payload.get("visitor", payload.get("visitor_score", "0")))
        ).zfill(2)

        timer = payload.get("clock", payload.get("time", "--:--"))

        # raw_set puede venir como "2", "2nd", "3rd", etc.
        raw_set = (
            payload.get("set")
            or payload.get("period")
            or payload.get("quarter")
            or "1"  # por defecto asumimos set 1 si no viene nada
        )
        raw_set_str = str(raw_set)

        # Intentar sacar solo el número del set (ej. "2nd" -> 2)
        m = re.search(r"\d+", raw_set_str)
        if m:
            set_num = int(m.group())
        else:
            set_num = 1

        # ----------- Actualizar solo lo que cambia -----------
        changed = []  # para log

        if home != last_home:
            FILE_HOME.write_text(home, encoding="utf-8")
            last_home = home
            changed.append("home")

        if visit != last_visit:
            FILE_VISIT.write_text(visit, encoding="utf-8")
            last_visit = visit
            changed.append("visit")

        if timer != last_timer:
            FILE_TIMER.write_text(timer, encoding="utf-8")
            last_timer = timer
            changed.append("timer")

        # Si cambia el set (numérico o texto) → actualizar y resetear triggers
        if set_num != last_set_num or raw_set_str != last_set_raw:
            last_set_num = set_num
            last_set_raw = raw_set_str

            # En el TXT dejamos solo el número de set (más limpio para OBS)
            FILE_SET.write_text(str(set_num), encoding="utf-8")

            # Resetear triggers a "0" porque ya estamos en OTRO set
            local_set_win_fired = False
            visit_set_win_fired = False
            FILE_LOCAL_SET_WIN.write_text("0", encoding="utf-8")
            FILE_VISIT_SET_WIN.write_text("0", encoding="utf-8")

            changed.append(f"set (nuevo set: {set_num} / raw: {raw_set_str})")

        # ----------- Lógica de voleibol: victoria de set -----------

        # Convertir marcadores a int para cuentas
        try:
            home_score_int = int(home)
            visit_score_int = int(visit)
        except ValueError:
            home_score_int = 0
            visit_score_int = 0

        # Sets 1–4 a 25 puntos, set 5 a 15 puntos
        if set_num < 5:
            puntos_minimos = 25
        else:
            puntos_minimos = 15

        # ¿Local gana el set?
        local_gana_set = (
            home_score_int >= puntos_minimos and
            (home_score_int - visit_score_int) >= 2
        )

        # ¿Visita gana el set?
        visit_gana_set = (
            visit_score_int >= puntos_minimos and
            (visit_score_int - home_score_int) >= 2
        )

        # Trigger set ganado LOCAL
        if local_gana_set and not local_set_win_fired:
            win_text = f"SET {set_num} WIN"
            FILE_LOCAL_SET_WIN.write_text(win_text, encoding="utf-8")
            local_set_win_fired = True
            changed.append(f"local_set_win ({win_text})")

        # Trigger set ganado VISITA
        if visit_gana_set and not visit_set_win_fired:
            win_text = f"SET {set_num} WIN"
            FILE_VISIT_SET_WIN.write_text(win_text, encoding="utf-8")
            visit_set_win_fired = True
            changed.append(f"visit_set_win ({win_text})")

        # ----------- Línea completa y JSON (solo si algo cambió) -----------
        if changed:
            line_text = f"HOME {home} - {visit} VISIT  |  T: {timer}  |  SET: {set_num}"
            FILE_LINE.write_text(line_text, encoding="utf-8")
            FILE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[PC2] {addr} → {line_text}  (cambios: {', '.join(changed)})")

    except Exception as e:
        print(f"[PC2] Error procesando paquete: {e}")