"""Pont entre l'extracteur Pierre et le document du studio.

Entrée : un dossier d'extraction (report.json) et les informations lues dans le
site (voir `pipeline.lecture`). Sortie : un site.json conforme au contrat partagé,
plus un fichier de provenance qui rattache chaque contenu à sa page d'origine.

Règle de fond : rien n'est inventé. Un champ que la source ne fournit pas reste
vide et sera complété par l'hôtelier dans le studio. Les seules valeurs non issues
de la source sont des libellés de gabarit, listés dans la provenance.

La collecte (Playwright) et la lecture du site sont chargées à l'intérieur de
`import_url` : le mapping reste testable sans navigateur ni clé d'API.
"""

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from studio_schema import SCHEMA_VERSION, validate_site

# Pages qui ne décrivent pas l'hôtel : elles ne servent ni au texte ni aux sources.
IGNORED_PAGE_TERMS = (
    "mention",
    "cgv",
    "cgu",
    "condition",
    "legal",
    "privacy",
    "confidentialite",
    "cookie",
    "rgpd",
)

# Libellés de gabarit : présents dans le document sans venir de la source.
TEMPLATE_DEFAULTS = (
    "hero.content.cta_label",
    "hero.content.cta_url",
    "hero.media.focal",
    "hero.media.ratio",
    "rooms.content.title",
    "services.content.title",
    "gallery.content.title",
    "contact.content.title",
)


def text(value):
    """Chaîne nettoyée, ou chaîne vide si la source ne fournit rien."""
    return value.strip() if isinstance(value, str) else ""


def slugify(value):
    """Identifiant de dossier : sans accent, sans espace, sans caractère spécial."""
    ascii_value = unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.decode()).strip("-").lower()
    return slug[:60] or "hotel"


def read_report(folder):
    """Charge le rapport produit par l'extraction."""
    return json.loads((Path(folder) / "report.json").read_text(encoding="utf-8"))


def relevant_pages(report):
    """Pages qui décrivent l'hôtel, dans l'ordre de priorité du crawl."""
    pages = report.get("pages") or []
    return [
        page
        for page in pages
        if not any(term in text(page.get("url")).lower() for term in IGNORED_PAGE_TERMS)
    ]


def build_media(report):
    """Photos retenues → médias du document, plus leur provenance par identifiant.

    `file` pointe pour l'instant vers l'URL d'origine, seule adresse affichable
    avant publication. Le fichier téléchargé est noté dans la provenance et
    deviendra la source de l'URL publiée au lot de publication.
    """
    media, origins = [], {}
    for photo in report.get("photos") or []:
        sources = photo.get("sources") or []
        media_id = text(photo.get("id"))
        if not sources or not media_id:
            continue
        origin = sources[0]
        media.append(
            {
                "id": media_id,
                "file": text(origin.get("url")),
                "width": int(photo.get("width") or 0),
                "height": int(photo.get("height") or 0),
                "source": "extraction",
                "status": "extracted",
                "alt": text(origin.get("alt")),
            }
        )
        origins[media_id] = {
            "original_url": text(origin.get("url")),
            "page": text(origin.get("page")),
            "local_file": text(photo.get("file")),
        }
    return media, origins


def build_document(report, extracted, slug, media=None):
    """Construit le document du studio et sa provenance depuis une extraction.

    Fonction pure : aucun accès réseau ni écriture. Le document est validé par le
    contrat partagé avant d'être renvoyé, donc un import réussi est toujours
    affichable par le studio.

    `media` permet de fournir des médias déjà préparés par le pipeline (noms
    lisibles, adresses publiées) ; sans lui, les photos de l'extraction sont
    reprises telles quelles.
    """
    info = extracted if isinstance(extracted, dict) else {}
    pages = relevant_pages(report)
    extracted_media, origins = build_media(report)
    medi = list(media) if media is not None else extracted_media
    photo_ids = [item["id"] for item in medi]
    first_page = pages[0] if pages else {}
    booking_url = text(info.get("booking"))

    rooms = [
        {
            "id": f"r{index}",
            "title": text(room.get("name")) if isinstance(room, dict) else "",
            "text": text(room.get("description")) if isinstance(room, dict) else "",
            # Aucune photo de chambre n'est devinée : l'hôtelier la choisit.
            "photo_id": "",
        }
        for index, room in enumerate(info.get("rooms") or [], start=1)
    ]
    services = [
        {"id": f"s{index}", "label": text(label)}
        for index, label in enumerate(info.get("amenities") or [], start=1)
        if text(label)
    ]
    gallery = [
        {"id": f"g{index}", "photo_id": photo_id}
        for index, photo_id in enumerate(photo_ids, start=1)
    ]

    sections = [
        {
            "id": "hero",
            "type": "hero",
            "content": {
                "title": text(info.get("name")) or text(first_page.get("title")),
                "intro": text(first_page.get("description")),
                "cta_label": "Réserver",
                "cta_url": booking_url,
            },
            "media": {
                "photo_id": photo_ids[0] if photo_ids else "",
                "focal": {"x": 0.5, "y": 0.5},
                "ratio": "16:9",
            },
        },
        {"id": "rooms", "type": "rooms", "content": {"title": "Nos chambres"}, "items": rooms},
        {
            "id": "services",
            "type": "services",
            "content": {"title": "Services et équipements"},
            "items": services,
        },
        {"id": "gallery", "type": "gallery", "content": {"title": "Galerie"}, "items": gallery},
        {
            "id": "contact",
            "type": "contact",
            "content": {
                "title": "Contact et accès",
                "address": text(info.get("address")),
                "phone": text(info.get("phone")),
                "email": text(info.get("email")),
                "booking_url": booking_url,
            },
        },
    ]

    document = {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "version": 1,
        "status": "draft",
        "pages": [{"id": "home", "sections": sections}],
        "media": medi,
    }

    provenance = {
        "source_url": text(report.get("source_url")),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "pages": [{"url": text(page.get("url")), "title": text(page.get("title"))} for page in pages],
        "media": origins,
        "defaults": list(TEMPLATE_DEFAULTS),
    }

    return validate_site(document), provenance


def write_draft(document, provenance, dossiers_dir="dossiers"):
    """Écrit le brouillon et sa provenance dans le dossier de l'hôtel."""
    folder = Path(dossiers_dir) / document["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "site.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "sources.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return folder


async def import_url(url, dossiers_dir="dossiers"):
    """Importe un site d'hôtel vers un brouillon site.json et renvoie son dossier.

    Étapes : collecte des pages et des photos, lecture du site, puis écriture du
    brouillon. Aucun modèle ni clé d'API n'intervient.
    """
    # Le paquet d'extraction vit dans son propre dossier et n'est importable
    # qu'avec ce chemin : il reste autonome, aucun fichier n'y est modifié.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "Extraction"))
    from pierre_extract import extract_site

    from pipeline.lecture import read_hotel

    extraction_folder = await extract_site(url)
    report = read_report(extraction_folder)
    info = read_hotel(report)

    slug = slugify(info.get("name")) if text(info.get("name")) else slugify(url.split("//")[-1].split("/")[0])
    document, provenance = build_document(report, info, slug)
    provenance["extraction_folder"] = str(extraction_folder)

    return write_draft(document, provenance, dossiers_dir)


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Importe le site d'un hôtel vers un brouillon site.json."
    )
    parser.add_argument("url")
    parser.add_argument("--dossiers", default="dossiers")
    arguments = parser.parse_args()

    dossier = asyncio.run(import_url(arguments.url, dossiers_dir=arguments.dossiers))
    print(f"Brouillon écrit : {dossier / 'site.json'}")
