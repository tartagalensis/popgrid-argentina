# CLAUDE.md

Mapas de bloques (block cartograms) de las provincias argentinas (10 censos, de 1895 a 2022) y de los departamentos de Salta (los 11 censos nacionales, de 1869 a 2022). Usa la librería [popgrid](https://github.com/databites-tech/popgrid) como dependencia y no la forkea. Docs y nombres del dominio en español.

## Comandos

```bash
uv sync --extra dev                                     # entorno
uv run pytest -q                                        # tests (sin red)
uv run ruff check . && uv run ruff format .             # lint / formato
uv run python scripts/descargar_limites.py              # IGN -> data/limites/
uv run python scripts/construir_censos.py               # INDEC -> provincias.csv, departamentos.csv
uv run python scripts/construir_salta_historico.py      # DGE Salta -> salta_historico.csv (necesita el anterior)
uv run python scripts/construir_provincias_historico.py # INDEC Cuadro 7 -> provincias_historico.csv (necesita provincias.csv)
uv run python scripts/generar_mapas.py <nivel> --modo todo   # nivel: provincias, salta, zonas:salta, zonas:argentina, departamentos:<prov>
uv run python scripts/grafico_serie.py <nivel>               # % por región y censo, en paneles chicos
```

En esta Mac el `python3` del PATH (`/Library/Frameworks/.../3.8`) falla con "Bad CPU type", y `/usr/bin/python3` es 3.9, que no alcanza (popgrid pide >=3.10). Usar siempre `uv run`.

## Arquitectura

- `src/popgrid_ar/config.py`: única fuente de rutas, códigos INDEC (`PROVINCIAS`, `DEPARTAMENTOS_SALTA`), departamentos excluidos, `CONTENIDOS` (Lezama y Tolhuin dentro de su departamento de origen en 2001 y 2010) y etiquetas cortas.
- `niveles.py`: **todo pasa por un `Nivel`** (`nivel("zonas:salta")`). Las claves son `provincias`, `departamentos:<prov>` (`salta` es atajo de `departamentos:66`), `zonas:<prov>` y `zonas:argentina`. `<prov>` acepta el código o el nombre. Un `Nivel` sabe sus regiones actuales (`nombres`), sus ausencias, el título, la unidad, el prefijo de archivos y la fuente. Las zonas tienen `base` (el nivel que agrupan) y `zonas_de` (el CSV en `data/zonas/`).
- **Zonas:** se agrupan en `censos._agrupar_zonas` (suma censo a censo; una fila compuesta no puede cruzar zonas) y en `mapas._limites_cache` (dissolve de los límites del nivel base). Son categorías analíticas propuestas, no oficiales, y se editan en los CSV.
- `limites.py`: descarga `ign:departamento` del WFS del IGN (campo `in1` = código INDEC de 5 dígitos, `nam` = nombre). Las provincias se arman con un **dissolve de departamentos antes de simplificar** (si se simplifica antes, quedan huecos).
- `censos.py`: CSV anchos. `provincias.csv` tiene `codigo,nombre,pob_AAAA...`; `departamentos.csv` (todo el país, 528 filas) agrega la columna `provincia`. El nivel `salta` lee `salta_historico.csv` (1869-2022).
  - **Filas compuestas:** un código como `66126+66056` (Orán + San Martín hasta 1947) representa un departamento que después se dividió. En los años en que tiene valor, sus partes van vacías. `validar` rechaza que una región quede contada dos veces en un mismo censo.
  - **Censo disponible:** cada región esperada está cubierta exactamente una vez, directamente o por una fila compuesta, salvo las ausencias declaradas en `config.AUSENCIAS_SALTA` (Los Andes en 1869 y 1895).
- `scripts/construir_salta_historico.py`: lee el cuadro 2.1.1 de la DGE Salta. Orán + San Martín viene en una fila *sin nombre* debajo de Orán. Controla sumas y que 2001-2022 coincida con el INDEC. El servidor de la DGE corta el TLS a veces (curl falla por el certificado; `requests` funciona) y el script reintenta.
- `scripts/construir_censos.py`: une los cuadros 2001-2010 (que no traen códigos) con los de 2022 (que sí) emparejando por la población de 2010, que figura en los dos. Las únicas celdas vacías son Lezama (06466) y Tolhuin (94011), creados después de 2010.
- `mapas.py`: `regiones_censo` arma las regiones de cada censo (une las geometrías de las filas compuestas y omite las regiones sin dato) y llama a `PopGrid.from_geodataframe(..., region_col="nombre", weight_col="pob_AAAA")`. Los colores se calculan una vez con las regiones actuales (`_colores`) y se pasan como `color_map` a todas las grillas; una fila compuesta toma el color de su primera parte. `comparar_censos` arma una grilla de hasta 4 columnas con `.draw(ax)` y agrupa en el pie las notas de cada censo.

## Reglas de datos

- **No inventar ni estimar cifras censales.** `data/censos/*.csv` lo generan `scripts/construir_censos.py` (INDEC) y `scripts/construir_salta_historico.py` (DGE Salta). Los enlaces están en `data/censos/FUENTES.md`. No editar a mano: si hay que corregir algo, corregir el script y regenerar.
- **Provincias 1895-1991:** `provincias_historico.csv` (`scripts/construir_provincias_historico.py`) tiene **porcentajes con un decimal**, del INDEC, Censo 2010, Tomo 1, Cuadro 7 (página 64 del PDF; se lee con `pypdf` en modo `layout`). Las columnas son `pct_AAAA`, no `pob_AAAA`. `cargar_censo("provincias")` une esta tabla con `provincias.csv`. Usar siempre `censos.columna(df, anio)` en vez de armar `f"pob_{anio}"`. Un valor 0 significa menos de 0,05% y no se dibuja. La población sin provincia asignada (1895 y 1914) está en `config.SIN_JURISDICCION_PCT`.
- Para sumar un censo hay que agregar la columna `pob_AAAA`, su fuente en el script y una fila en FUENTES.md.
- Las páginas del INDEC se cargan por JS. El listado real de cuadros del Censo 2022 está en `https://www.indec.gob.ar/Nivel4/Tema/2/41/165`, y el de 2010 por provincia en `/Nivel4/CensoProvincia/3/999/<cod_prov>/000/2010`.
- Los códigos INDEC son texto con ceros iniciales (`"02"`, `"06"`, `"66007"`). Leer siempre con `dtype={"codigo": str}`.
- Se excluyen los departamentos `94021` (Islas del Atlántico Sur) y `94028` (Antártida Argentina). Si no, su superficie domina el mapa de Tierra del Fuego.
- La suma de los departamentos de Salta debe ser igual al total de Salta en `provincias.csv` (lo verifica un test).
- `data/raw/` (~140 MB) no se versiona. `data/limites/*.geojson` sí, porque son livianos y reproducibles.

## Notas sobre popgrid

- `n=1000` hace que cada bloque valga el 0,1% del total. Con muchos departamentos chicos (La Poma, Molinos, Guachipas), `n=2000` les da más lugar.
- popgrid asigna colores según la geometría de las regiones que recibe. Si cambian las regiones (por ejemplo, Orán + San Martín), cambian también los colores de las vecinas. Por eso `mapas.py` fija los colores con `color_map`. Pasarle nombres que no están en la grilla genera un warning, así que se filtran antes.
- `plot()` devuelve una figura completa con título y fuente. `draw(ax)` dibuja solo el mapa.
- La shell de esta máquina es bash 3.2: conviene evitar comandos compuestos complejos.
