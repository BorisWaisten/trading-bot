"""
Lógica de Grid Trading: cálculo de niveles de precio y detección de qué
niveles se cruzaron entre una revisión y la siguiente.

Grid trading: se divide un rango de precios [lower, upper] en `grid_count`
niveles equiespaciados en % (geométrico — más adecuado para cripto que un
espaciado fijo en dólares, porque un mismo % de movimiento se comporta
igual en cualquier parte del rango). Cada vez que el precio cae hasta un
nivel sin posición ahí, se compra; cuando luego sube hasta el nivel
siguiente, se vende asegurando la ganancia de esa "celda", y el nivel
queda libre para volver a comprar si el precio vuelve a caer. Así se cobra
la volatilidad dentro del rango sin necesidad de acertar la dirección del
mercado.

El riesgo principal: si el precio rompe el rango y no vuelve (tendencia
fuerte en una dirección), la grilla deja de operar ese lado y las
posiciones abiertas quedan esperando — por eso existe `invalidate_pct` en
binance_config.py, que corta la operatoria en vez de perseguir el precio.

Este módulo es solo matemática/detección de cruces: no coloca órdenes ni
sabe nada de Binance ni de apalancamiento. Eso lo maneja cada script que
lo usa (binance_grid_bot.py para vivo, binance_grid_backtest.py para
histórico), cada uno con su propio manejo de posiciones y ejecución.
"""


def build_levels(lower: float, upper: float, grid_count: int) -> list:
    """Devuelve grid_count+1 niveles de precio, equiespaciados en % (geométrico),
    entre lower y upper (ambos incluidos), de menor a mayor."""
    if lower <= 0 or upper <= lower or grid_count < 1:
        raise ValueError("Rango de grilla inválido: se necesita 0 < lower < upper y grid_count >= 1")
    ratio = (upper / lower) ** (1 / grid_count)
    return [lower * (ratio ** i) for i in range(grid_count + 1)]


def find_crossings(levels: list, previous_price: float, current_price: float):
    """Índices de nivel cruzados entre previous_price y current_price, en el
    orden en que se cruzaron, junto con la dirección del movimiento.

    Devuelve (lista_de_indices, "up" | "down" | "flat").
    - "up": el precio subió; cada índice cruzado es candidato a SELL (si el
      nivel inmediatamente inferior tenía una posición comprada esperando).
    - "down": el precio bajó; cada índice cruzado es candidato a BUY (si ese
      nivel todavía no tiene posición y no es el techo de la grilla).
    """
    if current_price == previous_price:
        return [], "flat"

    if current_price > previous_price:
        crossed = [i for i, lvl in enumerate(levels) if previous_price < lvl <= current_price]
        return crossed, "up"

    crossed = [i for i, lvl in enumerate(levels) if current_price <= lvl < previous_price]
    crossed.reverse()
    return crossed, "down"
