"""
Punto de entrada único para Railway: levanta los bots configurados en
segundo plano y el dashboard de Streamlit en primer plano (bindeado a
$PORT), para que Railway exponga el panel en una URL pública mientras
los bots siguen corriendo en el mismo servicio/contenedor -- comparten
sistema de archivos, así que el dashboard puede leer los .json/.log de
estado que escriben los bots.

Qué bots levantar se controla con la variable de entorno RAILWAY_BOTS
(lista separada por comas de scripts). Por defecto levanta los tres.
Ejemplo para correr solo dos: RAILWAY_BOTS=swing_bot.py,binance_grid_bot.py
"""
import os
import subprocess
import sys
import threading
import time

DEFAULT_BOTS = "bot.py,swing_bot.py,binance_grid_bot.py"
RESTART_DELAY_SECONDS = 30


def run_bot_forever(script: str) -> None:
    while True:
        print(f"[run_all] iniciando {script}", flush=True)
        result = subprocess.run([sys.executable, script])
        print(
            f"[run_all] {script} termino (codigo {result.returncode}); "
            f"reintentando en {RESTART_DELAY_SECONDS}s",
            flush=True,
        )
        time.sleep(RESTART_DELAY_SECONDS)


def main() -> None:
    bots = [b.strip() for b in os.getenv("RAILWAY_BOTS", DEFAULT_BOTS).split(",") if b.strip()]
    for script in bots:
        threading.Thread(target=run_bot_forever, args=(script,), daemon=True).start()

    port = os.getenv("PORT", "8501")
    streamlit_args = [
        "streamlit", "run", "dashboard.py",
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
    ]
    print(f"[run_all] bots: {bots}", flush=True)
    print(f"[run_all] iniciando dashboard en el puerto {port}", flush=True)
    os.execvp("streamlit", streamlit_args)


if __name__ == "__main__":
    main()
