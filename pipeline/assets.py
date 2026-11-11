"""Tri des médias collectés : photos utilisables d'un côté, marque de l'autre.

Les logos sont repris de la liste des candidates, que l'extracteur conserve même
lorsqu'il rejette une image. C'est indispensable ici : les filtres de photos
écartent les petites images et les SVG, c'est-à-dire exactement les logos.

Faute de position dans la page, le signal retenu est la présence sur plusieurs
pages : un logo est un élément d'en-tête, donc répété ; une photo de chambre ne
l'est pas.
"""

import hashlib
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from ingestion import text
from pipeline import network

LOGO_MIN_PAGES = 2
LOGO_HINTS = ("logo", "brand", "marque", "identite")
VECTOR_SUFFIXES = (".svg",)
RASTER_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif")
LOGO_MAX = 12
LOGO_MAX_BYTES = 400_000
LOGO_FETCH_BYTES = 600_000


def suffix(url):
    return Path(urlsplit(url).path).suffix.lower()


def photo_score(photo, home_pages):
    """Intérêt d'une photo : résolution, cadrage, description et page d'origine."""
    width = int(photo.get("width") or 0)
    height = int(photo.get("height") or 0)
    if not width or not height:
        return 0.0
    score = 0.40 * min(width * height / 4_000_000, 1.0)
    sources = photo.get("sources") or []
    if any(text(source.get("alt")) for source in sources):
        score += 0.20
    if 1.2 <= width / height <= 2.0:
        score += 0.25
    if {source.get("page") for source in sources} & home_pages:
        score += 0.15
    return round(min(score, 1.0), 3)


def select_photos(report):
    """Photos retenues, classées par intérêt pour la démo."""
    home_pages = {page.get("url") for page in (report.get("pages") or [])[:1]}
    rows = []
    for photo in report.get("photos") or []:
        sources = photo.get("sources") or []
        if not sources or not text(photo.get("id")):
            continue
        origin = sources[0]
        rows.append(
            {
                "id": text(photo.get("id")),
                "url": text(origin.get("url")),
                "local_file": text(photo.get("file")),
                "width": int(photo.get("width") or 0),
                "height": int(photo.get("height") or 0),
                "bytes": int(photo.get("bytes") or 0),
                "alt": next((text(item.get("alt")) for item in sources if text(item.get("alt"))), ""),
                "pages": sorted({text(item.get("page")) for item in sources if text(item.get("page"))}),
                "score": photo_score(photo, home_pages),
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["id"]))
    return rows


def copy_photos(rows, extraction_folder, target):
    """Range les photos retenues sous un nom lisible, prêtes pour l'envoi.

    Les photos dont le fichier a disparu sont écartées, et la numérotation reste
    continue : les noms doivent rester prévisibles pour l'hôtelier.
    """
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    kept = []
    for row in rows:
        source = Path(extraction_folder) / row["local_file"]
        if not source.is_file():
            continue
        copy = dict(row)
        copy["file"] = f"photo-{len(kept) + 1:02d}{suffix(row['local_file']) or '.jpg'}"
        shutil.copyfile(source, target / copy["file"])
        kept.append(copy)
    return kept


def logo_reason(hinted, shared, extension):
    reasons = []
    if hinted:
        reasons.append("nom ou attribut qui désigne la marque")
    if shared:
        reasons.append("présente sur plusieurs pages")
    if extension in VECTOR_SUFFIXES:
        reasons.append("image vectorielle")
    return " · ".join(reasons)


def logo_candidates(report, photo_urls):
    """URL candidates qui ressemblent à un élément de marque plutôt qu'à une photo."""
    rows = []
    for url, sources in (report.get("candidates") or {}).items():
        if url in photo_urls:
            continue
        extension = suffix(url)
        if extension not in VECTOR_SUFFIXES + RASTER_SUFFIXES:
            continue
        pages = sorted({text(item.get("page")) for item in sources if text(item.get("page"))})
        alt = next((text(item.get("alt")) for item in sources if text(item.get("alt"))), "")
        haystack = f"{url} {alt}".lower()
        hinted = any(hint in haystack for hint in LOGO_HINTS)
        shared = len(pages) >= LOGO_MIN_PAGES
        vector = extension in VECTOR_SUFFIXES
        if not (hinted or shared or vector):
            continue
        score = (0.5 if hinted else 0.0) + (0.3 if shared else 0.0) + (0.2 if vector else 0.0)
        rows.append(
            {
                "url": url,
                "alt": alt,
                "pages": pages,
                "score": round(score, 3),
                "raison": logo_reason(hinted, shared, extension),
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["url"]))
    return rows[:LOGO_MAX]


def file_hashes(folder):
    """Empreintes des fichiers déjà conservés, pour ne pas ranger deux fois la même image."""
    folder = Path(folder) if folder else None
    if not folder or not folder.is_dir():
        return set()
    return {
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in folder.iterdir()
        if path.is_file()
    }


def download_logos(candidates, folder, photos_dir=None, fetch=None, limit=LOGO_MAX):
    """Télécharge les logos retenus et renvoie aussi les refus, pour la traçabilité.

    Un logo injoignable ne doit jamais interrompre la collecte : il est refusé et
    la raison est conservée.
    """
    fetch = fetch or network().fetch
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    known = file_hashes(photos_dir)
    saved, refused = [], []
    for row in candidates[:limit]:
        try:
            raw, mime, final = fetch(row["url"], LOGO_FETCH_BYTES)
        except Exception as error:
            refused.append({"url": row["url"], "raison": f"téléchargement impossible ({type(error).__name__})"})
            continue
        if not raw:
            refused.append({"url": row["url"], "raison": "fichier vide"})
            continue
        if len(raw) > LOGO_MAX_BYTES:
            refused.append({"url": row["url"], "raison": "fichier trop lourd pour un logo"})
            continue
        digest = hashlib.sha256(raw).hexdigest()
        if digest in known:
            refused.append({"url": row["url"], "raison": "image déjà conservée"})
            continue
        known.add(digest)
        extension = suffix(final or row["url"]) or ".png"
        name = f"logo-{len(saved) + 1:02d}{extension}"
        (folder / name).write_bytes(raw)
        saved.append(
            {
                "url": row["url"],
                "file": name,
                "bytes": len(raw),
                "mime": mime,
                "alt": row["alt"],
                "pages": row["pages"],
                "score": row["score"],
                "raison": row["raison"],
            }
        )
    return saved, refused
