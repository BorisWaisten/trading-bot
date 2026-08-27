"""
Bot de PAPER TRADING (dinero simulado) conectado a Alpaca.

Revisa periódicamente si hay una señal de compra/venta según la estrategia
de cruce de medias móviles, y ejecuta la orden correspondiente en la cuenta
de paper trading.

IMPORTANTE:
- Esto opera con dinero SIMULADO por defecto (ALPACA_BASE_URL en config.py
  apunta a paper-api.alpaca.markets). No arriesga dinero real.
- No modifiques ALPACA_BASE_URL a la URL de trading real hasta haber
  validado la estrategia extensamente y entender los riesgos.
- Este código es una base educativa, no un consejo de inversión ni una
  garantía de resultados.

Uso:
    python bot.py
"""
import time
from datetime import datetime, timedelta

import alpaca_trade_api as tradeapi
import pandas as pd

from config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL,
    SYMBOL, SMA_SHORT, SMA_LONG,
    CHECK_INTERVAL_SECONDS, MAX_POSITION_VALUE_USD,
    RISK_PER_TRADE_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
)
from strategy import add_signals, latest_action


def get_api():
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise RuntimeError(
            "Faltan las credenciales de Alpaca. Creá un archivo .env "
            "con ALPACA_API_KEY y ALPACA_SECRET_KEY (ver config.py)."
        )
    return tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")


def fetch_price_history(api, symbol: str, lookback_days: int = 100) -> pd.DataFrame:
    """Trae velas diarias recientes desde Alpaca para calcular las medias móviles."""
    end = datetime.now()
    start = end - timedelta(days=lookback_days * 2)  # margen por fines de semana/feriados
    # Fechas en formato YYYY-MM-DD: .isoformat() incluye microsegundos sin
    # zona horaria, que la API de Alpaca rechaza como RFC3339 invalido.
    bars = api.get_bars(symbol, tradeapi.TimeFrame.Day, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")).df
    bars = bars.rename(columns={"close": "close"})[["close"]]
    return bars


def get_position_qty(api, symbol: str) -> float:
    try:
        position = api.get_position(symbol)
        return float(position.qty)
    except Exception:
        return 0.0


def check_exit_conditions(api, symbol: str) -> bool:
    """Cierra la posición si toca el stop-loss o el take-profit. Devuelve True si vendió."""
    try:
        position = api.get_position(symbol)
    except Exception:
        return False

    unrealized_plpc = float(position.unrealized_plpc)  # ganancia/pérdida % no realizada

    if unrealized_plpc <= -STOP_LOSS_PCT:
        print(f"[STOP-LOSS] {symbol} cayó {unrealized_plpc:.2%}. Cerrando posición.")
        api.close_position(symbol)
        return True

    if unrealized_plpc >= TAKE_PROFIT_PCT:
        print(f"[TAKE-PROFIT] {symbol} subió {unrealized_plpc:.2%}. Asegurando ganancia, cerrando posición.")
        api.close_position(symbol)
        return True

    return False


def calculate_position_size(api, price: float) -> int:
    """Calcula cuántas acciones comprar arriesgando como máximo RISK_PER_TRADE_PCT
    del capital total, y respetando además el tope MAX_POSITION_VALUE_USD.

    El "riesgo" se define como: cantidad de acciones × distancia al stop-loss.
    Así, si el stop-loss salta, la pérdida real queda acotada al % definido.
    """
    account = api.get_account()
    total_capital = float(account.equity)

    risk_amount = total_capital * RISK_PER_TRADE_PCT
    loss_per_share = price * STOP_LOSS_PCT  # cuánto se pierde por acción si toca el stop-loss

    if loss_per_share <= 0:
        return 0

    qty_by_risk = int(risk_amount // loss_per_share)
    qty_by_cap = int(MAX_POSITION_VALUE_USD // price)

    return max(0, min(qty_by_risk, qty_by_cap))


def run_once(api):
    print(f"\n[{datetime.now()}] Revisando {SYMBOL}...")

    # 1. Chequeo de stop-loss / take-profit primero (protección y realización de ganancias)
    if check_exit_conditions(api, SYMBOL):
        return

    # 2. Traer precios y calcular señales
    df = fetch_price_history(api, SYMBOL)
    df = add_signals(df, SMA_SHORT, SMA_LONG)
    action = latest_action(df)
    current_qty = get_position_qty(api, SYMBOL)
    last_price = df["close"].iloc[-1]

    print(f"  Precio actual: ${last_price:.2f} | Posición actual: {current_qty} acciones | Señal: {action}")

    # 3. Ejecutar según la señal
    if action == "BUY" and current_qty == 0:
        qty = calculate_position_size(api, last_price)
        if qty <= 0:
            print("  Señal de compra ignorada: el tamaño calculado según el riesgo permitido es 0.")
            return
        api.submit_order(symbol=SYMBOL, qty=qty, side="buy", type="market", time_in_force="day")
        print(f"  -> Orden de COMPRA enviada: {qty} acciones de {SYMBOL} "
              f"(arriesgando ~{RISK_PER_TRADE_PCT:.1%} del capital)")

    elif action == "SELL" and current_qty > 0:
        api.submit_order(symbol=SYMBOL, qty=current_qty, side="sell", type="market", time_in_force="day")
        print(f"  -> Orden de VENTA enviada: {current_qty} acciones de {SYMBOL}")

    else:
        print("  -> Sin acción. Se mantiene la posición actual.")


def main():
    api = get_api()
    account = api.get_account()
    print("Conectado a Alpaca (PAPER TRADING)")
    print(f"Balance de la cuenta simulada: ${float(account.cash):,.2f}")
    print(f"Revisando {SYMBOL} cada {CHECK_INTERVAL_SECONDS // 60} minutos. Ctrl+C para detener.\n")

    while True:
        try:
            run_once(api)
        except Exception as e:
            print(f"  [ERROR] {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
