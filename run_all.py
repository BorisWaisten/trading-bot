"""
Punto de entrada único para Railway: levanta los bots configurados en
segundo plano y el dashboard de Streamlit en primer plano (bindeado a
$PORT), para que Railway exponga el panel en una URL pública mientras
los bots siguen corriendo en el mismo servicio/contenedor -- comparten
sistema de archivos, así que el dashboard puede leer los .json/.log de
estado que escriben los bots.

Qué bots levantar se controla con la variable de entorno RAILWAY_BOTS
(lista separada por comas de módulos). Por defecto levanta los tres.
Ejemplo para correr solo dos:
    RAILWAY_BOTS=tradingbot.bots.swing_bot,tradingbot.bots.binance_grid_bot

NOTA: si ya tenías RAILWAY_BOTS configurada en Railway con los nombres
viejos (ej. "swing_bot.py,binance_grid_bot.py"), hay que actualizarla a
los nombres de módulo nuevos de arriba -- el proyecto se reorganizó en
carpetas (ver tradingbot/).
"""
import os
import subprocess
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BOTS = "tradingbot.bots.bot,tradingbot.bots.swing_bot,tradingbot.bots.binance_grid_bot"
RESTART_DELAY_SECONDS = 30


def run_bot_forever(module: str) -> None:
    while True:
        print(f"[run_all] iniciando {module}", flush=True)
        result = subprocess.run([sys.executable, "-m", module], cwd=PROJECT_ROOT)
        print(
            f"[run_all] {module} termino (codigo {result.returncode}); "
            f"reintentando en {RESTART_DELAY_SECONDS}s",
            flush=True,
        )
        time.sleep(RESTART_DELAY_SECONDS)


def main() -> None:
    bots = [b.strip() for b in os.getenv("RAILWAY_BOTS", DEFAULT_BOTS).split(",") if b.strip()]
    for module in bots:
        threading.Thread(target=run_bot_forever, args=(module,), daemon=True).start()

    port = os.getenv("PORT", "8501")
    dashboard_path = os.path.join(PROJECT_ROOT, "tradingbot", "dashboard.py")
    streamlit_args = [
        "streamlit", "run", dashboard_path,
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
    ]
    print(f"[run_all] bots: {bots}", flush=True)
    print(f"[run_all] iniciando dashboard en el puerto {port}", flush=True)
    os.chdir(PROJECT_ROOT)
    os.execvp("streamlit", streamlit_args)


if __name__ == "__main__":
    main()
