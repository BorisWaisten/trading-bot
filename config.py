"""
Configuración del bot. Las credenciales se leen de variables de entorno
(nunca las escribas directamente en el código).

Cómo obtener tus claves de Alpaca (paper trading, gratis):
1. Creá una cuenta en https://alpaca.markets/
2. Andá a la sección "Paper Trading" del dashboard
3. Generá tu API Key y Secret Key
4. Creá un archivo .env en esta carpeta (ver .env.example) con:
     ALPACA_API_KEY=tu_key
     ALPACA_SECRET_KEY=tu_secret
"""
import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

# URL de paper trading (dinero simulado). Para ir a real sería
# "https://api.alpaca.markets", pero NO lo cambies hasta haber
# validado la estrategia con paper trading durante un buen tiempo.
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

# --- Parámetros de la estrategia ---
SYMBOL = "AAPL"          # Ticker a operar
SMA_SHORT = 20            # Media móvil corta (días)
SMA_LONG = 50             # Media móvil larga (días)
CHECK_INTERVAL_SECONDS = 60 * 60  # Cada cuánto revisa señales (1 hora)

# --- Configuración de la estrategia de RANGO (take-profit + reingreso por pullback) ---
# Para YPF y VIST, separado del resto. Ver swing_bot.py
SWING_SYMBOLS = ["YPF", "VIST"]
SWING_PROFIT_TARGET_PCT = 0.10   # vender al subir 10% desde la compra
SWING_PULLBACK_PCT = 0.05        # comprar al caer 5% desde el pico (mientras se está afuera)
SWING_STOP_LOSS_PCT = 0.08       # vender de emergencia si cae 8% desde la compra
SWING_STATE_FILE = "swing_state.json"  # dónde se guarda el seguimiento del "pico" entre corridas
# En vez de una cantidad fija de acciones, el tamaño de cada operación se
# calcula según cuánto capital total tenés y cuánto estás dispuesto a
# arriesgar en esa operación puntual (regla clásica: 1-2% por operación).
RISK_PER_TRADE_PCT = 0.01      # Arriesgar como máximo 1% del capital total por operación
STOP_LOSS_PCT = 0.10            # Cierra posición si cae 10% desde la compra (antes 5%, muy ajustado)
TAKE_PROFIT_PCT = 0.20          # Cierra posición (asegura ganancia) si sube 20% desde la compra
MAX_POSITION_VALUE_USD = 1000  # Tope adicional de exposición en este símbolo, más allá del % de riesgo
