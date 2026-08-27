"""
Backtest de estrategia BUY & HOLD enfocado en el sector ENERGÍA del panel
Merval argentino, vía sus ADRs (cotización en USD en Wall Street).

Uso:
    python energy_buy_hold.py
"""
import yfinance as yf
import pandas as pd

# Panel de energía del Merval vía ADRs (cotizan en USD en NYSE/NASDAQ)
ENERGY_ADRS = {
    "YPF": "YPF (petrolera integrada, mayor market cap del sector)",
    "VIST": "Vista Energy (shale oil, Vaca Muerta)",
    "PAM": "Pampa Energía (oil & gas + generación eléctrica)",
    "CEPU": "Central Puerto (generación eléctrica)",
    "TGS": "Transportadora de Gas del Sur (transporte de gas)",
    "EDN": "Edenor (distribución eléctrica)",
}

START_DATE = "2026-01-01"  # lo que va del año
INITIAL_CAPITAL = 10_000


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def run_buy_and_hold(symbols: dict, start: str, initial_capital: float):
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    print(f"Descargando datos de {len(symbols)} acciones de energía ({start} a {end})...\n")

    capital_per_symbol = initial_capital / len(symbols)
    results = []

    for symbol, name in symbols.items():
        raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
        if raw.empty:
            print(f"  {symbol}: sin datos disponibles, se omite.")
            continue

        raw = flatten_columns(raw)
        start_price = raw["Close"].iloc[0]
        end_price = raw["Close"].iloc[-1]
        return_pct = (end_price / start_price - 1) * 100
        final_value = capital_per_symbol * (end_price / start_price)

        results.append({
            "symbol": symbol,
            "name": name,
            "start_price": start_price,
            "end_price": end_price,
            "return_pct": return_pct,
            "final_value": final_value,
        })

    if not results:
        print("No se pudo descargar ningún dato.")
        return

    df_results = pd.DataFrame(results).sort_values("return_pct", ascending=False)

    total_final_value = df_results["final_value"].sum()
    total_return_pct = (total_final_value / initial_capital - 1) * 100

    print("--- Resultados individuales (ordenados de mejor a peor) ---")
    for _, row in df_results.iterrows():
        print(f"  {row['symbol']:6s} ({row['name']:50s})")
        print(f"          ${row['start_price']:.2f} -> ${row['end_price']:.2f}   {row['return_pct']:+.2f}%")

    print(f"\n--- Panel de energía completo (capital repartido en partes iguales) ---")
    print(f"Capital inicial:  ${initial_capital:,.2f}")
    print(f"Capital final:    ${total_final_value:,.2f}")
    print(f"Retorno total:    {total_return_pct:+.2f}%")
    print(f"\nMejor performer:  {df_results.iloc[0]['symbol']} ({df_results.iloc[0]['return_pct']:+.2f}%)")
    print(f"Peor performer:   {df_results.iloc[-1]['symbol']} ({df_results.iloc[-1]['return_pct']:+.2f}%)")

    return df_results


if __name__ == "__main__":
    run_buy_and_hold(ENERGY_ADRS, START_DATE, INITIAL_CAPITAL)
