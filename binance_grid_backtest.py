"""
Backtesting de la estrategia de Grid Trading sobre datos históricos de
Binance Futures. No usa las API keys ni arriesga nada — los datos de velas
son públicos. Corré esto primero, siempre, antes de tocar el bot en vivo
(ni siquiera en testnet).

⚠️ Esta simulación es una aproximación educativa: NO modela liquidación
por apalancamiento, funding rate, ni slippage/parcialidad de órdenes.
Solo estima el PnL bruto de la grilla asumiendo que cada orden se ejecuta
exactamente al precio del nivel. El apalancamiento amplifica tanto las
ganancias como las pérdidas y las comisiones — mirá el resultado con
esa salvedad en mente, y validá igual en testnet en vivo durante varias
semanas antes de pensar en cuenta real.

Uso:
    python binance_grid_backtest.py
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from binance_config import GRID_CONFIG, FEE_PCT
from grid_strategy import build_levels, find_crossings

KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"


def fetch_klines(symbol: str, interval: str, start: datetime, end: datetime) -> list:
    """Descarga velas históricas de Binance Futures (endpoint público, sin
    API key), paginando de a 1500 velas hasta cubrir [start, end]."""
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    all_klines = []

    while start_ms < end_ms:
        resp = requests.get(KLINES_URL, params={
            "symbol": symbol, "interval": interval,
            "startTime": start_ms, "endTime": end_ms, "limit": 1500,
        }, timeout=15)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_klines.extend(batch)
        start_ms = batch[-1][6] + 1  # close_time de la última vela + 1ms
        if len(batch) < 1500:
            break
        time.sleep(0.2)  # no pegarle demasiado rápido al rate limit público

    return all_klines


def run_backtest(symbol: str, interval: str = "1h", days_back: int = 180):
    cfg = GRID_CONFIG[symbol]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    print(f"Descargando velas de {symbol} ({interval}, últimos {days_back} días)...")
    klines = fetch_klines(symbol, interval, start, end)
    if not klines:
        print("No se encontraron datos. Verificá el símbolo y el rango de fechas.")
        return

    closes = [float(k[4]) for k in klines]
    times = [datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc) for k in klines]

    ref_price = closes[0]
    lower = ref_price * (1 - cfg["range_pct"])
    upper = ref_price * (1 + cfg["range_pct"])
    levels = build_levels(lower, upper, cfg["grid_count"])
    invalidate_low = lower * (1 - cfg["invalidate_pct"])
    invalidate_high = upper * (1 + cfg["invalidate_pct"])

    print(f"Precio de referencia: ${ref_price:,.2f} | Rango de grilla: ${lower:,.2f} - ${upper:,.2f} "
          f"({cfg['grid_count']} niveles, leverage {cfg['leverage']}x)")

    positions = {}  # nivel -> {"qty":, "entry_price":}
    realized_pnl = 0.0
    trades = []
    invalidated_at = None
    previous_price = closes[0]

    for t, price in zip(times, closes):
        if invalidated_at is not None:
            break

        if price < invalidate_low or price > invalidate_high:
            invalidated_at = (t, price)
            break

        crossed, direction = find_crossings(levels, previous_price, price)

        for i in crossed:
            if direction == "down":
                if i < len(levels) - 1 and i not in positions:
                    qty = (cfg["capital_per_grid_usd"] * cfg["leverage"]) / levels[i]
                    positions[i] = {"qty": qty, "entry_price": levels[i]}
                    trades.append((t, "BUY", levels[i], qty))
            else:
                below = i - 1
                if below in positions:
                    pos = positions.pop(below)
                    sell_price = levels[i]
                    gross = (sell_price - pos["entry_price"]) * pos["qty"]
                    fees = (sell_price + pos["entry_price"]) * pos["qty"] * FEE_PCT
                    pnl = gross - fees
                    realized_pnl += pnl
                    trades.append((t, "SELL", sell_price, pos["qty"], pnl))

        previous_price = price

    final_price = closes[-1]
    open_positions_value = sum(
        (final_price - pos["entry_price"]) * pos["qty"] for pos in positions.values()
    )
    total_margin = cfg["capital_per_grid_usd"] * cfg["grid_count"]
    total_pnl = realized_pnl + open_positions_value
    total_return_pct = (total_pnl / total_margin) * 100

    buy_hold_qty = total_margin / ref_price
    buy_hold_pnl = (final_price - ref_price) * buy_hold_qty
    buy_hold_return_pct = (buy_hold_pnl / total_margin) * 100

    print(f"\n--- Resultados del backtest de grilla: {symbol} ---")
    if invalidated_at:
        print(f"[AVISO] Grilla INVALIDADA el {invalidated_at[0].date()} (precio salio del rango: ${invalidated_at[1]:,.2f}). "
              f"Se detuvo la simulacion ahi -- en vivo, el bot dejaria de operar este simbolo y avisaria.")
    print(f"Margen total de referencia:     ${total_margin:,.2f}  (capital_per_grid_usd × grid_count)")
    print(f"PnL realizado (celdas cerradas): ${realized_pnl:,.2f}")
    print(f"PnL no realizado (celdas abiertas): ${open_positions_value:,.2f}  ({len(positions)} posiciones abiertas)")
    print(f"PnL total estimado (grilla, {cfg['leverage']}x): ${total_pnl:,.2f}  ({total_return_pct:+.2f}% del margen)")
    print(f"Comparación buy & hold (sin apalancamiento): ${buy_hold_pnl:,.2f}  ({buy_hold_return_pct:+.2f}%)")
    print(f"Cantidad de operaciones cerradas: {len([t for t in trades if t[1] == 'SELL'])}")
    print("\nÚltimas operaciones:")
    for t in trades[-10:]:
        if t[1] == "BUY":
            print(f"  {t[0]}  {t[1]:5s}  precio=${t[2]:,.2f}  qty={t[3]:.6f}")
        else:
            print(f"  {t[0]}  {t[1]:5s}  precio=${t[2]:,.2f}  qty={t[3]:.6f}  pnl=${t[4]:+,.2f}")

    return trades


if __name__ == "__main__":
    for symbol in GRID_CONFIG:
        run_backtest(symbol, interval="1h", days_back=180)
        print("\n" + "=" * 70 + "\n")
