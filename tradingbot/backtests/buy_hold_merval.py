"""
Análisis de Buy & Hold: rendimiento en lo que va de 2026 de las principales
acciones del panel líder del Merval (por capitalización de mercado, datos
de julio 2026).

NOTA IMPORTANTE: estos tickers cotizan en BYMA (Buenos Aires), en pesos
argentinos. El bot de trading que armamos usa Alpaca, que solo opera
acciones listadas en EE.UU. (NYSE/NASDAQ) — por lo tanto este script sirve
para ANÁLISIS/BACKTESTING, pero el bot en vivo (bot.py) no puede operar
estos tickers directamente. Para operar automáticamente alguna de estas
empresas necesitarías su ADR en EE.UU. (ver MERVAL_TICKERS más abajo,
columna 'adr_alpaca').

Uso:
    python -m tradingbot.backtests.buy_hold_merval
"""
from datetime import datetime

import pandas as pd
import yfinance as yf

# Top 10 del panel líder del Merval por capitalización de mercado (jul-2026).
# 'yahoo' = ticker para yfinance (sufijo .BA = Buenos Aires).
# 'adr_alpaca' = ticker del ADR operable en Alpaca/EE.UU., si existe.
MERVAL_TICKERS = {
    "YPFD": {"name": "YPF", "yahoo": "YPFD.BA", "adr_alpaca": "YPF"},
    "GGAL": {"name": "Grupo Financiero Galicia", "yahoo": "GGAL.BA", "adr_alpaca": "GGAL"},
    "TECO2": {"name": "Telecom Argentina", "yahoo": "TECO2.BA", "adr_alpaca": None},
    "BMA": {"name": "Banco Macro", "yahoo": "BMA.BA", "adr_alpaca": "BMA"},
    "TGSU2": {"name": "Transportadora de Gas del Sur", "yahoo": "TGSU2.BA", "adr_alpaca": "TGS"},
    "PAMP": {"name": "Pampa Energía", "yahoo": "PAMP.BA", "adr_alpaca": "PAM"},
    "BBAR": {"name": "Banco BBVA Argentina", "yahoo": "BBAR.BA", "adr_alpaca": "BBAR"},
    "CEPU": {"name": "Central Puerto", "yahoo": "CEPU.BA", "adr_alpaca": "CEPU"},
    "TXAR": {"name": "Ternium Argentina", "yahoo": "TXAR.BA", "adr_alpaca": None},
    "ALUA": {"name": "Aluar", "yahoo": "ALUA.BA", "adr_alpaca": None},
}

START_DATE = "2026-01-01"


def get_close_series(yahoo_ticker: str, start: str, end: str) -> pd.Series | None:
    raw = yf.download(yahoo_ticker, start=start, end=end, progress=False, auto_adjust=True)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return raw["Close"]


def run_analysis():
    end_date = datetime.now().strftime("%Y-%m-%d")
    print(f"Analizando rendimiento Buy & Hold desde {START_DATE} hasta {end_date}\n")

    results = []
    for symbol, info in MERVAL_TICKERS.items():
        series = get_close_series(info["yahoo"], START_DATE, end_date)
        if series is None or len(series) < 2:
            print(f"  [{symbol}] Sin datos disponibles, se omite.")
            continue

        start_price = series.iloc[0]
        end_price = series.iloc[-1]
        return_pct = (end_price / start_price - 1) * 100

        results.append({
            "symbol": symbol,
            "name": info["name"],
            "adr_alpaca": info["adr_alpaca"] or "—",
            "start_price": start_price,
            "end_price": end_price,
            "return_pct": return_pct,
        })

    if not results:
        print("No se pudo descargar ningún dato. Verificá tu conexión a internet.")
        return

    results.sort(key=lambda r: r["return_pct"], reverse=True)

    print(f"{'Acción':<28} {'Ticker':<8} {'ADR (Alpaca)':<14} {'Precio inicial':>15} {'Precio actual':>15} {'Retorno':>10}")
    print("-" * 95)
    for r in results:
        print(f"{r['name']:<28} {r['symbol']:<8} {r['adr_alpaca']:<14} "
              f"{r['start_price']:>15,.2f} {r['end_price']:>15,.2f} {r['return_pct']:>+9.2f}%")

    # Portafolio equal-weighted: mismo monto invertido en cada acción desde el inicio
    avg_return = sum(r["return_pct"] for r in results) / len(results)
    print("-" * 95)
    print(f"{'PROMEDIO (equal-weighted, todas las acciones)':<28} {'':<8} {'':<14} {'':>15} {'':>15} {avg_return:>+9.2f}%")

    best = results[0]
    worst = results[-1]
    print(f"\nMejor performance: {best['name']} ({best['symbol']}) con {best['return_pct']:+.2f}%")
    print(f"Peor performance:  {worst['name']} ({worst['symbol']}) con {worst['return_pct']:+.2f}%")

    print("\nNota: precios en pesos argentinos (ARS), tal como cotizan en BYMA. "
          "No incluye ajuste por inflación ni tipo de cambio.")


if __name__ == "__main__":
    run_analysis()
