# Zonas: agrupaciones analíticas

Cada archivo agrupa las regiones de un nivel en zonas. Se usan como nivel de análisis
propio (`zonas:<nombre>`): mapa de bloques, serie y tabla, igual que provincias o
departamentos.

| Archivo | Agrupa | Nivel | Censos |
|---|---|---|---|
| `salta.csv` | los 23 departamentos de Salta | `zonas:salta` | 1869-2022 |
| `argentina.csv` | las 24 provincias | `zonas:argentina` | 1895-2022 |

Formato: `codigo,<nombre de la región>,zona`. El código es el INDEC del departamento
(5 dígitos) o de la provincia (2). Cada región va en una sola zona, y todas las
regiones del nivel tienen que estar. El orden de las zonas en el archivo es el orden
en los gráficos.

Para agregar una provincia, creá `<provincia>.csv` con sus departamentos
(por ejemplo `jujuy.csv`) y usá `zonas:jujuy`.

## Son propuestas, no divisiones oficiales

**`salta.csv`** es una regionalización geográfica propuesta para este proyecto:

| Zona | Departamentos |
|---|---|
| Capital | Capital |
| Valle de Lerma | Cerrillos, Rosario de Lerma, Chicoana, La Caldera |
| Valles Calchaquíes | Cachi, Molinos, San Carlos, Cafayate |
| Puna | Los Andes, La Poma |
| Norte andino | Santa Victoria, Iruya |
| Noreste | Orán, General José de San Martín, Rivadavia |
| Centro-sur | General Güemes, Anta, Metán, Rosario de la Frontera, La Candelaria, Guachipas, La Viña |

En 1869 y 1895 la Puna está, pero sin Los Andes (que se anexó a Salta en 1943).
Los gráficos lo aclaran.

**`argentina.csv`** sigue las regiones habituales (NOA, NEA, Cuyo, Pampeana,
Patagonia) con CABA aparte. A diferencia de la regionalización del INDEC, no separa
los 24 partidos del Gran Buenos Aires: esa región "Metropolitana" necesita datos por
partido, que solo existen desde 2001. La provincia de Buenos Aires va entera en Pampeana.
