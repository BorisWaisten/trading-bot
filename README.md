# Dashboard (panel general)

Panel único de **solo lectura** para ver de un vistazo el estado de ambos
bots (acciones y cripto) sin tener que leer los `.log` a mano: cuenta,
posiciones abiertas, P/L, estado de la grilla de Binance y semáforo macro.
No coloca, modifica ni cancela ninguna orden.

```bash
streamlit run tradingbot/dashboard.py
```

Se abre en http://localhost:8501 y se auto-actualiza cada 30 segundos
(desactivable con el checkbox). Si todavía no configuraste las keys de
Binance en `.env`, ese panel simplemente avisa que falta configurarlo — no
hace falta tenerlas para ver el panel de Alpaca.

## Desplegar el dashboard en Railway (URL pública)

El dashboard lee archivos de estado (`data/swing_state.json`,
`data/binance_grid_state.json`, los `.log` en `data/`) que escriben los bots, así que tiene
que correr **en el mismo servicio/contenedor** que ellos para compartir el
filesystem. `run_all.py` levanta los bots en segundo plano y el dashboard
en primer plano, bindeado al puerto que asigna Railway:

1. En el servicio de Railway donde corre el bot, andá a **Settings → Deploy
   → Custom Start Command** y poné:
   ```
   python run_all.py
   ```
   (o dejá que use el `Procfile` del repo, que ya define lo mismo).
2. En **Variables**, agregá `DASHBOARD_PASSWORD` con una clave — sin esto
   cualquiera con la URL pública ve tus balances y posiciones. Opcionalmente
   `RAILWAY_BOTS` si querés levantar solo algunos bots (ej.
   `tradingbot.bots.swing_bot,tradingbot.bots.binance_grid_bot`); por
   defecto levanta los tres.
3. En **Settings → Networking**, generá un dominio público si todavía no
   tenés uno. Esa URL sirve el dashboard (Railway inyecta `$PORT`
   automáticamente, `run_all.py` lo usa para Streamlit).
