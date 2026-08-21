"""
Configuración del bot de Grid Trading sobre Binance FUTURES (BTC, ETH, SOL).

Cómo obtener tus claves de Binance Futures TESTNET (fondos simulados, gratis):
1. Entrá a https://testnet.binancefuture.com/ e iniciá sesión con tu cuenta
   de GitHub (no hace falta tu cuenta real de Binance)
2. Generá tu API Key y Secret Key ahí (son distintas a las de tu cuenta real)
3. Creá un archivo .env en esta carpeta (ver .env.example) con:
     BINANCE_API_KEY=tu_key_de_testnet
     BINANCE_API_SECRET=tu_secret_de_testnet
     BINANCE_TESTNET=true

⚠️ NO pongas ahí las API keys de tu cuenta REAL hasta haber validado la
estrategia en testnet durante varias semanas y entender bien el riesgo de
operar con apalancamiento (ver README.md).
"""
import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", ".")

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# true = Binance Futures Testnet (dinero simulado). NO pasar a false hasta
# validar extensamente en testnet.
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

GRID_STATE_FILE = os.path.join(DATA_DIR, "binance_grid_state.json")
GRID_LOG_FILE = os.path.join(DATA_DIR, "binance_grid_bot.log")
GRID_CHECK_INTERVAL_SECONDS = 30  # cada cuánto revisa el precio (la grilla reacciona más rápido que el SMA diario)

FEE_PCT = 0.0004  # comisión aproximada de taker en Binance Futures (0.04%), se usa solo en el backtest

# --- Grilla por símbolo ---
# range_pct:            ancho de la grilla, en % hacia arriba y hacia abajo del precio
#                        de referencia tomado al iniciar el bot (o al reiniciar la grilla).
#                        No se hardcodean precios absolutos porque quedan viejos: la grilla
#                        se arma dinámicamente alrededor del precio de mercado del momento.
# grid_count:            cantidad de niveles dentro del rango. Más niveles = operaciones
#                        más chicas y frecuentes; menos niveles = operaciones más grandes
#                        y espaciadas.
# leverage:              apalancamiento en Binance Futures. Empezar BAJO (2-3x): a mayor
#                        apalancamiento, más cerca queda el precio de liquidación de tu
#                        posición y más rápido se pierde el margen ante un movimiento en
#                        contra. Como regla aproximada (sin contar comisiones ni margen de
#                        mantenimiento), con leverage=N un movimiento en contra de ~1/N
#                        ya te acerca a la liquidación de esa posición.
# capital_per_grid_usd:  margen (USD) asignado a CADA orden individual de la grilla, no al
#                        total. Si hay grid_count/2 posiciones abiertas a la vez en el peor
#                        caso, el margen total comprometido puede llegar a esa cantidad.
# invalidate_pct:        si el precio sale del rango [lower, upper] por más de este % extra,
#                        el bot deja de operar ese símbolo y solo avisa (no persigue el
#                        precio fuera de rango ni reabre la grilla solo).
GRID_CONFIG = {
    "BTCUSDT": {
        "range_pct": 0.12,
        "grid_count": 10,
        "leverage": 2,
        "capital_per_grid_usd": 50,
        "invalidate_pct": 0.05,
    },
    "ETHUSDT": {
        "range_pct": 0.15,
        "grid_count": 10,
        "leverage": 2,
        "capital_per_grid_usd": 50,
        "invalidate_pct": 0.05,
    },
    "SOLUSDT": {
        "range_pct": 0.20,
        "grid_count": 10,
        "leverage": 2,
        "capital_per_grid_usd": 30,
        "invalidate_pct": 0.05,
    },
}
