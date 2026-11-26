"""CLI InspireAir : show, validate, push, grab, import, export, undo, compare, kit.

Sécurités actives dans toutes les commandes de push :
- headamp (trim d'entrée) et fader jamais envoyés ;
- gate toujours en dernier ;
- état du canal sauvegardé avant chaque envoi (undo) ;
- `--dry-run` pour prévisualiser sans émettre.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import DEFAULT_PORT, XAirClient, XAirError
from .kit import load_kit
from .model import BLOCKS, Preset, PresetError
from .oscmap import channel_prefix, preset_to_osc, snapshot_to_preset_values
from .snapshot import capture_snapshot, compare_preset, restore_items, undo_path
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
    if not args.no_undo:
        try:
            undo_file = capture_snapshot(client, args.channel)
        except XAirError as exc:
            print(f"Capture du snapshot undo impossible ({exc}) — push annulé par sécurité.", file=sys.stderr)
            return 1
        print(f"Undo sauvegardé : {undo_file}")
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
            "instrument": args.instrument,
            "element": args.element or f"Canal {args.channel}",
            "style": args.style,
            "variant": args.variant,
            "tessiture": args.tessiture,
            "notes": args.notes,
            **values,
        }
    ).validated()
    out = save_preset(preset, args.output, fmt=args.fmt)
    print(f"Tranche du canal {args.channel} aspirée → {out}")
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    path = undo_path(args.channel)
    if not path.exists():
        print(f"Aucun snapshot undo pour le canal {args.channel} ({path}).", file=sys.stderr)
        return 1
    items = restore_items(path, args.channel)
    if args.dry_run:
        print(f"[dry-run] {len(items)} messages pour restaurer le canal {args.channel} :")
        for address, value in items:
            print(f"{SEPARATION}{address} {value}")
        return 0
    client = XAirClient(args.host, port=args.port)
    if not args.assume_on and not client.ping():
        print(f"La console {args.host} ne répond pas (ping /info).", file=sys.stderr)
        return 1
    count = client.push(items)
    print(f"Canal {args.channel} restauré depuis {path} ({count} messages).")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    preset = load_preset(args.path)
    client = XAirClient(args.host, port=args.port)
    if not args.assume_on and not client.ping():
        print(f"La console {args.host} ne répond pas (ping /info).", file=sys.stderr)
        return 1
    replies = client.capture(args.channel)
    diffs = compare_preset(preset, replies, args.channel, _parse_blocks(args.blocks))
    if not diffs:
        print(f"Canal {args.channel} conforme à {args.path} (tolérance : demi-cran console).")
        return 0
    print(f"Canal {args.channel} ≠ {args.path} ({len(diffs)} écart(s) au-delà d'un demi-cran) :")
    for diff in diffs:
        print(f"{SEPARATION}{diff}")
    return 1


def cmd_kit(args: argparse.Namespace) -> int:
    plan = load_kit(Path(args.path))
    blocks = _parse_blocks(args.blocks)
    if args.dry_run:
        total = 0
        for channel, preset in plan:
            count = len(preset_to_osc(preset, channel, blocks))
            total += count
            print(f"[dry-run] canal {channel} ← {preset.instrument}/{preset.element} ({count} messages)")
        print(f"[dry-run] {len(plan)} canaux, {total} messages vers {args.host}.")
        return 0
    client = XAirClient(args.host, port=args.port)
    if not args.assume_on and not client.ping():
        print(f"La console {args.host} ne répond pas (ping /info).", file=sys.stderr)
        return 1
    total = 0
    for channel, preset in plan:
        undo_file = capture_snapshot(client, channel)
        count = client.push(preset_to_osc(preset, channel, blocks))
        total += count
        print(f"canal {channel} ← {preset.instrument}/{preset.element} : {count} messages (undo : {undo_file})")
    print(f"Kit complet : {total} messages sur {len(plan)} canaux.")
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
    push.add_argument("--no-undo", action="store_true", help="ne sauvegarde pas l'état du canal avant l'envoi (déconseillé)")
    push.set_defaults(func=cmd_push)

    grab = sub.add_parser("grab", help="aspire la tranche courante du canal")
    grab.add_argument("--host", required=True)
    grab.add_argument("--port", type=int, default=DEFAULT_PORT)
    grab.add_argument("--channel", type=int, required=True)
    grab.add_argument("-o", "--output", required=True)
    grab.add_argument("--fmt", choices=("yaml", "json"), default="yaml")
    grab.add_argument("--notes", default="Capturée depuis la console")
    grab.add_argument("--instrument", default="Capture", help="section taxonomie (ex. Batterie)")
    grab.add_argument("--element", default=None, help="élément (défaut : Canal N)")
    grab.add_argument("--style", default="Balance capturée", help="caractère (ex. Funk sec)")
    grab.add_argument("--variant", default=None, help="variante (ex. Top, Top+Bottom)")
    grab.add_argument("--tessiture", default=None, choices=("Homme", "Femme"))
    grab.set_defaults(func=cmd_grab)

    und = sub.add_parser("undo", help="restaure l'état du canal sauvegardé avant le dernier push")
    und.add_argument("--host", required=True)
    und.add_argument("--port", type=int, default=DEFAULT_PORT)
    und.add_argument("--channel", type=int, required=True)
    und.add_argument("--dry-run", action="store_true")
    und.add_argument("--assume-on", action="store_true")
    und.set_defaults(func=cmd_undo)

    cmp = sub.add_parser("compare", help="compare un preset à l'état réel du canal")
    cmp.add_argument("path")
    cmp.add_argument("--host", required=True)
    cmp.add_argument("--port", type=int, default=DEFAULT_PORT)
    cmp.add_argument("--channel", type=int, required=True)
    cmp.add_argument("--blocks")
    cmp.add_argument("--assume-on", action="store_true")
    cmp.set_defaults(func=cmd_compare)

    kit = sub.add_parser("kit", help="applique un kit multi-canaux (undo par canal)")
    kit.add_argument("path", help="fichier kit (clée 'entries')")
    kit.add_argument("--host", required=True)
    kit.add_argument("--port", type=int, default=DEFAULT_PORT)
    kit.add_argument("--blocks")
    kit.add_argument("--dry-run", action="store_true")
    kit.add_argument("--assume-on", action="store_true")
    kit.set_defaults(func=cmd_kit)

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
    except XAirError as exc:
        print(f"Erreur console : {exc}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Fichier illisible : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
