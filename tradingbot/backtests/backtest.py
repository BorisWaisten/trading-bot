"""
Backtesting: prueba la estrategia con datos históricos, SIN arriesgar
dinero real ni simulado. Corré esto primero, siempre, antes de tocar
el bot de paper trading.

Uso:
    python backtest.py
"""
import yfinance as yf
import pandas as pd

from config import SYMBOL, SMA_SHORT, SMA_LONG, RISK_PER_TRADE_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT
from strategy import add_signals


def run_backtest(symbol: str, start: str, end: str, sma_short: int, sma_long: int,
                  initial_capital: float = 10_000):
    print(f"Descargando datos históricos de {symbol} ({start} a {end})...")
    raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
    if raw.empty:
        print("No se encontraron datos. Verificá el símbolo y las fechas.")
        return

    # yfinance a veces devuelve columnas con multi-nivel (Close, símbolo);
    # esto lo simplifica a un único nivel para poder trabajar normal
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(columns={"Close": "close"})[["close"]]
    df = add_signals(df, sma_short, sma_long)

    cash = initial_capital
    shares = 0
    entry_price = None
    trades = []

    for date, row in df.iterrows():
        price = row["close"]

        # Chequeo de stop-loss / take-profit sobre la posición abierta (aproximado con el cierre diario)
        if shares > 0 and entry_price is not None:
            change_pct = (price - entry_price) / entry_price
            if change_pct <= -STOP_LOSS_PCT:
                cash += shares * price
                trades.append((date, "SELL (stop-loss)", price, shares))
                shares, entry_price = 0, None
                continue
            elif change_pct >= TAKE_PROFIT_PCT:
                cash += shares * price
                trades.append((date, "SELL (take-profit)", price, shares))
                shares, entry_price = 0, None
                continue

        if row["position"] == 1 and shares == 0:  # señal de compra
            # Tamaño de posición según % de capital que se está dispuesto a arriesgar,
            # igual que hace el bot en vivo (config.RISK_PER_TRADE_PCT)
            total_equity = cash
            risk_amount = total_equity * RISK_PER_TRADE_PCT
            loss_per_share = price * STOP_LOSS_PCT
            qty_by_risk = int(risk_amount // loss_per_share) if loss_per_share > 0 else 0
            qty_by_cash = int(cash // price)
            shares = max(0, min(qty_by_risk, qty_by_cash))

            if shares > 0:
                cash -= shares * price
                entry_price = price
                trades.append((date, "BUY", price, shares))

        elif row["position"] == -1 and shares > 0:  # señal de venta (cruce bajista)
            cash += shares * price
            trades.append((date, "SELL (señal)", price, shares))
            shares, entry_price = 0, None

    final_price = df["close"].iloc[-1]
    final_value = cash + shares * final_price
    total_return_pct = (final_value / initial_capital - 1) * 100

    # Comparación contra "comprar y mantener" (buy & hold), el benchmark de referencia
    buy_hold_shares = initial_capital // df["close"].iloc[0]
    buy_hold_value = buy_hold_shares * final_price + (initial_capital - buy_hold_shares * df["close"].iloc[0])
    buy_hold_return_pct = (buy_hold_value / initial_capital - 1) * 100

    print(f"\n--- Resultados del backtest: {symbol} ---")
    print(f"Capital inicial:        ${initial_capital:,.2f}")
    print(f"Capital final (estrategia): ${final_value:,.2f}  ({total_return_pct:+.2f}%)")
    print(f"Capital final (buy & hold): ${buy_hold_value:,.2f}  ({buy_hold_return_pct:+.2f}%)")
    print(f"Cantidad de operaciones: {len(trades)}")
    print("\nÚltimas operaciones:")
    for t in trades[-10:]:
        print(f"  {t[0].date()}  {t[1]:20s}  precio=${t[2]:.2f}  cantidad={t[3]}")

    return df, trades


if __name__ == "__main__":
    run_backtest(
        symbol=SYMBOL,
        start="2022-01-01",
        end="2025-01-01",
        sma_short=SMA_SHORT,
        sma_long=SMA_LONG,
    )
