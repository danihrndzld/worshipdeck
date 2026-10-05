# worshipdeck

Genera la presentación del culto dominical (PPTX) a partir de una foto del flyer de la semana.
Corre tesseract sobre la imagen, saca los himnos de `data/hymnal.json` (Himnario Corazón y Vida,
412 himnos) y las canciones de `reference/song-library/`, y clona las slides de
`reference/style-template.pptx`, así que el fondo, las fuentes y el logo salen idénticos a los de
una deck real.

Es el port a programa de la skill [`worship-deck-builder`](https://github.com/danihrndzld/worship-deck-builder):
el builder es el mismo y lo nuevo es el paso imagen → spec, que antes hacía el agente.

## Uso

```bash
brew install tesseract   # más spa.traineddata en $(brew --prefix)/share/tessdata
uv sync

# flyer → deck en un paso (deja el spec junto a la deck para revisarlo)
uv run worshipdeck make flyer.jpg \
  --sermon-lead "Sed por la" --sermon-title "Presencia de Dios" \
  --passage "Salmos 42:1-2 & 63:1-3"

# o en dos pasos: revisa/edita el spec y después construye
uv run worshipdeck parse flyer.jpg -o semana.json
uv run worshipdeck build --spec semana.json
```

Sin `-o`, la deck se llama como el domingo siguiente (`OCTUBRE 11.pptx`).
`examples/flyer.example.png` reproduce las 72 slides del 6 de septiembre.

### Qué entiende del flyer

| Línea del flyer | Resultado |
|---|---|
| `Himno 64`, `H. 64`, `#64` | himno 64 del himnario |
| `Al estar ante Ti` | canción de `reference/song-library/` (match difuso, sin acentos) |
| `Jehová es mi pastor` (sin número) | himno por título |
| `Salmos 42:1-2 & 63:1-3` | slides de pasaje con el texto RVR1960 de `data/rvr1960.json` |
| cualquier otra cosa | `_pendientes` en el spec y aviso en stderr |

### Cuando el OCR no entiende

Si una línea sale con confianza menor a 60 %, no coincide con nada, o hay texto que tesseract
no devolvió (una zona con tinta que ningún bloque de OCR cubre), `parse`/`make` abre el recorte de
esa zona y pregunta en la terminal:

```
? Aquí hay texto que no pude leer
  recorte: flyer-dudas/02.png
  Escribe el texto correcto · Enter = dejarlo así · - = no es parte del culto
  > Himno 83
```

El texto escrito se vuelve a evaluar al momento, y si sigue sin coincidir pregunta otra vez.
Con `--no-ask`, o si la entrada no es una terminal, no pregunta: las líneas quedan en
`_pendientes` del spec con su `conf`, su `box` y la ruta del recorte (`--crops` cambia la carpeta).

El flyer casi nunca trae la prédica: pásala con `--sermon-title` / `--passage`.
Un pasaje entra en grupos de hasta 6 líneas por slide; si el `scripture` del spec no trae
`chunks`, `build` los saca de la Biblia. Una canción que cae en `_pendientes` falta en la biblioteca; agrégala con `worshipdeck song add`
o mina una deck vieja con `worshipdeck song import-deck --deck VIEJA.pptx`.

### App web

```bash
uv run flask --app worshipdeck.web run --port 5077   # http://127.0.0.1:5077
```

La misma secuencia en el navegador, pensada para el teléfono: subir el flyer (el OCR corre en el
navegador con tesseract.js), corregir las líneas dudosas viendo su recorte, ordenar el culto, prédica,
lecturas, vista previa y descarga del `.pptx`. Incluye la biblioteca de canciones, la importación desde
un `.pptx` viejo y el PDF de letras. El frontend es JS plano en `web/`, sin build; la API está en
`worshipdeck/web.py`. En Vercel (`api/index.py`, `vercel.json`) la biblioteca es de solo lectura.

### Otros comandos (los mismos de la skill)

```bash
uv run worshipdeck hymn --page 83                    # ver un himno parseado
uv run worshipdeck insert --spec lecturas.json       # meter lecturas en una deck ya editada
uv run worshipdeck song list
uv run worshipdeck letras --deck "OCTUBRE 3.pptx" --reviewed   # PDF de letras, solo tras revisión
```

El formato del spec, las reglas de chunking y las convenciones del operador están en
`reference/slide-types.md` y en el SKILL.md de la skill original.

## Datos

| Archivo | Qué es |
|---|---|
| `reference/style-template.pptx` | deck del 6 de septiembre de 2026, fuente de estilo |
| `reference/decks/` | decks reales de referencia (AGOSTO 30, SEPTIEMBRE 6); se suman las nuevas |
| `reference/hymnal.pdf` | Himnario Corazón y Vida (la página N es el himno N) |
| `data/hymnal.json` | el himnario parseado; se regenera con `tools/extract_hymnal.py` |
| `data/rvr1960.json` | Reina-Valera 1960 (31 104 versículos, de [mrk214/bible-data-es-spa](https://github.com/mrk214/bible-data-es-spa)); se regenera con `tools/extract_bible.py` |
| `reference/song-library/` | una canción contemporánea por JSON, minadas de las decks |

## Tests

```bash
uv run ruff check .   # estático
uv run pytest         # 144 tests en ~5 s: unit, integración y e2e (sin el render de LibreOffice)
```

La estrategia (Testing Trophy), la técnica de diseño detrás de cada prueba y los mutantes que la
suite mata están en [`tests/README.md`](tests/README.md). CI corre estático → unit + integración → e2e.

## Deploy (pendiente)

El OCR está aislado en `worshipdeck/flyer.py:ocr()`. Para Vercel gratis, el plan es correr
tesseract.js en el navegador y mandar el texto a una función Python que llama
`make_spec()` y `build()`; así el servidor no necesita el binario de tesseract.
