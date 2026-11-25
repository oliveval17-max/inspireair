"""Chargement / sauvegarde des presets (JSON ou YAML) et validation par schéma."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml
from jsonschema import Draft202012Validator

from .model import Preset

SCHEMA_PATH = Path(__file__).parent / "schema" / "inspireair-preset.schema.json"


def load_raw(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} : contenu de preset invalide (objet attendu)")
    return data


def load_preset(path: str | Path, validate: bool = True) -> Preset:
    data = load_raw(path)
    preset = Preset.from_dict(data)
    if validate:
        schema_errors(path, data)
    return preset.validated()


def save_preset(preset: Preset, path: str | Path, fmt: str = "yaml") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = preset.to_dict()
    text = (
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        if fmt.lower() in ("yaml", ".yml")
        else json.dumps(data, ensure_ascii=False, indent=2)
    )
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def schema_errors(path: str | Path, data: Optional[dict[str, Any]] = None) -> list[str]:
    """Renvoie les erreurs de schéma (liste vide si le preset est valide)."""
    if data is None:
        data = load_raw(path)
    return [
        f"{path} : {list(error.absolute_path) or '<racine>'} — {error.message}"
        for error in sorted(_validator().iter_errors(data), key=lambda e: e.path)
    ]
