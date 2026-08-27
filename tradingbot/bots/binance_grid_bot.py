"""
Bot de Grid Trading en vivo sobre Binance FUTURES (BTC, ETH, SOL).

Por defecto opera contra el TESTNET de Binance Futures (dinero simulado,
ver BINANCE_TESTNET en binance_config.py). Revisa el precio de cada
símbolo periódicamente y, cuando cruza un nivel de la grilla, envía una
orden MARKET (compra al bajar a un nivel libre, vende -- reduceOnly -- al
subir al nivel siguiente de una posición abierta).

IMPORTANTE:
- Con BINANCE_TESTNET=true (default) NO arriesga dinero real.
- Usa apalancamiento (ver GRID_CONFIG). El apalancamiento amplifica tanto
  ganancias como pérdidas y acerca el precio de liquidación -- no cambiar
  a testnet=false ni subir el leverage sin haber validado extensamente.
- Si el precio sale del rango de la grilla más allá de `invalidate_pct`,
  el bot deja de operar ese símbolo (no persigue el precio ni reabre la
  grilla solo). Para reiniciarla hay que borrar su entrada en el archivo
  de estado (GRID_STATE_FILE) y reiniciar el bot.
- Este código es una base educativa, no un consejo de inversión ni una
  garantía de resultados.

Uso:
    python -m tradingbot.bots.binance_grid_bot
"""
import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, FUTURE_ORDER_TYPE_MARKET

from tradingbot.binance_config import (
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
    GRID_CONFIG, GRID_STATE_FILE, GRID_LOG_FILE, GRID_CHECK_INTERVAL_SECONDS,
    DATA_DIR, with_timeout,
)
from tradingbot.strategies.grid_strategy import build_levels, find_crossings

os.makedirs(DATA_DIR, exist_ok=True)

logger = logging.getLogger("binance_grid_bot")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(GRID_LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_client() -> Client:
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise RuntimeError(
            "Faltan las credenciales de Binance. Crea un archivo .env con "
            "BINANCE_API_KEY y BINANCE_API_SECRET (ver binance_config.py)."
        )
    # ping=False: por defecto python-binance verifica conectividad contra la
    # API de Spot al crear el cliente, pero este bot solo usa Futures (URL y
    # claves distintas) -- ese ping de Spot puede fallar (incluido el
    # bloqueo geografico "restricted location" de Binance) sin que afecte
    # en nada a las llamadas futures_* que realmente usa el bot.
    return Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=BINANCE_TESTNET, ping=False)


def load_symbol_filters(client: Client) -> dict:
    """precision de cantidad y cantidad minima por simbolo, para redondear
    las ordenes segun las reglas de Binance (LOT_SIZE)."""
    info = with_timeout(client.futures_exchange_info)
    filters = {}
    for s in info["symbols"]:
        if s["symbol"] in GRID_CONFIG:
            lot = next(f for f in s["filters"] if f["filterType"] == "LOT_SIZE")
            filters[s["symbol"]] = (s["quantityPrecision"], float(lot["minQty"]))
    return filters


