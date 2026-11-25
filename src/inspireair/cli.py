"""CLI InspireAir : show, validate, push, grab, import, export.

Sécurités actives dans toutes les commandes de push :
- headamp (trim d'entrée) et fader jamais envoyés ;
- gate toujours en dernier ;
- `--dry-run` pour prévisualiser sans émettre.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import DEFAULT_PORT, XAirClient, snapshot_to_preset_values
from .model import BLOCKS, Preset, PresetError
from .oscmap import channel_prefix, preset_to_osc
from .storage import load_preset, save_preset, schema_errors
from .xae_import import preset_to_chn_lines

SEPARATION = "  "


def _parse_blocks(raw: Optional[str]) -> set[str] | None:
    if not raw:
        return None
    blocks = {b.strip().lower() for b in raw.split(",") if b.strip()}
    unknown = blocks - set(BLOCKS)
    if unknown:
        raise SystemExit(f"bloc(s) inconnu(s) : {', '.join(sorted(unknown))} (attendus : {', '.join(BLOCKS)})")
    return blocks


def _print_preset(preset: Preset) -> None:
    print(f"Instrument : {preset.instrument}")
    print(f"Élément    : {preset.element}" + (f" ({preset.variant})" if preset.variant else ""))
    print(f"Style      : {preset.style}")
    if preset.tessiture:
        print(f"Tessiture  : {preset.tessiture}")
    print(f"Blocs      : {', '.join(sorted(preset.blocks())) or '(vide)'}")
    if preset.notes:
        print(f"Notes      : {preset.notes}")
    print()
    print(preset.describe())


def cmd_show(args: argparse.Namespace) -> int:
    preset = load_preset(args.path, validate=not args.lax)
    _print_preset(preset)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = schema_errors(args.path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    load_preset(args.path, validate=False).validated()
    print(f"{args.path} : preset valide.")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    preset = load_preset(args.path)
    blocks = _parse_blocks(args.blocks)
    items = preset_to_osc(preset, args.channel, blocks)
    if args.dry_run:
        print(f"[dry-run] {len(items)} messages vers {args.host} (canal {args.channel}) :")
        for address, value in items:
            print(f"{SEPARATION}{address} {value}")
        return 0
    client = XAirClient(args.host, port=args.port)
    if not args.assume_on and not client.ping():
        print(f"La console {args.host} ne répond pas (ping /info).", file=sys.stderr)
        return 1
    count = client.push(items)
    print(f"{count} messages envoyés vers {args.host} (canal {args.channel}).")
    if "gate" in (blocks or preset.blocks()):
        print("Gate envoyé en dernier ; vérifie le rendu avant de rejouer la tranche.")
    return 0


def cmd_grab(args: argparse.Namespace) -> int:
    client = XAirClient(args.host, port=args.port)
    prefix = channel_prefix(args.channel)
    results = client.capture(args.channel)
    values = snapshot_to_preset_values(results, prefix)
    preset = Preset.from_dict(
        {
            "instrument": "Capture",
            "element": f"Canal {args.channel}",
            "style": "Balance capturée",
            "notes": args.notes,
            **values,
        }
    ).validated()
    out = save_preset(preset, args.output, fmt=args.fmt)
    print(f"Tranche du canal {args.channel} aspirée → {out}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    from .xae_import import chn_to_preset_values, finalize_preset

    values = chn_to_preset_values(text, args.channel)
    if not values:
        print("Aucun paramètre exploitable trouvé (format de scène agrégée non supporté ?).", file=sys.stderr)
        return 1
    preset = finalize_preset(values)
    out = save_preset(preset, args.output, fmt=args.fmt)
    print(f"{args.path} importé → {out} ({', '.join(sorted(preset.blocks()))}).")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    preset = load_preset(args.path)
    lines = preset_to_chn_lines(preset.keep_blocks(_parse_blocks(args.blocks)), args.channel)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{args.path} exporté → {args.output} ({len(lines)} lignes OSC).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inspireair", description="Bibliothèque de presets X-Air")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="affiche un preset en langage humain")
    show.add_argument("path")
    show.add_argument("--lax", action="store_true", help="tolère les écarts de schéma")
    show.set_defaults(func=cmd_show)

    validate = sub.add_parser("validate", help="valide un preset contre le schéma")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_validate)

    push = sub.add_parser("push", help="applique un preset sur un canal de la console")
    push.add_argument("path")
    push.add_argument("--host", required=True, help="IP de la console")
    push.add_argument("--port", type=int, default=DEFAULT_PORT)
    push.add_argument("--channel", type=int, required=True, help="1-18")
    push.add_argument("--blocks", help="ex. hpf,eq,comp (défaut : tous les blocs du preset)")
    push.add_argument("--dry-run", action="store_true", help="prévisualise sans envoyer")
    push.add_argument("--assume-on", action="store_true", help="ne teste pas la console avec /info avant l'envoi")
    push.set_defaults(func=cmd_push)

    grab = sub.add_parser("grab", help="aspire la tranche courante du canal")
    grab.add_argument("--host", required=True)
    grab.add_argument("--port", type=int, default=DEFAULT_PORT)
    grab.add_argument("--channel", type=int, required=True)
    grab.add_argument("-o", "--output", required=True)
    grab.add_argument("--fmt", choices=("yaml", "json"), default="yaml")
    grab.add_argument("--notes", default="Capturée depuis la console")
    grab.set_defaults(func=cmd_grab)

    imp = sub.add_parser("import", help="convertit un .chn / .scn X-Air Edit en preset")
    imp.add_argument("path")
    imp.add_argument("--channel", type=int, default=1)
    imp.add_argument("-o", "--output", required=True)
    imp.add_argument("--fmt", choices=("yaml", "json"), default="yaml")
    imp.set_defaults(func=cmd_import)

    exp = sub.add_parser("export", help="exporte un preset en lignes OSC (.chn)")
    exp.add_argument("path")
    exp.add_argument("--channel", type=int, required=True)
    exp.add_argument("-o", "--output", required=True)
    exp.add_argument("--blocks")
    exp.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PresetError as exc:
        print(f"Preset invalide : {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"JSON invalide : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
