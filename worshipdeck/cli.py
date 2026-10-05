"""worshipdeck CLI.

  worshipdeck make flyer.jpg --sermon-title Esperanza --passage "Salmos 1:1-3"
  worshipdeck parse flyer.jpg -o spec.json     # OCR + parse only, review, then:
  worshipdeck build --spec spec.json
  worshipdeck hymn --page 64 | insert | song ...   (same as the skill's builder)
  worshipdeck letras --deck reviewed.pptx --reviewed
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from worshipdeck import builder, flyer, lyrics_pdf


def add_flyer_args(p):
    p.add_argument("source", help="flyer image (png/jpg) or, with --text, a .txt with the song list")
    p.add_argument("--text", action="store_true", help="source is already text (skip OCR)")
    p.add_argument("--sermon-title", help='big word of the prédica, e.g. "Esperanza"')
    p.add_argument("--sermon-lead", default="El tema de hoy")
    p.add_argument("--passage", help='prédica passage, e.g. "Salmos 42:1-2 & 63:1-3"')
    p.add_argument("--hymnal", help="defaults to data/hymnal.json")
    p.add_argument("--no-ask", action="store_true",
                   help="don't ask about doubtful OCR lines; list them in _pendientes with a crop")
    p.add_argument("--crops", help="folder for the crops of doubtful lines (default: <image>-dudas/)")
    p.add_argument("--library", help="legacy song-library.json (the reference/song-library/ folder is always read)")


def describe(items):
    return ", ".join(f"Himno {i['himno']}" if i["op"] == "hymn" else
                     f"canción {i['key']}" if i["op"] == "song" else
                     f"{i['book']} {i['range']}" for i in items)


def make_asker(image, crop_dir):
    """Ask in the terminal about each doubtful OCR line, opening its crop."""
    seen = {}

    def ask(rec, line, found):
        if id(rec) not in seen:
            crop_dir.mkdir(parents=True, exist_ok=True)
            seen[id(rec)] = flyer.crop_line(image, rec["box"], crop_dir / f"{len(seen) + 1:02}.png")
            if sys.platform == "darwin":
                subprocess.run(["open", seen[id(rec)]], check=False)
            if not rec["text"]:
                print("\n? Aquí hay texto que no pude leer", file=sys.stderr)
            else:
                why = (f"confianza {rec['conf']}%" if rec["conf"] < flyer.MIN_CONF else "no coincide con nada")
                print(f"\n? No entendí bien esta línea ({why}): «{line}»", file=sys.stderr)
            print(f"  recorte: {seen[id(rec)]}", file=sys.stderr)
        else:
            print(f"  «{line}» sigue sin coincidir con un himno, canción o pasaje", file=sys.stderr)
        if found:
            print(f"  coincide con: {describe(found)}", file=sys.stderr)
        print("  Escribe el texto correcto · Enter = dejarlo así · - = no es parte del culto", file=sys.stderr)
        try:
            answer = input("  > ")
        except EOFError:  # Ctrl-D: stop asking, leave the line in _pendientes
            print(file=sys.stderr)
            return ""
        return None if answer.strip() == "-" else answer

    return ask


def spec_from_args(args, output):
    if args.text:
        lines, ask = Path(args.source).read_text(encoding="utf-8"), None
    else:
        lines = flyer.ocr_lines(args.source)
        crop_dir = Path(args.crops or f"{Path(args.source).stem}-dudas")
        interactive = sys.stdin.isatty() and not args.no_ask
        ask = make_asker(args.source, crop_dir) if interactive else None
    spec = flyer.make_spec(lines, output, args.sermon_title, args.sermon_lead,
                           args.passage, args.hymnal, args.library, ask)
    for n, p in enumerate(q for q in spec.get("_pendientes", []) if isinstance(q, dict)):
        crop_dir.mkdir(parents=True, exist_ok=True)
        p["crop"] = flyer.crop_line(args.source, p["box"], crop_dir / f"pendiente-{n + 1:02}.png")
    for w in flyer.warnings(spec):
        print(f"! {w}", file=sys.stderr)
    return spec


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("build", "insert", "hymn", "song"):
        sys.argv = ["worshipdeck", *argv]
        return builder.main()
    if argv and argv[0] == "letras":
        sys.argv = ["worshipdeck letras", *argv[1:]]
        return lyrics_pdf.main()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("parse", help="flyer -> build spec JSON (review it before building)")
    add_flyer_args(p)
    p.add_argument("-o", "--spec-out", help="write the spec here (default: stdout)")
    p.add_argument("--output", help="deck filename inside the spec (default: next Sunday, e.g. 'OCTUBRE 11.pptx')")
    m = sub.add_parser("make", help="flyer -> deck in one step (writes the spec next to the deck)")
    add_flyer_args(m)
    m.add_argument("-o", "--output", help="deck path (default: next Sunday, e.g. 'OCTUBRE 11.pptx')")
    for name in ("build", "insert", "hymn", "song", "letras"):
        sub.add_parser(name, help=f"see `worshipdeck {name} --help`", add_help=False)
    args = parser.parse_args(argv)

    spec = spec_from_args(args, args.output)
    if args.command == "parse":
        text = json.dumps(spec, ensure_ascii=False, indent=2)
        if args.spec_out:
            Path(args.spec_out).write_text(text + "\n", encoding="utf-8")
            print(f"wrote {args.spec_out}", file=sys.stderr)
        else:
            print(text)
        return 0

    spec_path = Path(spec["output"]).with_suffix(".spec.json")
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {spec_path}", file=sys.stderr)
    builder.build(str(spec_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
