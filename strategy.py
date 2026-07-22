"""
Estrategia de cruce de medias móviles (SMA crossover).

Lógica:
- Señal de COMPRA cuando la SMA corta cruza HACIA ARRIBA a la SMA larga
  (momento en que la tendencia de corto plazo se vuelve más fuerte que la de largo plazo)
- Señal de VENTA cuando la SMA corta cruza HACIA ABAJO a la SMA larga

Esta es una estrategia de tendencia clásica y simple. No es garantía de
ganancias: funciona mejor en mercados con tendencia definida y peor en
mercados laterales ("sin rumbo"), donde genera señales falsas.
"""
import pandas as pd


def add_signals(df: pd.DataFrame, sma_short: int, sma_long: int) -> pd.DataFrame:
    """Agrega columnas de SMA y señales de compra/venta a un DataFrame de precios.

    Espera un DataFrame con una columna 'close'.
    Devuelve el mismo DataFrame con columnas: sma_short, sma_long, signal, position.
    """
    df = df.copy()
    df["sma_short"] = df["close"].rolling(window=sma_short).mean()
    df["sma_long"] = df["close"].rolling(window=sma_long).mean()

    # 1 = corta por encima de la larga (tendencia alcista), 0 = por debajo
    df["signal"] = 0
    df.loc[df["sma_short"] > df["sma_long"], "signal"] = 1

    # 'position' marca el punto exacto donde cambia la señal:
    #  1 -> se acaba de cruzar hacia arriba (COMPRAR)
    # -1 -> se acaba de cruzar hacia abajo (VENDER)
    #  0 -> sin cambio, mantener posición actual
    df["position"] = df["signal"].diff()

    return df


def latest_action(df: pd.DataFrame) -> str:
    """Devuelve 'BUY', 'SELL' o 'HOLD' según la última fila del DataFrame con señales."""
    if df.empty or len(df) < 2:
        return "HOLD"

    last_position = df["position"].iloc[-1]
    if last_position == 1:
        return "BUY"
    elif last_position == -1:
        return "SELL"
    return "HOLD"
