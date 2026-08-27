"""
Monitoreo de bonos argentinos vía BYMA Open Data (librería NO OFICIAL,
comunidad: https://github.com/franco-lamas/PyOBD).

IMPORTANTE — limitaciones a tener en cuenta:
- Es una librería no oficial que consulta el sitio público de BYMA. Puede
  dejar de funcionar sin aviso si BYMA cambia su sitio o bloquea el acceso.
- Probado desde un servidor fuera de Argentina, devolvió error 403
  (Forbidden) — probablemente por protección anti-bot o geo-bloqueo.
  Desde tu conexión en Argentina puede funcionar distinto. Si a vos
  también te da error, esta fuente no es viable y hay que buscar otra.
- Los datos vienen con ~20 minutos de demora, no en tiempo real.

Instalación (no está en PyPI todavía, se instala desde GitHub):
    pip install git+https://github.com/franco-lamas/PyOBD --upgrade --no-cache-dir

Uso:
    python bond_monitor.py
"""
import json

import pandas as pd
from pyobd import BymaData, endpoints

# Bonos soberanos a trackear (riesgo país general)
SOVEREIGN_BONDS = ["GD30", "AL30", "GD35", "AL35", "GD38"]

# Palabras clave para identificar bonos corporativos (ON) de YPF dentro
# del panel completo de bonos corporativos que devuelve la librería
YPF_KEYWORDS = ["YPF", "YPFD", "YCA", "YMC"]


def _is_text_column(series):
    # pandas 3.x usa el dtype "str" para columnas de texto en vez de
    # "object", así que hay que chequear ambos casos
    return series.dtype == object or pd.api.types.is_string_dtype(series)


def get_sovereign_bonds_summary():
    """Trae los bonos soberanos y calcula la variación promedio del panel.

    client.get_government_bonds() de pyobd tiene dos bugs: (1) ignora el
    parámetro que se le pasa y siempre pide T1=False, T0=False, con lo
    cual BYMA devuelve 0 resultados; y (2) el panel completo viene
    paginado (6 páginas) y la librería solo trae la primera. Acá pegamos
    directo al endpoint pidiendo T0/T1/T2 en True y recorriendo todas
    las páginas.
    """
    client = BymaData()
    all_rows = []
    page = 1
    while True:
        payload = json.dumps(
            {
                "T2": True,
                "T1": True,
                "T0": True,
                "page_number": page,
                "Content-Type": "application/json",
            }
        )
        response = client.session.post(endpoints.PUBLIC_BONDS, data=payload)
        body = json.loads(response.text)
        rows = body.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        page_count = body.get("content", {}).get("page_count", 1)
        if page >= page_count:
            break
        page += 1

    df = pd.DataFrame(all_rows)

    # Filtramos solo los símbolos que nos interesan, si están presentes
    if "symbol" in df.columns:
        filtered = df[df["symbol"].isin(SOVEREIGN_BONDS)]
    else:
        filtered = df  # si la columna tiene otro nombre, mostramos todo para inspeccionar

    return filtered


def get_ypf_corporate_bonds():
    """Trae los bonos corporativos y filtra los que parecen ser de YPF."""
    client = BymaData()
    df = client.get_corporate_bonds()

    # Buscamos por nombre/símbolo que contenga alguna palabra clave de YPF
    text_columns = [c for c in df.columns if _is_text_column(df[c])]
    mask = False
    for col in text_columns:
        for kw in YPF_KEYWORDS:
            mask = mask | df[col].astype(str).str.contains(kw, case=False, na=False)

    return df[mask] if not isinstance(mask, bool) else df


if __name__ == "__main__":
    print("=== Bonos soberanos ===")
    try:
        sov = get_sovereign_bonds_summary()
        print(sov)
    except Exception as e:
        print(f"Error obteniendo bonos soberanos: {e}")

    print("\n=== Bonos corporativos de YPF (Obligaciones Negociables) ===")
    try:
        ypf_bonds = get_ypf_corporate_bonds()
        print(ypf_bonds)
    except Exception as e:
        print(f"Error obteniendo bonos corporativos: {e}")
