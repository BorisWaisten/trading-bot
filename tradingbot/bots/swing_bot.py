"""
Bot de PAPER TRADING para la estrategia de RANGO (take-profit + reingreso
por pullback desde el pico) sobre YPF y VIST, vía Alpaca.

Lógica por símbolo, de forma independiente:
1. AFUERA del mercado: se trackea el precio más alto ("pico") desde que
   se quedó afuera. Cuando el precio cae SWING_PULLBACK_PCT desde ese
   pico, COMPRA (con una porción del capital total de la cuenta) — salvo
   que el semáforo macro (petróleo + CCL) esté en ROJO, en cuyo caso
   bloquea la compra.
2. ADENTRO (con posición): si el precio cae SWING_STOP_LOSS_PCT desde la
   compra, VENDE (stop-loss). Si sube SWING_PROFIT_TARGET_PCT, VENDE
   (take-profit).
3. Al vender, se reinicia el trackeo del pico desde ese momento.

Robustez:
- Todo se registra en trading_bot.log (además de la consola).
- Antes de cada revisión, chequea si el mercado de EE.UU. está abierto;
  si está cerrado, espera sin intentar operar.
- Cualquier error en un símbolo o en un ciclo se loguea pero NO tumba el
  proceso — el bot sigue corriendo en el próximo ciclo.

El seguimiento del "pico" se guarda en un archivo local (SWING_STATE_FILE)
para no perderlo si el bot se reinicia.

IMPORTANTE: Corre en cuenta de PAPER TRADING (dinero simulado) por
defecto. No es consejo de inversión.

Uso:
    python -m tradingbot.bots.swing_bot
"""
import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import alpaca_trade_api as tradeapi

from tradingbot.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, ALPACA_LIVE_TRADING,
    SWING_SYMBOLS, SWING_PROFIT_TARGET_PCT, SWING_PULLBACK_PCT,
    SWING_STOP_LOSS_PCT, SWING_STATE_FILE, CHECK_INTERVAL_SECONDS,
    DATA_DIR,
)
from tradingbot.macro_filter import get_market_signal

# --- Logging: a archivo (con rotación, para no llenar el disco) y a consola ---
os.makedirs(DATA_DIR, exist_ok=True)

