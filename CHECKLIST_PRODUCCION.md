# Checklist: ¿Listo para pasar a cuenta real?

No es un trámite — es la diferencia entre plata simulada y plata real.
Ningún ítem es obligatorio por sí solo, pero cuantos menos tenés tildados,
más alto es el riesgo de una sorpresa cara.

## 1. Tiempo y estabilidad técnica

- [ ] El bot corrió en Railway **al menos 3-4 semanas seguidas** sin
      caerse ni necesitar que lo reinicies a mano
- [ ] Pasó por **al menos un fin de semana y un feriado de EE.UU.**
      sin errores (el chequeo de horario de mercado se comportó bien)
- [ ] Revisaste `trading_bot.log` completo al menos una vez por semana,
      no solo cuando te acordás
- [ ] No hay errores repetidos o silenciosos en el log (ej. el mismo
      error todos los días que "se banca" pero nunca se resuelve)
- [ ] El Volume de Railway efectivamente persistió el estado después
      de al menos un redeploy (lo confirmaste, no lo asumiste)

## 2. Comportamiento de la estrategia

- [ ] Viste al bot completar **al menos 3-4 ciclos completos**
      (compra → venta por take-profit o stop-loss → nueva compra) en
      cada símbolo, no solo una compra inicial
- [ ] Las compras/ventas que ejecutó tienen sentido comparado con lo
      que esperabas mirando el precio real de YPF/VIST ese día
- [ ] El semáforo macro bloqueó o permitió compras de forma coherente
      (no en rojo todo el tiempo, no en verde todo el tiempo sin razón)
- [ ] No viste ningún comportamiento "raro": comprar y vender el mismo
      día en loop, posiciones que no coinciden con lo que loggeó,
      montos que no cierran

## 3. Expectativas de resultado

- [ ] Sabés que **los backtests dieron resultados mixtos** (perdió
      contra buy & hold en AAPL, YPF, y VIST en el período largo) y
      vas con eso claro, no con la expectativa de que va a repetir el
      +200% que vimos en un backtest de un período específico
- [ ] Tenés un número en mente de **cuánto estás dispuesto a perder**
      con este capital sin que te cambie el humor o las decisiones de
      otras partes de tu vida financiera
- [ ] Ese capital es dinero que **no necesitás** en el corto/mediano
      plazo (no es el fondo de emergencia, no es plata comprometida)

## 4. Operativo y legal

- [ ] Confirmaste cómo se trata impositivamente ganar o perder plata
      operando ADRs en EE.UU. siendo residente fiscal argentino (con
      un contador, no con lo que dijimos acá — nunca lo confirmamos)
- [ ] Sabés cómo vas a mover pesos a dólares y de ahí a tu cuenta de
      Alpaca (MEP/CCL, con qué bróker, qué costos tiene ese paso)
- [ ] Tenés un plan simple para si tenés que frenar el bot de urgencia
      (sabés entrar a Railway, pausar el servicio, o cerrar posiciones
      manualmente desde el dashboard de Alpaca)

## Una guía simple

- **0-4 tildados**: seguí en paper trading, todavía es pronto
- **5-9 tildados**: podés considerar empezar con un capital chico,
  simbólico, no el monto completo que tenías pensado
- **10-13 tildados**: tenés una base razonable para decidir por tu
  cuenta, con los ojos abiertos

Esto no reemplaza tu propio criterio — es una forma de que la decisión
sea "porque ya lo evalué" y no "porque ya cobré".
