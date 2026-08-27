"""
Estrategia de "take-profit + reingreso por pullback desde el pico" para
YPF y VIST, en PESOS ARGENTINOS, con capital separado de tu DCA existente
en YPF.

Costos reales incorporados (según boleto de Balanz/Brubank del 14/07/2026):
- Comisión total por operación (arancel + derecho de mercado + IVA): 0.7865%
  Se aplica tanto en la compra como en la venta.

Impuesto a las Ganancias sobre CEDEARs:
- Hay información contradictoria sobre si las ganancias por venta de
  CEDEARs están exentas (como las acciones locales) o gravadas al 15%.
  NO SOY CONTADOR — confirmá esto con un profesional o en la app.
  Mientras tanto, este script calcula AMBOS escenarios para que veas
  el impacto real en cada caso.

Simplificación importante: el precio en pesos del CEDEAR se aproxima
usando el % de variación del ADR en dólares (no se modela el efecto del
tipo de cambio CCL por separado). En la práctica, el precio en pesos del
CEDEAR también se mueve por el CCL, así que el resultado real puede
diferir de esta simulación.

Uso:
    python swing_take_profit_ars.py
"""
import yfinance as yf
import pandas as pd

SYMBOLS = {
    "YPF": "YPF",
    "VIST": "Vista Energy",
}

START_DATE = "2026-01-01"
INITIAL_CAPITAL_ARS = 100_000
PROFIT_TARGET_PCT = 0.10
PULLBACK_PCT = 0.05
STOP_LOSS_PCT = 0.08
COMMISSION_PCT = 0.007865   # 0.7865%, según boleto real de Balanz/Brubank
TAX_SCENARIOS = {"Exento (0%)": 0.0, "Gravado (15%)": 0.15}


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def run_swing_strategy(symbol: str, start: str, capital: float,
                        profit_target_pct: float, pullback_pct: float,
                        stop_loss_pct: float, commission_pct: float, tax_pct: float):
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
    total_commissions = 0.0
    total_tax = 0.0

    for date, price in prices.items():
        if shares == 0:
            if peak_since_flat is None or price > peak_since_flat:
                peak_since_flat = price

            if price <= peak_since_flat * (1 - pullback_pct):
                gross_shares = cash / price
                # Reservamos margen para la comisión de compra
                shares = int((cash / (1 + commission_pct)) // price)
                if shares > 0:
                    cost = shares * price
                    commission = cost * commission_pct
                    cash -= (cost + commission)
                    total_commissions += commission
                    entry_price = price
                    trades.append((date, "BUY", price, shares, commission))
                    peak_since_flat = None
        else:
            change_pct = (price - entry_price) / entry_price
            should_sell = False
            reason = ""

            if change_pct <= -stop_loss_pct:
                should_sell, reason = True, "SELL (stop-loss)"
            elif price >= entry_price * (1 + profit_target_pct):
                should_sell, reason = True, "SELL (take-profit)"

            if should_sell:
                proceeds = shares * price
                commission = proceeds * commission_pct
                gain = proceeds - (shares * entry_price)
                tax = max(0, gain) * tax_pct  # el impuesto solo aplica sobre ganancia positiva

                cash += proceeds - commission - tax
                total_commissions += commission
                total_tax += tax

                trades.append((date, reason, price, shares, commission))
                shares = 0
                entry_price = None
                peak_since_flat = price

    final_price = prices.iloc[-1]
    final_value = cash + shares * final_price
    return_pct = (final_value / capital - 1) * 100

    return {
        "symbol": symbol,
        "final_value": final_value,
        "return_pct": return_pct,
        "num_trades": len(trades),
        "total_commissions": total_commissions,
        "total_tax": total_tax,
        "trades": trades,
        "open_shares": shares,
    }


if __name__ == "__main__":
    capital_per_symbol = INITIAL_CAPITAL_ARS / len(SYMBOLS)

    for tax_label, tax_pct in TAX_SCENARIOS.items():
        print(f"\n{'='*60}")
        print(f"ESCENARIO: {tax_label}")
        print(f"{'='*60}")

        total_final = 0
        total_commissions_all = 0
        total_tax_all = 0

        for symbol in SYMBOLS:
            r = run_swing_strategy(symbol, START_DATE, capital_per_symbol,
                                    PROFIT_TARGET_PCT, PULLBACK_PCT, STOP_LOSS_PCT,
                                    COMMISSION_PCT, tax_pct)
            if r:
                print(f"\n{r['symbol']}:")
                print(f"  Capital inicial:     ${capital_per_symbol:,.2f} ARS")
                print(f"  Capital final:       ${r['final_value']:,.2f} ARS  ({r['return_pct']:+.2f}%)")
                print(f"  Operaciones:         {r['num_trades']}")
                print(f"  Comisiones pagadas:  ${r['total_commissions']:,.2f} ARS")
                print(f"  Impuesto pagado:     ${r['total_tax']:,.2f} ARS")
                total_final += r["final_value"]
                total_commissions_all += r["total_commissions"]
                total_tax_all += r["total_tax"]

        total_return_pct = (total_final / INITIAL_CAPITAL_ARS - 1) * 100
        print(f"\n--- TOTAL PANEL (YPF + VIST) — {tax_label} ---")
        print(f"Capital inicial:        ${INITIAL_CAPITAL_ARS:,.2f} ARS")
        print(f"Capital final:           ${total_final:,.2f} ARS")
        print(f"Retorno neto:            {total_return_pct:+.2f}%")
        print(f"Comisiones totales:      ${total_commissions_all:,.2f} ARS")
        print(f"Impuesto total:          ${total_tax_all:,.2f} ARS")
