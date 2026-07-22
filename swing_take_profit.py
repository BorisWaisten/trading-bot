"""
Estrategia de "take-profit + reingreso por pullback desde el pico"
para YPF y VIST (ADRs, cotización en USD).

Lógica (por cada símbolo, de forma independiente):
1. Mientras estás AFUERA del mercado (sin posición): se trackea el precio
   más alto ("pico") desde que quedaste afuera. Cuando el precio cae un
   PULLBACK_PCT desde ese pico, COMPRÁS.
2. Mientras estás ADENTRO (con posición): cuando el precio sube un
   PROFIT_TARGET_PCT desde tu precio de compra, VENDÉS (asegurás ganancia).
3. Apenas vendés, se reinicia el trackeo del pico desde ese momento, y
   se repite el ciclo.

Uso:
    python swing_take_profit.py
"""
import yfinance as yf
import pandas as pd

SYMBOLS = {
    "YPF": "YPF",
    "VIST": "Vista Energy",
}

START_DATE = "2023-01-01"   # ahora evaluamos un período más amplio: 2023 a hoy
INITIAL_CAPITAL = 10_000
PROFIT_TARGET_PCT = 0.10   # vender al subir 10% desde la compra
PULLBACK_PCT = 0.05        # comprar al caer 5% desde el pico
STOP_LOSS_PCT = 0.08       # vender de emergencia si cae 8% desde la compra (protección, nuevo)


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def run_swing_strategy(symbol: str, start: str, capital: float,
                        profit_target_pct: float, pullback_pct: float, stop_loss_pct: float):
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
    if raw.empty:
        print(f"{symbol}: sin datos disponibles.")
        return None

    raw = flatten_columns(raw)
    prices = raw["Close"]

    cash = capital
    shares = 0
    entry_price = None
    peak_since_flat = None
    trades = []

    for date, price in prices.items():
        if shares == 0:
            # Afuera del mercado: trackear el pico y esperar la caída del 5%
            if peak_since_flat is None or price > peak_since_flat:
                peak_since_flat = price

            if price <= peak_since_flat * (1 - pullback_pct):
                shares = int(cash // price)
                if shares > 0:
                    cash -= shares * price
                    entry_price = price
                    trades.append((date, "BUY", price, shares))
                    peak_since_flat = None
        else:
            # Con posición: chequear stop-loss primero (protección), después take-profit
            change_pct = (price - entry_price) / entry_price

            if change_pct <= -stop_loss_pct:
                cash += shares * price
                trades.append((date, "SELL (stop-loss)", price, shares))
                shares = 0
                entry_price = None
                peak_since_flat = price
            elif price >= entry_price * (1 + profit_target_pct):
                cash += shares * price
                trades.append((date, "SELL (take-profit)", price, shares))
                shares = 0
                entry_price = None
                peak_since_flat = price  # empieza a trackear el próximo pico desde acá

    final_price = prices.iloc[-1]
    final_value = cash + shares * final_price
    return_pct = (final_value / capital - 1) * 100

    buy_hold_shares = int(capital // prices.iloc[0])
    buy_hold_value = buy_hold_shares * final_price + (capital - buy_hold_shares * prices.iloc[0])
    buy_hold_return_pct = (buy_hold_value / capital - 1) * 100

    print(f"\n=== {symbol} ({SYMBOLS.get(symbol, '')}) ===")
    print(f"Capital inicial:            ${capital:,.2f}")
    print(f"Capital final (estrategia): ${final_value:,.2f}  ({return_pct:+.2f}%)")
    print(f"Capital final (buy & hold): ${buy_hold_value:,.2f}  ({buy_hold_return_pct:+.2f}%)")
    print(f"Cantidad de operaciones:    {len(trades)}")
    if shares > 0:
        print(f"(Posición abierta al final: {shares} acciones sin vender)")
    print("Operaciones:")
    for t in trades:
        print(f"  {t[0].date()}  {t[1]:20s}  precio=${t[2]:.2f}  cantidad={t[3]}")

    return {"symbol": symbol, "return_pct": return_pct, "final_value": final_value,
            "buy_hold_return_pct": buy_hold_return_pct}


if __name__ == "__main__":
    capital_per_symbol = INITIAL_CAPITAL / len(SYMBOLS)
    results = []
    for symbol in SYMBOLS:
        r = run_swing_strategy(symbol, START_DATE, capital_per_symbol,
                                PROFIT_TARGET_PCT, PULLBACK_PCT, STOP_LOSS_PCT)
        if r:
            results.append(r)

    if results:
        total_final = sum(r["final_value"] for r in results)
        total_return_pct = (total_final / INITIAL_CAPITAL - 1) * 100
        print(f"\n=== TOTAL PANEL (YPF + VIST) ===")
        print(f"Capital inicial: ${INITIAL_CAPITAL:,.2f}")
        print(f"Capital final:   ${total_final:,.2f}")
        print(f"Retorno total:   {total_return_pct:+.2f}%")