4. Confirmá que `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
   `BINANCE_API_KEY`/`BINANCE_API_SECRET` ya estén cargadas como variables
   del servicio (las mismas que usan los bots).

Vercel no es una buena opción para esto: es serverless/edge, pensado para
funciones cortas y sitios estáticos, y Streamlit necesita un proceso
persistente con WebSocket abierto todo el tiempo.

---

# Bot de Trading Automatizado (Paper Trading) — Acciones

Bot educativo que automatiza una estrategia de **cruce de medias móviles (SMA)**
sobre acciones, usando la API de **Alpaca** en modo **paper trading** (dinero
simulado, datos de mercado reales).

⚠️ **Esto no es un consejo de inversión.** Es una base de código para que
aprendas, pruebes y ajustes a tu criterio. El trading conlleva riesgo real de
pérdida de capital. Nunca uses este bot en una cuenta real sin antes:
1. Entender completamente cómo funciona
2. Haber corrido el backtest en varios períodos y símbolos
3. Haber operado en paper trading durante semanas/meses
4. Consultar con un asesor financiero matriculado si vas a operar con dinero real

## 1. Instalación

```bash
pip install -r requirements.txt
```

## 2. Crear cuenta y obtener API keys (gratis)

1. Registrate en https://alpaca.markets/
2. En el dashboard, activá **Paper Trading** (viene por defecto, no requiere fondear nada)
3. Generá tu **API Key** y **Secret Key**
4. Copiá `.env.example` a `.env` y completá tus claves:

```bash
cp .env.example .env
# editá .env con tus datos
```

## 3. Backtesting (probar la estrategia con historia, sin riesgo)

```bash
python -m tradingbot.backtests.backtest
```

Esto descarga precios históricos, corre la estrategia y compara el resultado
contra simplemente "comprar y mantener" (buy & hold). **Corré esto primero y
ajustá los parámetros hasta que el resultado te convenza.**

## 4. Paper trading (dinero simulado, en vivo)

```bash
python -m tradingbot.bots.bot
```

El bot va a revisar el símbolo configurado periódicamente y ejecutar compras/
ventas simuladas según la señal. Podés ver el estado de tu cuenta y las
operaciones en el dashboard de Alpaca (sección Paper Trading).

## 5. Parámetros ajustables

Todo se configura en `tradingbot/config.py`:

| Parámetro | Qué hace |
|---|---|
| `SYMBOL` | Ticker a operar (ej. "AAPL") |
| `SMA_SHORT` / `SMA_LONG` | Períodos de las medias móviles |
| `RISK_PER_TRADE_PCT` | % del capital total que se arriesga por operación (regla 1-2%). El tamaño de la posición se calcula automáticamente en base a esto y al stop-loss |
| `STOP_LOSS_PCT` | % de pérdida al que se cierra la posición automáticamente |
| `TAKE_PROFIT_PCT` | % de ganancia al que se cierra la posición para asegurarla |
| `MAX_POSITION_VALUE_USD` | Tope adicional de exposición en dólares para el símbolo |
| `CHECK_INTERVAL_SECONDS` | Frecuencia de revisión de señales |

**Cómo se calcula el tamaño de la posición:** en vez de comprar una cantidad
fija de acciones, el bot calcula cuántas acciones puede comprar sin arriesgar
más de `RISK_PER_TRADE_PCT` del capital total, asumiendo que en el peor caso
el stop-loss se ejecuta. Por ejemplo, con capital de $10,000, riesgo del 1%
($100) y un stop-loss del 5%, el bot arriesga $100 / 5% = hasta $2,000 en
valor de posición.

## 6. Estructura del proyecto

```
trading_bot/
├── run_all.py                       # Entry point único (Railway): levanta bots + dashboard
├── requirements.txt
├── .env.example
├── data/                             # Estado y logs generados en runtime (gitignored)
└── tradingbot/
    ├── config.py                     # Config y credenciales (Alpaca / estrategia RANGO)
    ├── binance_config.py             # Config y credenciales (Binance grid)
    ├── macro_filter.py               # Semáforo macro (petróleo + CCL)
    ├── bond_monitor.py               # Monitoreo de bonos (en desarrollo)
    ├── dashboard.py                  # Panel Streamlit de solo lectura
    ├── strategies/
    │   ├── strategy.py               # Estrategia SMA crossover (ya no en producción)
    │   └── grid_strategy.py          # Lógica de niveles de grilla
    ├── bots/                         # Bots en vivo (paper trading / testnet)
    │   ├── bot.py                    # SMA sobre AAPL (ya no en producción)
    │   ├── swing_bot.py              # Estrategia de RANGO sobre YPF/VIST (el real)
    │   └── binance_grid_bot.py       # Grid trading sobre Binance Futures
    └── backtests/                    # Scripts exploratorios, no corren en producción
        ├── backtest.py
        ├── swing_take_profit.py
        ├── swing_take_profit_ars.py
        ├── binance_grid_backtest.py
        ├── buy_and_hold_merval.py
        ├── buy_hold_merval.py
        └── energy_buy_hold.py
