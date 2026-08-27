"""
Filtro macro: combina petróleo (WTI) y tipo de cambio CCL en un semáforo
(GREEN / YELLOW / RED) que se usa como filtro adicional antes de comprar.

No reemplaza la estrategia técnica (pullback/take-profit/stop-loss): solo
bloquea NUEVAS compras cuando el contexto macro es claramente negativo.
No fuerza ventas de posiciones ya abiertas.

Fuentes:
- Petróleo (WTI, ticker CL=F): vía yfinance, gratis, sin necesidad de API key.
- CCL: vía dolarapi.com, gratis, comunidad (no oficial). Como esta API solo
  devuelve el valor ACTUAL (no histórico), este módulo arma su propio
  historial local en un archivo JSON para poder calcular variaciones con
  el tiempo. Los primeros días, al no haber historial suficiente, el CCL
  se reporta como GREEN por defecto (dato insuficiente, no señal negativa).
"""
import json
import os
from datetime import datetime

import requests
import yfinance as yf
import pandas as pd

DATA_DIR = os.getenv("DATA_DIR", ".")
CCL_HISTORY_FILE = os.path.join(DATA_DIR, "ccl_history.json")
CCL_LOOKBACK_ENTRIES = 3   # comparar contra el valor de hace N registros guardados

# Umbrales
OIL_RED_DROP_PCT = 0.05     # caída del petróleo en 3 días que dispara ROJO
OIL_YELLOW_DROP_PCT = 0.02  # caída que dispara AMARILLO
CCL_RED_RISE_PCT = 0.04     # suba del CCL que dispara ROJO
CCL_YELLOW_RISE_PCT = 0.02  # suba del CCL que dispara AMARILLO


def get_oil_signal() -> dict:
    """Señal basada en la variación del WTI (petróleo) en los últimos días."""
    try:
        raw = yf.download("CL=F", period="10d", progress=False, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        if len(raw) < 4:
            return {"signal": "GREEN", "detail": "Datos insuficientes de petróleo, se asume neutral."}

        recent = raw["Close"].iloc[-1]
        past = raw["Close"].iloc[-4]  # ~3 ruedas atrás
        change_pct = (recent - past) / past

        if change_pct <= -OIL_RED_DROP_PCT:
            return {"signal": "RED", "detail": f"Petróleo cayó {change_pct:.2%} en 3 ruedas."}
        elif change_pct <= -OIL_YELLOW_DROP_PCT:
            return {"signal": "YELLOW", "detail": f"Petróleo cayó {change_pct:.2%} en 3 ruedas."}
        else:
            return {"signal": "GREEN", "detail": f"Petróleo estable/positivo ({change_pct:+.2%} en 3 ruedas)."}
    except Exception as e:
        return {"signal": "GREEN", "detail": f"Error consultando petróleo ({e}), se asume neutral."}


def _load_ccl_history() -> list:
    if os.path.exists(CCL_HISTORY_FILE):
        with open(CCL_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def _save_ccl_history(history: list):
    with open(CCL_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_ccl_signal() -> dict:
    """Señal basada en la variación reciente del dólar CCL, usando un
    historial local que el propio bot va armando con cada corrida."""
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/contadoconliqui", timeout=10)
        response.raise_for_status()
        data = response.json()
        current_value = float(data["venta"])
    except Exception as e:
        return {"signal": "GREEN", "detail": f"Error consultando CCL ({e}), se asume neutral."}

    history = _load_ccl_history()
    history.append({"timestamp": datetime.now().isoformat(), "value": current_value})
    history = history[-100:]  # no dejar que el archivo crezca indefinidamente
    _save_ccl_history(history)

    if len(history) <= CCL_LOOKBACK_ENTRIES:
        return {"signal": "GREEN", "detail": f"CCL actual ${current_value:,.2f}. Historial insuficiente aún, se asume neutral."}

    past_value = history[-1 - CCL_LOOKBACK_ENTRIES]["value"]
    change_pct = (current_value - past_value) / past_value

    if change_pct >= CCL_RED_RISE_PCT:
        return {"signal": "RED", "detail": f"CCL subió {change_pct:+.2%} (${past_value:,.2f} -> ${current_value:,.2f})."}
    elif change_pct >= CCL_YELLOW_RISE_PCT:
        return {"signal": "YELLOW", "detail": f"CCL subió {change_pct:+.2%} (${past_value:,.2f} -> ${current_value:,.2f})."}
    else:
        return {"signal": "GREEN", "detail": f"CCL estable (${current_value:,.2f}, {change_pct:+.2%})."}


def get_market_signal() -> dict:
    """Combina petróleo + CCL en un semáforo único.
    Regla: si cualquiera de los dos está en ROJO, el resultado es ROJO.
    Si ninguno está en ROJO pero alguno está en AMARILLO, el resultado es AMARILLO.
    Si ambos están en VERDE, el resultado es VERDE.
    """
    oil = get_oil_signal()
    ccl = get_ccl_signal()

    if oil["signal"] == "RED" or ccl["signal"] == "RED":
        combined = "RED"
    elif oil["signal"] == "YELLOW" or ccl["signal"] == "YELLOW":
        combined = "YELLOW"
    else:
        combined = "GREEN"

    return {
        "signal": combined,
        "oil": oil,
        "ccl": ccl,
    }


if __name__ == "__main__":
    result = get_market_signal()
    print(f"Semáforo macro: {result['signal']}")
    print(f"  Petróleo: {result['oil']['signal']} — {result['oil']['detail']}")
    print(f"  CCL:      {result['ccl']['signal']} — {result['ccl']['detail']}")
