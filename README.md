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
| `Salmos 42:1-2 & 63:1-3` | slides de pasaje (el texto RV1960 se pega a mano) |
| cualquier otra cosa | `_pendientes` en el spec y aviso en stderr |

El flyer casi nunca trae la prédica: pásala con `--sermon-title` / `--passage`.
Una canción que cae en `_pendientes` falta en la biblioteca; agrégala con `worshipdeck song add`
o mina una deck vieja con `worshipdeck song import-deck --deck VIEJA.pptx`.

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
| `reference/song-library/` | una canción contemporánea por JSON, minadas de las decks |

## Tests

```bash
for t in tests/test_*.py; do uv run python $t; done
```

## Deploy (pendiente)

El OCR está aislado en `worshipdeck/flyer.py:ocr()`. Para Vercel gratis, el plan es correr
tesseract.js en el navegador y mandar el texto a una función Python que llama
`make_spec()` y `build()`; así el servidor no necesita el binario de tesseract.
