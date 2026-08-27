"""
Dashboard local (Streamlit) para ver de un vistazo el estado de los bots:
cuenta y posiciones de Alpaca (acciones, paper trading) y de Binance
Futures (grilla BTC/ETH/SOL, testnet por defecto).

Es de SOLO LECTURA: no coloca, modifica ni cancela ninguna orden. Lee las
cuentas vía API y el estado que ya guardan los bots (swing_state.json,
binance_grid_state.json) para mostrarlo en una sola pantalla, en vez de
andar mirando los .log a mano.

Uso:
    streamlit run dashboard.py
"""
import json
import math
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

REFRESH_SECONDS = 30


def read_tail(path: str, n: int = 20) -> str:
    if not os.path.exists(path):
        return "Sin actividad registrada todavía."
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(lines[-n:]) or "Sin actividad registrada todavía."


def read_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------- Alpaca --
def render_alpaca():
    st.header("Acciones (Alpaca, paper trading)")
    try:
        import alpaca_trade_api as tradeapi
        from config import (
            ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL,
            DATA_DIR, SWING_STATE_FILE,
        )
    except Exception as e:
        st.error(f"No se pudo cargar config.py: {e}")
        return

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        st.info("Todavía no configuraste ALPACA_API_KEY / ALPACA_SECRET_KEY en .env.")
        return

    try:
        api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")
        account = api.get_account()
    except Exception as e:
        st.error(f"No se pudo conectar a Alpaca: {e}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Equity", f"${float(account.equity):,.2f}")
    col2.metric("Cash disponible", f"${float(account.cash):,.2f}")
    col3.metric("Buying power", f"${float(account.buying_power):,.2f}")

    positions = api.list_positions()
    st.subheader("Posiciones abiertas")
    if positions:
        rows = [{
            "Simbolo": p.symbol,
            "Cantidad": float(p.qty),
            "Precio entrada": float(p.avg_entry_price),
            "Precio actual": float(p.current_price),
            "P/L no realizado": float(p.unrealized_pl),
            "P/L %": float(p.unrealized_plpc) * 100,
        } for p in positions]
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.format({
                "Cantidad": "{:.4f}", "Precio entrada": "${:,.2f}", "Precio actual": "${:,.2f}",
                "P/L no realizado": "${:+,.2f}", "P/L %": "{:+.2f}%",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.write("Sin posiciones abiertas.")

    swing_state = read_json(SWING_STATE_FILE)
    if swing_state:
        st.subheader("Panel de rango (YPF / VIST)")
        rows = [{"Simbolo": sym, "Pico desde afuera": data.get("peak_since_flat")}
                for sym, data in swing_state.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    try:
        from macro_filter import get_market_signal
        signal = get_market_signal()
        st.subheader("Semaforo macro")
        st.write(f"**{signal['signal']}** -- Petroleo: {signal['oil']['signal']} "
                 f"({signal['oil']['detail']}) | CCL: {signal['ccl']['signal']} ({signal['ccl']['detail']})")
    except Exception as e:
        st.caption(f"No se pudo calcular el semaforo macro: {e}")

    with st.expander("Ultimas lineas del log (trading_bot.log)"):
        st.code(read_tail(os.path.join(DATA_DIR, "trading_bot.log")))


# --------------------------------------------------------------- Binance --
def render_binance():
    st.header("Cripto (Binance Futures, grid trading)")
    try:
        from binance_config import (
            BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
            GRID_CONFIG, GRID_STATE_FILE, GRID_LOG_FILE,
        )
    except Exception as e:
        st.error(f"No se pudo cargar binance_config.py: {e}")
        return

    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        st.info(
            "Todavia no configuraste BINANCE_API_KEY / BINANCE_API_SECRET en .env "
            "(conseguilas gratis en https://testnet.binancefuture.com/)."
        )
        return

    try:
        from binance.client import Client
        # ping=False: ver comentario en binance_grid_bot.py -- el ping por
        # defecto pega contra la API de Spot, no la de Futures que usa este
        # panel.
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=BINANCE_TESTNET, ping=False)
        balances = client.futures_account_balance()
    except Exception as e:
        st.error(f"No se pudo conectar a Binance: {e}")
        return

    st.caption("TESTNET (fondos simulados)" if BINANCE_TESTNET else "*** CUENTA REAL ***")

    usdt = next((b for b in balances if b["asset"] == "USDT"), None)
    if usdt:
        col1, col2 = st.columns(2)
        col1.metric("Balance USDT", f"${float(usdt['balance']):,.2f}")
        col2.metric("Disponible", f"${float(usdt['availableBalance']):,.2f}")

    state = read_json(GRID_STATE_FILE) or {}

    for symbol, cfg in GRID_CONFIG.items():
        st.subheader(symbol)
        symbol_state = state.get(symbol)
        if symbol_state is None:
            st.write("El bot todavia no inicializo la grilla de este simbolo (corre binance_grid_bot.py primero).")
            continue

        try:
            price = float(client.futures_symbol_ticker(symbol=symbol)["price"])
        except Exception:
            price = None

        status = "INVALIDADA" if symbol_state.get("invalidated") else "activa"
        cols = st.columns(4)
        cols[0].metric("Precio actual", f"${price:,.2f}" if price is not None else "N/D")
        cols[1].metric("Rango", f"${symbol_state['lower']:,.2f} - ${symbol_state['upper']:,.2f}")
        cols[2].metric("Estado", status)
        cols[3].metric("Leverage", f"{cfg['leverage']}x")

        positions = symbol_state.get("positions", {})
        if positions:
            rows = []
            for level, pos in positions.items():
                unrealized = (price - pos["entry_price"]) * pos["qty"] if price is not None else math.nan
                rows.append({
                    "Nivel": int(level),
                    "Cantidad": pos["qty"],
                    "Precio entrada": pos["entry_price"],
                    "P/L no realizado": unrealized,
                })
            df = pd.DataFrame(rows).sort_values("Nivel")
            st.dataframe(
                df.style.format({
                    "Cantidad": "{:.6f}", "Precio entrada": "${:,.2f}", "P/L no realizado": "${:+,.2f}",
                }),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("Sin posiciones abiertas en esta grilla.")

    with st.expander("Ultimas lineas del log (binance_grid_bot.log)"):
        st.code(read_tail(GRID_LOG_FILE))


def check_password() -> bool:
    """Si DASHBOARD_PASSWORD esta configurada, pide clave antes de mostrar
    el panel (relevante cuando el dashboard queda expuesto en una URL
    publica, ej. Railway). Sin esa variable, no pide nada (uso local)."""
    required = os.getenv("DASHBOARD_PASSWORD", "")
    if not required:
        return True
    if st.session_state.get("dashboard_authed"):
        return True

    st.title("Trading Bot -- Panel general")
    pwd = st.text_input("Clave de acceso", type="password")
    if pwd:
        if pwd == required:
            st.session_state["dashboard_authed"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")
    return False


def main():
    if not check_password():
        return

    st.title("Trading Bot -- Panel general")
    st.caption(f"Ultima actualizacion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    left, right = st.columns(2)
    with left:
        render_alpaca()
    with right:
        render_binance()

    st.divider()
    auto = st.checkbox(f"Auto-actualizar cada {REFRESH_SECONDS}s", value=True)
    st.button("Actualizar ahora")

    if auto:
        time.sleep(REFRESH_SECONDS)
        st.rerun()


if __name__ == "__main__":
    main()
