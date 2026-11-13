# CLAUDE.md

Mapas de bloques (block cartograms) de las provincias argentinas y de los departamentos de Salta, comparando los censos 2001, 2010 y 2022. Usa la librería [popgrid](https://github.com/databites-tech/popgrid) como dependencia y no la forkea. Docs y nombres del dominio en español.

## Comandos

```bash
uv sync --extra dev                                     # entorno
uv run pytest -q                                        # tests (sin red)
uv run ruff check . && uv run ruff format .             # lint / formato
uv run python scripts/descargar_limites.py              # IGN -> data/limites/
uv run python scripts/construir_censos.py               # INDEC -> data/censos/*.csv
uv run python scripts/generar_mapas.py salta --modo todo
```

En esta Mac el `python3` del PATH (`/Library/Frameworks/.../3.8`) falla con "Bad CPU type", y `/usr/bin/python3` es 3.9, que no alcanza (popgrid pide >=3.10). Usar siempre `uv run`.

## Arquitectura

- `src/popgrid_ar/config.py`: única fuente de rutas, códigos INDEC (`PROVINCIAS`, `DEPARTAMENTOS_SALTA`), departamentos excluidos y etiquetas cortas.
- `limites.py`: descarga `ign:departamento` del WFS del IGN (campo `in1` = código INDEC de 5 dígitos, `nam` = nombre). Las provincias se arman con un **dissolve de departamentos antes de simplificar** (si se simplifica antes, quedan huecos).
- `censos.py`: CSV anchos. `provincias.csv` tiene `codigo,nombre,pob_AAAA...`; `departamentos.csv` (todo el país, 528 filas) agrega la columna `provincia`. El nivel `salta` es `cargar_departamentos("66")`. Un censo cuenta como "disponible" solo si no tiene celdas vacías.
- `scripts/construir_censos.py`: une los cuadros 2001-2010 (que no traen códigos) con los de 2022 (que sí) emparejando por la población de 2010, que figura en los dos. Las únicas celdas vacías son Lezama (06466) y Tolhuin (94011), creados después de 2010.
- `mapas.py`: une límites y censo por `codigo` (validate 1:1) y llama a `AreaGrid` / `PopGrid.from_geodataframe(gdf, region_col="nombre", weight_col="pob_AAAA", n=...)`. `comparar_censos` usa `.draw(ax)` para armar subplots.

## Reglas de datos

- **No inventar ni estimar cifras censales.** `data/censos/*.csv` lo genera `scripts/construir_censos.py` desde los cuadros del INDEC (los enlaces están en `data/censos/FUENTES.md`). No editar a mano: si hay que corregir algo, corregir el script y regenerar.
- Para sumar un censo hay que agregar la columna `pob_AAAA`, su fuente en el script y una fila en FUENTES.md.
- Las páginas del INDEC se cargan por JS. El listado real de cuadros del Censo 2022 está en `https://www.indec.gob.ar/Nivel4/Tema/2/41/165`, y el de 2010 por provincia en `/Nivel4/CensoProvincia/3/999/<cod_prov>/000/2010`.
- Los códigos INDEC son texto con ceros iniciales (`"02"`, `"06"`, `"66007"`). Leer siempre con `dtype={"codigo": str}`.
- Se excluyen los departamentos `94021` (Islas del Atlántico Sur) y `94028` (Antártida Argentina). Si no, su superficie domina el mapa de Tierra del Fuego.
- La suma de los departamentos de Salta debe ser igual al total de Salta en `provincias.csv` (lo verifica un test).
- `data/raw/` (~140 MB) no se versiona. `data/limites/*.geojson` sí, porque son livianos y reproducibles.

## Notas sobre popgrid

- `n=1000` hace que cada bloque valga el 0,1% del total. Con muchos departamentos chicos (La Poma, Molinos, Guachipas), `n=2000` les da más lugar.
- Los colores se asignan a partir de la geometría, así que el mismo departamento conserva su color en todos los censos.
- `plot()` devuelve una figura completa con título y fuente. `draw(ax)` dibuja solo el mapa.
- La shell de esta máquina es bash 3.2: conviene evitar comandos compuestos complejos.
