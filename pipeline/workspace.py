"""Dossiers de travail par identifiant client, et état d'avancement du traitement.

L'identifiant vient d'un tableur, donc de l'extérieur : il est vérifié avant tout
usage, sans quoi il pourrait désigner un chemin hors du dossier de travail.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Étapes d'un traitement réussi, dans l'ordre.
STEPS = ("recue", "collecte", "tri", "organisation", "envoi", "prete")
FAILED = "echec"

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InvalidId(ValueError):
    """Identifiant de dossier refusé."""


def check_id(value):
    """Identifiant attendu : lettres, chiffres, tiret, souligné, 64 caractères au plus."""
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise InvalidId(
            "Identifiant attendu : 1 à 64 caractères parmi lettres, chiffres, tiret et souligné."
        )
    return value


def workspace(root, id):
    """Dossier de travail d'un client. Le nom vient de l'identifiant vérifié."""
    return Path(root) / check_id(id)


def create(root, id):
    """Crée l'arborescence de travail et renvoie son chemin."""
    folder = workspace(root, id)
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("images", "logos", "hotel"):
        (folder / name).mkdir(exist_ok=True)
    return folder


def now():
    return datetime.now(timezone.utc).isoformat()


def new_manifest(id, url):
    return {
        "schema_version": 1,
        "id": id,
        "source_url": url,
        "step": "recue",
        "started_at": now(),
        "updated_at": now(),
        "history": [],
        "counts": {},
        "error": None,
    }


def load(root, id):
    """Manifeste d'un dossier, ou None s'il n'a jamais été traité."""
    path = workspace(root, id) / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save(root, id, manifest):
    """Écriture atomique : un manifeste tronqué laisserait croire à un état faux."""
    folder = workspace(root, id)
    folder.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = now()
    handle, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, folder / "manifest.json")
    return manifest


def advance(root, id, manifest, step, detail=None, counts=None):
    """Fait passer le dossier à l'étape suivante et écrit l'état."""
    if step not in STEPS and step != FAILED:
        raise ValueError(f"Étape inconnue : {step}")
    manifest["step"] = step
    if counts:
        manifest["counts"].update(counts)
    manifest["history"].append({"step": step, "at": now(), "detail": detail})
    return save(root, id, manifest)


def fail(root, id, manifest, message):
    """Marque l'échec. Le dossier reste en place pour permettre le diagnostic."""
    manifest["error"] = str(message)
    return advance(root, id, manifest, FAILED, detail=str(message))