logger = logging.getLogger("swing_bot")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(os.path.join(DATA_DIR, "trading_bot.log"), maxBytes=5_000_000, backupCount=3, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_api():
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise RuntimeError(
            "Faltan las credenciales de Alpaca. Creá un archivo .env "
            "con ALPACA_API_KEY y ALPACA_SECRET_KEY (ver config.py)."
        )
    return tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")


def load_state() -> dict:
    if os.path.exists(SWING_STATE_FILE):
        with open(SWING_STATE_FILE, "r") as f:
            return json.load(f)
    return {symbol: {"peak_since_flat": None} for symbol in SWING_SYMBOLS}


def save_state(state: dict):
    with open(SWING_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_latest_price(api, symbol: str) -> float:
    trade = api.get_latest_trade(symbol)
    return float(trade.price)


def get_position(api, symbol: str):
    """Devuelve (qty, avg_entry_price) o (0, None) si no hay posición."""
    try:
        position = api.get_position(symbol)
        return float(position.qty), float(position.avg_entry_price)
    except Exception:
        return 0.0, None


def is_market_open(api) -> bool:
    try:
        clock = api.get_clock()
        return bool(clock.is_open)
    except Exception as e:
        logger.warning(f"No se pudo consultar el horario de mercado ({e}). Se asume cerrado por precaución.")
        return False


def process_symbol(api, symbol: str, state: dict, capital_per_symbol: float, macro_signal: dict):
    price = get_latest_price(api, symbol)
    qty, entry_price = get_position(api, symbol)
    symbol_state = state.setdefault(symbol, {"peak_since_flat": None})

    logger.info(f"\n[{symbol}] Precio actual: ${price:.2f} | Posición: {qty} acciones")

    if qty == 0:
        # Afuera del mercado: trackear el pico y esperar la caída del PULLBACK_PCT
        peak = symbol_state.get("peak_since_flat")
        if peak is None or price > peak:
            peak = price
            symbol_state["peak_since_flat"] = peak
            logger.info(f"  Nuevo pico registrado: ${peak:.2f}")

        trigger_price = peak * (1 - SWING_PULLBACK_PCT)
        if price <= trigger_price:
            if macro_signal["signal"] == "RED":
                logger.info(f"  Señal técnica de compra detectada, pero BLOQUEADA por semáforo macro en ROJO "
                      f"(petróleo: {macro_signal['oil']['detail']} | CCL: {macro_signal['ccl']['detail']})")
                return
            if macro_signal["signal"] == "YELLOW":
                logger.info(f"  [Aviso] Semáforo macro en AMARILLO, se compra igual pero con precaución "
                      f"(petróleo: {macro_signal['oil']['detail']} | CCL: {macro_signal['ccl']['detail']})")

            qty_to_buy = int(capital_per_symbol // price)
            if qty_to_buy > 0:
                api.submit_order(symbol=symbol, qty=qty_to_buy, side="buy",
                                  type="market", time_in_force="day")
                logger.info(f"  -> COMPRA enviada: {qty_to_buy} acciones (cayó {SWING_PULLBACK_PCT:.0%} desde el pico de ${peak:.2f})")
                symbol_state["peak_since_flat"] = None
            else:
                logger.info(f"  Señal de compra, pero el capital asignado (${capital_per_symbol:.2f}) no alcanza para 1 acción.")
        else:
            logger.info(f"  Esperando... compra si baja de ${trigger_price:.2f} (pico: ${peak:.2f})")

    else:
        # Con posición: chequear stop-loss y take-profit
        change_pct = (price - entry_price) / entry_price
        logger.info(f"  Precio de entrada: ${entry_price:.2f}  |  Variación: {change_pct:+.2%}")

        if change_pct <= -SWING_STOP_LOSS_PCT:
            api.close_position(symbol)
            logger.info(f"  -> VENTA (stop-loss) enviada: cayó {change_pct:.2%} desde la compra")
            symbol_state["peak_since_flat"] = price
        elif change_pct >= SWING_PROFIT_TARGET_PCT:
            api.close_position(symbol)
            logger.info(f"  -> VENTA (take-profit) enviada: subió {change_pct:.2%} desde la compra")
            symbol_state["peak_since_flat"] = price
        else:
            logger.info(f"  Manteniendo posición (objetivo: +{SWING_PROFIT_TARGET_PCT:.0%}, stop: -{SWING_STOP_LOSS_PCT:.0%})")


def run_once(api, state: dict):
    if not is_market_open(api):
        logger.info(f"\n[{datetime.now()}] Mercado cerrado. No se opera en este ciclo.")
        return

    account = api.get_account()
    capital_per_symbol = float(account.equity) / len(SWING_SYMBOLS)

    logger.info(f"\n[{datetime.now()}] Revisando panel de rango (YPF + VIST)...")
    logger.info(f"Capital total de la cuenta: ${float(account.equity):,.2f} | Por símbolo: ${capital_per_symbol:,.2f}")

    macro_signal = get_market_signal()
    logger.info(f"\nSemáforo macro: {macro_signal['signal']}")
    logger.info(f"  Petróleo: {macro_signal['oil']['signal']} — {macro_signal['oil']['detail']}")
    logger.info(f"  CCL:      {macro_signal['ccl']['signal']} — {macro_signal['ccl']['detail']}")

    for symbol in SWING_SYMBOLS:
        try:
            process_symbol(api, symbol, state, capital_per_symbol, macro_signal)
        except Exception as e:
            logger.info(f"  [ERROR] {symbol}: {e}")

    save_state(state)


def main():
    api = get_api()
    state = load_state()

    account = api.get_account()
    modo = "*** CUENTA REAL ***" if ALPACA_LIVE_TRADING else "PAPER TRADING (simulado)"
    logger.info(f"Conectado a Alpaca -- modo: {modo}")
    if ALPACA_LIVE_TRADING:
        logger.warning("ALPACA_LIVE_TRADING=true: este bot va a operar con DINERO REAL. "
                        "Confirma que validaste la estrategia extensamente antes de seguir "
                        "(ver CHECKLIST_PRODUCCION.md).")
    logger.info(f"Balance de la cuenta: ${float(account.cash):,.2f}")
    logger.info(f"Símbolos: {', '.join(SWING_SYMBOLS)}")
    logger.info(f"Registrando actividad en trading_bot.log")
    logger.info(f"Revisando cada {CHECK_INTERVAL_SECONDS // 60} minutos. Ctrl+C para detener.\n")

    while True:
        try:
            run_once(api, state)
        except Exception as e:
            logger.error(f"[ERROR GENERAL] {e}", exc_info=True)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
