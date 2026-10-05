"""worshipdeck CLI.

  worshipdeck make flyer.jpg --sermon-title Esperanza --passage "Salmos 1:1-3"
  worshipdeck parse flyer.jpg -o spec.json     # OCR + parse only, review, then:
  worshipdeck build --spec spec.json
  worshipdeck hymn --page 64 | insert | song ...   (same as the skill's builder)
  worshipdeck letras --deck reviewed.pptx --reviewed
"""
import argparse
import json
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
    p.add_argument("--library", help="legacy song-library.json (the reference/song-library/ folder is always read)")


def spec_from_args(args, output):
    text = Path(args.source).read_text(encoding="utf-8") if args.text else flyer.ocr(args.source)
    spec = flyer.make_spec(text, output, args.sermon_title, args.sermon_lead,
                           args.passage, args.hymnal, args.library)
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