def load_state() -> dict:
    if os.path.exists(GRID_STATE_FILE):
        with open(GRID_STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(GRID_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_price(client: Client, symbol: str) -> float:
    return float(with_timeout(client.futures_symbol_ticker, symbol=symbol)["price"])


def init_symbol_state(client: Client, symbol: str, cfg: dict) -> dict:
    """Arma una grilla nueva centrada en el precio actual del simbolo."""
    price = get_price(client, symbol)
    lower = price * (1 - cfg["range_pct"])
    upper = price * (1 + cfg["range_pct"])
    levels = build_levels(lower, upper, cfg["grid_count"])

    with_timeout(client.futures_change_leverage, symbol=symbol, leverage=cfg["leverage"])

    return {
        "levels": levels,
        "lower": lower,
        "upper": upper,
        "positions": {},         # nivel (str) -> {"qty":, "entry_price":}
        "previous_price": price,
        "invalidated": False,
    }


def process_symbol(client: Client, symbol: str, cfg: dict, state: dict, filters: dict):
    symbol_state = state.get(symbol)
    if symbol_state is None:
        symbol_state = init_symbol_state(client, symbol, cfg)
        state[symbol] = symbol_state
        logger.info(f"[{symbol}] Grilla inicializada: rango ${symbol_state['lower']:,.2f} - "
                    f"${symbol_state['upper']:,.2f} ({cfg['grid_count']} niveles, leverage {cfg['leverage']}x)")

    price = get_price(client, symbol)

    if symbol_state.get("invalidated"):
        logger.info(f"[{symbol}] Grilla invalidada, no se opera (precio actual: ${price:,.2f}). "
                    f"Para reiniciarla, borra su entrada en {GRID_STATE_FILE} y reinicia el bot.")
        return

    lower, upper = symbol_state["lower"], symbol_state["upper"]
    invalidate_low = lower * (1 - cfg["invalidate_pct"])
    invalidate_high = upper * (1 + cfg["invalidate_pct"])

    if price < invalidate_low or price > invalidate_high:
        symbol_state["invalidated"] = True
        logger.warning(f"[{symbol}] Precio (${price:,.2f}) salio del rango invalidado "
                        f"[${invalidate_low:,.2f}, ${invalidate_high:,.2f}]. Se detiene la operatoria "
                        f"de este simbolo -- las posiciones abiertas quedan como estan, revisalas manualmente.")
        return

    levels = symbol_state["levels"]
    positions = symbol_state["positions"]
    precision, min_qty = filters[symbol]

    crossed, direction = find_crossings(levels, symbol_state["previous_price"], price)

    for i in crossed:
        if direction == "down":
            if i < len(levels) - 1 and str(i) not in positions:
                qty = round((cfg["capital_per_grid_usd"] * cfg["leverage"]) / levels[i], precision)
                if qty < min_qty:
                    logger.warning(f"[{symbol}] Nivel {i} (${levels[i]:,.2f}): cantidad calculada ({qty}) "
                                    f"menor al minimo permitido ({min_qty}). Se omite la compra.")
                    continue
                with_timeout(client.futures_create_order, symbol=symbol, side=SIDE_BUY,
                             type=FUTURE_ORDER_TYPE_MARKET, quantity=qty)
                positions[str(i)] = {"qty": qty, "entry_price": levels[i]}
                logger.info(f"[{symbol}] BUY nivel {i}: {qty} @ ~${levels[i]:,.2f}")
        else:
            below = i - 1
            if below >= 0 and str(below) in positions:
                pos = positions.pop(str(below))
                with_timeout(client.futures_create_order, symbol=symbol, side=SIDE_SELL,
                             type=FUTURE_ORDER_TYPE_MARKET, quantity=pos["qty"], reduceOnly=True)
                logger.info(f"[{symbol}] SELL nivel {below}: {pos['qty']} @ ~${levels[i]:,.2f} "
                            f"(compra: ${pos['entry_price']:,.2f})")

    symbol_state["previous_price"] = price


def run_once(client: Client, state: dict, filters: dict):
    logger.info(f"\n[{datetime.now()}] Revisando grilla de {', '.join(GRID_CONFIG)}...")
    for symbol, cfg in GRID_CONFIG.items():
        try:
            process_symbol(client, symbol, cfg, state, filters)
        except Exception as e:
            logger.error(f"[{symbol}] [ERROR] {e}")
    save_state(state)


def main():
    client = get_client()
    state = load_state()
    filters = load_symbol_filters(client)

    modo = "TESTNET (fondos simulados)" if BINANCE_TESTNET else "*** CUENTA REAL ***"
    logger.info(f"Conectado a Binance Futures -- modo: {modo}")
    if not BINANCE_TESTNET:
        logger.warning("BINANCE_TESTNET=false: este bot va a operar con dinero REAL y apalancamiento. "
                        "Confirma que validaste la estrategia extensamente antes de seguir.")

    balances = with_timeout(client.futures_account_balance)
    usdt = next((b for b in balances if b["asset"] == "USDT"), None)
    if usdt:
        logger.info(f"Balance USDT disponible: ${float(usdt['availableBalance']):,.2f}")

    logger.info(f"Simbolos: {', '.join(GRID_CONFIG)}")
    logger.info(f"Registrando actividad en {GRID_LOG_FILE}")
    logger.info(f"Revisando cada {GRID_CHECK_INTERVAL_SECONDS} segundos. Ctrl+C para detener.\n")

    while True:
        try:
            run_once(client, state, filters)
        except Exception as e:
            logger.error(f"[ERROR GENERAL] {e}", exc_info=True)
        time.sleep(GRID_CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
