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
python backtest.py
```

Esto descarga precios históricos, corre la estrategia y compara el resultado
contra simplemente "comprar y mantener" (buy & hold). **Corré esto primero y
ajustá los parámetros hasta que el resultado te convenza.**

## 4. Paper trading (dinero simulado, en vivo)

```bash
python bot.py
```

El bot va a revisar el símbolo configurado periódicamente y ejecutar compras/
ventas simuladas según la señal. Podés ver el estado de tu cuenta y las
operaciones en el dashboard de Alpaca (sección Paper Trading).

## 5. Parámetros ajustables

Todo se configura en `config.py`:

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
├── config.py       # Configuración y credenciales
├── strategy.py      # Lógica de la estrategia (SMA crossover)
├── backtest.py       # Prueba histórica sin riesgo
├── bot.py            # Bot de paper trading en vivo
├── requirements.txt
└── .env.example
```

## Próximos pasos posibles

- Agregar más símbolos (portafolio en vez de un solo ticker)
- Probar otras estrategias (RSI, bandas de Bollinger, momentum)
- Añadir notificaciones (Telegram/email) cuando se ejecuta una orden
- Desplegar el bot en un servidor (ej. una VM pequeña) para que corra 24/7
- Solo después de mucha validación: evaluar migrar a cuenta real, cambiando
  `ALPACA_BASE_URL` en `config.py` — con pleno entendimiento del riesgo
