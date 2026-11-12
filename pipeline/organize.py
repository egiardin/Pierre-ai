"""Organisation des informations collectées, pour que la démo soit facile à monter.

Principe : chaque valeur porte son origine et un niveau de confiance vérifiable.
Une valeur que l'on ne retrouve pas dans le texte des pages est signalée « à
confirmer » plutôt que présentée comme certaine. Aucun tarif, horaire ni
équipement absent de la source n'est ajouté.

Ce que la démo utilise vraiment est mis en avant : présentation, chambres,
équipements, contact. Le reste des passages du site est conservé en réserve de
texte, sous forme verbatim.
"""

import json
import re
from pathlib import Path

from ingestion import build_document, relevant_pages, text
from pipeline import publish

MIN_PASSAGE = 120
QUOTE_RADIUS = 160


def collapse(value):
    return re.sub(r"\s+", " ", value).strip()


def find_quote(pages, value, radius=QUOTE_RADIUS):
    """Retrouve le passage qui porte la valeur : une provenance doit être vérifiable."""
    needle = collapse(value).lower()
    if not needle:
        return None
    for page in pages:
        haystack = collapse(text(page.get("text")))
        position = haystack.lower().find(needle)
        if position < 0:
            # Une URL (ex. lien de réservation) n'apparaît pas dans le texte :
            # elle est cherchée aussi parmi les ancres de la page.
            for anchor in page.get("anchors") or []:
                hay = collapse(f"{text(anchor.get('t'))} {text(anchor.get('h'))}")
                if needle in hay.lower():
                    return {"page": text(page.get("url")), "extrait": hay[: radius * 2]}
            continue
        start = max(0, position - radius)
        end = min(len(haystack), position + len(needle) + radius)
        return {"page": text(page.get("url")), "extrait": haystack[start:end]}
    return None


def field(pages, value):
    """Valeur, origine et confiance. « Confirmée » seulement si retrouvée dans la source."""
    value = text(value)
    if not value:
        return {"valeur": "", "origine": None, "confiance": "absente"}
    origin = find_quote(pages, value)
    if origin is None:
        return {"valeur": value, "origine": None, "confiance": "a_confirmer"}
    return {"valeur": value, "origine": origin, "confiance": "confirmee"}


def passages(pages, minimum=MIN_PASSAGE, limit=4):
    """Passages verbatim les plus longs : matière première du rédacteur, jamais réécrite.

    Un passage est repris tel quel du site : sa confiance est donc acquise.
    """
    rows = []
    for page in pages:
        for line in text(page.get("text")).splitlines():
            line = collapse(line)
            if len(line) >= minimum:
                rows.append(
                    {
                        "valeur": line,
                        "origine": {"page": text(page.get("url")), "extrait": line},
                        "confiance": "confirmee",
                    }
                )
    rows.sort(key=lambda row: -len(row["valeur"]))
    return rows[:limit]


def media_items(photos, id):
    """Photos au format du document du studio : nom lisible et adresse publiée."""
    return [
        {
            "id": photo["id"],
            "file": publish.media_url(id, photo["file"], "images"),
            "width": photo["width"],
            "height": photo["height"],
            "source": "extraction",
            "status": "extracted",
            "alt": photo["alt"],
        }
        for photo in photos
    ]


def missing(infos):
    """Ce qui manque pour que la démo soit complète, dit franchement."""
    manques = []
    for key, label in (
        ("nom", "nom"),
        ("adresse", "adresse"),
        ("telephone", "telephone"),
        ("email", "email"),
        ("reservation", "lien_reservation"),
    ):
        if not infos["etablissement"][key]["valeur"]:
            manques.append(label)
    if not infos["chambres"]:
        manques.append("chambres")
    else:
        # Aucune photo de chambre n'est devinée : elle reste à choisir.
        manques.append("photos_de_chambres")
    if not infos["equipements"]:
        manques.append("equipements")
    if not infos["presentation"]["texte"]["valeur"]:
        manques.append("texte_de_presentation")
    if not infos["medias"]["photos"]:
        manques.append("photos")
    if not infos["medias"]["logos"]:
        manques.append("logo")
    # Jamais repris de la source, par principe : l'hôtelier les fournit lui-même.
    manques.extend(("tarifs", "horaires", "coordonnees_gps", "conditions_de_reservation"))
    return manques


def to_confirm(infos):
    """Chemins des valeurs que la source ne permet pas de confirmer."""
    paths = []
    for name, entry in infos["etablissement"].items():
        if entry["confiance"] == "a_confirmer":
            paths.append(f"etablissement.{name}")
    for index, chambre in enumerate(infos["chambres"]):
        for name in ("nom", "description"):
            if chambre[name]["confiance"] == "a_confirmer":
                paths.append(f"chambres[{index}].{name}")
    for index, equipement in enumerate(infos["equipements"]):
        if equipement["origine"] is None:
            paths.append(f"equipements[{index}]")
    return paths


def build_infos(report, extracted, id, photos, logos, debut=None, fin=None):
    """Construit le JSON organisé de l'hôtel, à partir de la collecte et de l'extraction."""
    pages = relevant_pages(report)
    info = extracted if isinstance(extracted, dict) else {}
    verbatim = passages(pages)

    chambres = [
        {
            "nom": field(pages, chambre.get("name")),
            "description": field(pages, chambre.get("description")),
        }
        for chambre in (info.get("rooms") or [])
        if isinstance(chambre, dict)
    ]
    equipements = [
        {"valeur": text(label), "origine": find_quote(pages, text(label))}
        for label in (info.get("amenities") or [])
        if text(label)
    ]

    infos = {
        "schema_version": 1,
        "id": id,
        "collecte": {
            "url_source": text(report.get("source_url")),
            "statut": text(report.get("status")),
            "limite": report.get("limit"),
            "pages": report.get("page_count"),
            "requetes": report.get("requests"),
            "octets": report.get("network_bytes"),
            "debut": debut,
            "fin": fin,
        },
        "pages": [
            {"url": text(page.get("url")), "titre": text(page.get("title"))} for page in pages
        ],
        "etablissement": {
            "nom": field(pages, info.get("name")),
            "adresse": field(pages, info.get("address")),
            "telephone": field(pages, info.get("phone")),
            "email": field(pages, info.get("email")),
            "reservation": field(pages, info.get("booking")),
        },
        "liens_reservation": [
            field(pages, link.get("url"))
            for link in (info.get("booking_links") or [])
            if isinstance(link, dict) and text(link.get("url"))
        ][:5],
        "presentation": {
            "accroche": field(pages, pages[0].get("description") if pages else ""),
            "texte": verbatim[0] if verbatim else {"valeur": "", "origine": None, "confiance": "absente"},
            "extraits": verbatim[1:],
        },
        "chambres": chambres,
        "equipements": equipements,
        "medias": {"photos": photos, "logos": logos},
    }
    infos["manques"] = missing(infos)
    infos["a_confirmer"] = to_confirm(infos)
    return infos


def build_site(report, extracted, id, photos):
    """Document du studio et sa provenance : un seul contrat, deux usages."""
    return build_document(report, extracted, id, media=media_items(photos, id))


def write_collection(folder, infos, sources, site, pierre_data):
    """Écrit le dossier d'information : ce que la démo lira, et d'où tout vient."""
    hotel = Path(folder) / "hotel"
    hotel.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("infos.json", infos),
        ("sources.json", sources),
        ("site.json", site),
        ("pierre.json", pierre_data),
    ):
        (hotel / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return hotel
