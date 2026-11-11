"""Publication du dossier client sur Cloudflare R2, puis libération de la machine.

Deux règles gouvernent ce module.

1. Rien n'est supprimé avant que l'envoi soit confirmé. Un dossier effacé trop tôt,
   c'est une collecte entière à refaire : on envoie d'abord, on efface ensuite.
2. Seuls les fichiers lourds sont effacés après envoi. Les JSON partent aussi, mais
   restent en local : le studio les lit directement et ils ne pèsent rien.

L'adresse publique d'un média se déduit de son nom : elle ne dépend pas de l'envoi,
si bien que le document du studio peut la référencer avant même la publication.

Le lien remis au client suit le même principe : il ne porte qu'un identifiant, et
c'est cet identifiant qui désigne le dossier du compartiment. Les JSON partent donc
aussi sur R2 — sans être effacés — puisque la page de bienvenue les lit par ce lien.

Le client du compartiment n'est construit qu'au moment de l'envoi : le reste du
paquet reste importable sans boto3, sans clé et sans réseau.
"""

import json
import os
import urllib.request
from pathlib import Path

# Préfixe des objets dans le compartiment, aligné sur celui de Sacha.
PREFIX = "demos"

# Sous-dossiers envoyés puis effacés. Le reste (hotel/, manifest.json) reste local.
MEDIA_FOLDERS = ("images", "logos")

# Sous-dossier envoyé mais conservé : la page de démonstration le lit par le lien.
DOCUMENTS_FOLDER = "hotel"

# Adresse publique de la page de démonstration remise au client.
DEMO_BASE_DEFAULT = "https://demo.pierre-ai.com"

# Variables d'environnement exigées pour l'envoi.
REQUIRED = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
)

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


class PublishError(RuntimeError):
    """Envoi impossible : configuration absente ou dépendance manquante."""


def public_base():
    """Adresse publique de lecture du compartiment, ou chaîne vide si non configurée."""
    return os.environ.get("R2_PUBLIC_BASE", "").rstrip("/")


def object_key(id, file, kind):
    """Clé de l'objet dans le compartiment : prévisible, donc connue avant l'envoi."""
    return f"{PREFIX}/{id}/{kind}/{file}"


def demo_base():
    """Adresse publique de la page de démonstration, sans barre oblique finale."""
    return os.environ.get("DEMO_BASE", DEMO_BASE_DEFAULT).rstrip("/")


def demo_url(id):
    """Lien remis au client : l'identifiant est le paramètre de la ressource R2.

    Le même identifiant sert de nom de dossier sur le compartiment : la page de
    démonstration retrouve donc seule les photos et le contenu du site.
    """
    return f"{demo_base()}/{id}"


def sheet_payload(id):
    """Ligne renvoyée à Google Sheets en fin de traitement."""
    return {"ID": id, "lien demo": demo_url(id)}


def media_url(id, file, kind):
    """Adresse publique d'un média, calculée et jamais devinée par l'appelant.

    Sans adresse publique configurée, on renvoie le chemin de la clé : la valeur
    reste exploitable et le jour de la configuration, elle devient une URL pleine.
    """
    key = object_key(id, file, kind)
    base = public_base()
    return f"{base}/{key}" if base else f"/{key}"


def client(environ=None, s3=None):
    """Client du compartiment. boto3 n'est chargé qu'ici, là où il sert."""
    if s3 is not None:
        return s3
    environ = environ or os.environ
    missing = [name for name in REQUIRED if not environ.get(name)]
    if missing:
        raise PublishError("Configuration R2 incomplète : " + ", ".join(missing))
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:  # pragma: no cover - dépendance absente de l'installation
        raise PublishError("boto3 est requis pour publier (pip install boto3).") from error
    account = environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def put(bucket, key, path, s3):
    """Envoie un fichier avec son type de contenu, déduit de l'extension."""
    path = Path(path)
    s3.upload_file(
        str(path),
        bucket,
        key,
        ExtraArgs={
            "ContentType": CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"),
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )


def publish_media(folder, id, s3=None, bucket=None, environ=None):
    """Envoie les médias lourds, puis les efface — dans cet ordre, sans exception.

    L'envoi d'un sous-dossier est confirmé avant que ce sous-dossier ne soit
    effacé. Un échec d'envoi laisse donc les fichiers en place, prêts à réessayer.
    """
    environ = environ or os.environ
    bucket = bucket or environ.get("R2_BUCKET_NAME")
    if not bucket:
        raise PublishError("Configuration R2 incomplète : R2_BUCKET_NAME")
    s3 = client(environ=environ, s3=s3)
    folder = Path(folder)
    report = {"sent": [], "freed_bytes": 0}
    for kind in MEDIA_FOLDERS:
        directory = folder / kind
        if not directory.is_dir():
            continue
        files = [path for path in sorted(directory.iterdir()) if path.is_file()]
        if not files:
            continue
        for path in files:
            put(bucket, object_key(id, path.name, kind), path, s3)
            report["sent"].append(
                {"kind": kind, "file": path.name, "bytes": path.stat().st_size}
            )
        # Envoi confirmé pour ce sous-dossier : la place peut être libérée.
        for path in files:
            report["freed_bytes"] += path.stat().st_size
            path.unlink()
    return report


def publish_documents(folder, id, s3=None, bucket=None, environ=None):
    """Envoie les JSON du dossier sans rien effacer.

    Ils sont légers et la page de démonstration les lit par le lien : ils partent
    donc sur le compartiment tout en restant sur la machine, où le studio les lit.
    """
    environ = environ or os.environ
    bucket = bucket or environ.get("R2_BUCKET_NAME")
    if not bucket:
        raise PublishError("Configuration R2 incomplète : R2_BUCKET_NAME")
    s3 = client(environ=environ, s3=s3)
    report = {"sent": []}
    directory = Path(folder) / DOCUMENTS_FOLDER
    if not directory.is_dir():
        return report
    for path in sorted(directory.iterdir()):
        if path.is_file():
            put(bucket, object_key(id, path.name, DOCUMENTS_FOLDER), path, s3)
            report["sent"].append(
                {"kind": DOCUMENTS_FOLDER, "file": path.name, "bytes": path.stat().st_size}
            )
    return report


def publish_folder(folder, id, s3=None, bucket=None, environ=None):
    """Envoie tout le dossier : les médias (puis libérés) et les documents (gardés)."""
    media = publish_media(folder, id, s3=s3, bucket=bucket, environ=environ)
    documents = publish_documents(folder, id, s3=s3, bucket=bucket, environ=environ)
    return {
        "sent": media["sent"] + documents["sent"],
        "freed_bytes": media["freed_bytes"],
    }


def notify(url, payload, send=None):
    """Prévient un service extérieur que le dossier est prêt.

    Adresse vide : rien à faire. Un webhook injoignable ne doit jamais faire
    échouer une publication déjà réussie : l'échec est signalé, pas levé.
    """
    if not url:
        return False
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        opened = (send or urllib.request.urlopen)(request, timeout=10)
        with opened as response:
            return 200 <= response.status < 300
    except Exception:
        return False