```

Todos los módulos y bots se corren con `python -m tradingbot.<ruta>`, ej.
`python -m tradingbot.bots.swing_bot` (así los imports internos entre
archivos funcionan bien). Correr siempre desde la raíz del proyecto.

## Próximos pasos posibles

- Agregar más símbolos (portafolio en vez de un solo ticker)
- Probar otras estrategias (RSI, bandas de Bollinger, momentum)
- Añadir notificaciones (Telegram/email) cuando se ejecuta una orden
- Desplegar el bot en un servidor (ej. una VM pequeña) para que corra 24/7
- Solo después de mucha validación: evaluar migrar a cuenta real, cambiando
  `ALPACA_BASE_URL` en `config.py` — con pleno entendimiento del riesgo

---

# Bot de Grid Trading (Testnet) — Binance Futures: BTC / ETH / SOL

Módulo separado del anterior (broker y activos distintos, misma filosofía:
backtest primero, testnet después, cuenta real solo con mucha validación).

⚠️ **Esto no es un consejo de inversión.** Además del riesgo normal de
trading, este bot usa **apalancamiento en Binance Futures**, que amplifica
tanto ganancias como pérdidas y puede **liquidar tu posición** si el precio
se mueve en contra lo suficiente — perdés más rápido que en spot sin
apalancamiento. No lo uses con cuenta real sin:
1. Entender bien cómo funciona una grilla y qué es la liquidación
2. Correr `tradingbot/backtests/binance_grid_backtest.py` en varios rangos de fechas y símbolos
3. Operar en testnet durante semanas y revisar manualmente el margen y las
   posiciones abiertas
4. Consultar con un asesor financiero matriculado si vas a operar con dinero real

## Qué es una grilla (grid trading)

Se define un rango de precio `[lower, upper]` alrededor del precio actual y
se divide en niveles. El bot compra cuando el precio cae hasta un nivel
libre, y vende (con `reduceOnly`, para nunca terminar corto por error)
cuando sube al nivel siguiente, asegurando la ganancia de esa "celda". El
riesgo principal es que el precio rompa el rango y no vuelva: si se aleja
más de `invalidate_pct` del rango, el bot **deja de operar ese símbolo**
(no persigue el precio ni reabre la grilla solo).

## 1. Instalación

```bash
pip install -r requirements.txt
```

## 2. Obtener API keys de Binance Futures Testnet (gratis)

1. Entrá a https://testnet.binancefuture.com/ e iniciá sesión con GitHub
   (no hace falta tu cuenta real de Binance)
2. Generá tu API Key y Secret Key ahí — son distintas a las de tu cuenta real
3. Copiá `.env.example` a `.env` (si no lo hiciste ya) y completá:

```bash
BINANCE_API_KEY=tu_key_de_testnet
BINANCE_API_SECRET=tu_secret_de_testnet
BINANCE_TESTNET=true
```

## 3. Backtesting (histórico real, sin riesgo ni necesidad de API keys)

```bash
python -m tradingbot.backtests.binance_grid_backtest
```

Descarga velas históricas públicas de Binance Futures y simula la grilla
para BTCUSDT, ETHUSDT y SOLUSDT, comparando contra comprar-y-mantener.
**Corré esto primero.** Ojo: la simulación NO modela liquidación,
funding rate ni slippage — es una aproximación del PnL bruto, no una
garantía de lo que pasaría en vivo.

## 4. Bot en vivo (Testnet por defecto)

```bash
python -m tradingbot.bots.binance_grid_bot
```

Revisa cada símbolo cada `GRID_CHECK_INTERVAL_SECONDS` y coloca órdenes
market en Binance Futures Testnet cuando el precio cruza un nivel de la
grilla. Al iniciar por primera vez arma la grilla centrada en el precio
de mercado del momento (no hay precios hardcodeados). El estado se
guarda en `data/binance_grid_state.json` para sobrevivir reinicios.

## 5. Parámetros ajustables

Todo se configura en `tradingbot/binance_config.py`, en `GRID_CONFIG` por símbolo:

| Parámetro | Qué hace |
|---|---|
| `range_pct` | Ancho de la grilla: % hacia arriba/abajo del precio de referencia al iniciar |
| `grid_count` | Cantidad de niveles dentro del rango (más niveles = operaciones más chicas y frecuentes) |
| `leverage` | Apalancamiento en Binance Futures. Empezar bajo (2-3x): a mayor leverage, más cerca queda el precio de liquidación |
| `capital_per_grid_usd` | Margen (USD) asignado a CADA orden individual de la grilla, no al total |
| `invalidate_pct` | Si el precio sale del rango `[lower, upper]` por más de este % extra, el bot deja de operar ese símbolo |

## 6. Estructura del módulo

```
tradingbot/binance_config.py                 # Credenciales y parámetros de grilla por símbolo
tradingbot/strategies/grid_strategy.py       # Lógica pura: niveles de la grilla y detección de cruces
tradingbot/backtests/binance_grid_backtest.py # Backtest contra velas históricas públicas
tradingbot/bots/binance_grid_bot.py          # Bot en vivo (Testnet por defecto)
```

## Próximos pasos posibles

- Notificaciones (Telegram/email) en cada BUY/SELL o al invalidar una grilla
- Reinicio automático de la grilla tras invalidación (con confirmación manual)
- Trailing del rango en vez de invalidar y detener
- Solo después de mucha validación en testnet: evaluar cuenta real, bajando
  aún más el `leverage` inicial y el `capital_per_grid_usd`
