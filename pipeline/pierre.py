"""Ce que Pierre doit savoir pour suggérer, case par case.

Les propositions sont calculées pendant la collecte : quand l'hôtelier touche une
case, la suggestion est déjà là, sans appel réseau. Aucune proposition ne peut
être un fait absent de la source : le rédacteur ne reprend que des passages
verbatim du site, et une photo de chambre n'est jamais devinée.
"""

import re

from ingestion import text

ROLES = (
    "analyste",
    "detective_des_manques",
    "selectionneur_de_photos",
    "redacteur_prudent",
)

REGLES = (
    "Ne jamais proposer un tarif, un horaire ni un équipement absent de la source.",
    "Toute proposition de texte est un passage verbatim du site, jamais une reformulation.",
    "Une valeur que l'on ne retrouve pas dans le texte des pages est signalée à confirmer.",
    "Une photo de chambre n'est jamais devinée : elle est choisie par l'hôtelier.",
)


def photo_reason(photo):
    """Pourquoi cette photo : la raison doit être lisible par l'hôtelier."""
    parts = []
    if photo["width"] and photo["height"]:
        parts.append(f"{photo['width']}×{photo['height']} pixels")
    if photo["alt"]:
        parts.append(f"décrite « {photo['alt']} »")
    if photo["pages"]:
        parts.append(f"trouvée sur {photo['pages'][0]}")
    return " · ".join(parts) or "mieux classée pour la démo"


def photo_proposals(photos, limit=3):
    return [
        {
            "valeur": photo["id"],
            "libelle": photo["file"],
            "raison": photo_reason(photo),
            "score": photo["score"],
        }
        for photo in photos[:limit]
    ]


def from_field(entry, raison):
    """Reprend une valeur collectée comme proposition, avec sa confiance."""
    if not entry["valeur"]:
        return []
    return [
        {
            "valeur": entry["valeur"],
            "raison": raison,
            "confiance": entry["confiance"],
            "origine": entry["origine"],
        }
    ]


def citations(presentation, limit=4):
    """Passages verbatim du site : le rédacteur ne réécrit rien lui-même."""
    rows = []
    if presentation["texte"]["valeur"]:
        rows.append(
            {
                "valeur": presentation["texte"]["valeur"],
                "raison": "passage le plus long du site",
                "confiance": presentation["texte"]["confiance"],
                "origine": presentation["texte"]["origine"],
            }
        )
    for extrait in presentation["extraits"]:
        rows.append(
            {
                "valeur": extrait["valeur"],
                "raison": "passage verbatim du site",
                "confiance": "confirmee",
                "origine": extrait["origine"],
            }
        )
    return rows[:limit]


def room_proposals(room_name, photos, limit=3):
    """Photos dont la description évoque le nom de la chambre. Rien n'est deviné."""
    tokens = [token for token in re.split(r"\W+", text(room_name).lower()) if len(token) >= 4]
    if not tokens:
        return []
    rows = []
    for photo in photos:
        haystack = f"{photo['alt']} {' '.join(photo['pages'])}".lower()
        matched = [token for token in tokens if token in haystack]
        if not matched:
            continue
        rows.append(
            {
                "valeur": photo["id"],
                "libelle": photo["file"],
                "raison": f"correspond à « {' '.join(matched)} »",
                "score": photo["score"],
            }
        )
    rows.sort(key=lambda row: -row["score"])
    return rows[:limit]


def build_pierre(infos):
    """Index des suggestions, prêt à être servi au studio sans calcul ni réseau."""
    photos = infos["medias"]["photos"]
    etablissement = infos["etablissement"]
    reglages = texts = infos["presentation"]

    champs = {
        "hero.content.title": from_field(etablissement["nom"], "nom relevé sur le site"),
        "hero.content.intro": citations(reglages),
        "hero.media.photo_id": photo_proposals(photos),
        "gallery.items": [
            {
                "valeur": photo["id"],
                "libelle": photo["file"],
                "raison": photo_reason(photo),
                "score": photo["score"],
            }
            for photo in photos
        ],
        "contact.content.email": from_field(etablissement["email"], "adresse de contact du site"),
        "contact.content.phone": from_field(etablissement["telephone"], "téléphone du site"),
        "contact.content.address": from_field(etablissement["adresse"], "adresse du site"),
        "services.items": [
            {
                "valeur": equipement["valeur"],
                "raison": "équipement mentionné sur le site",
                "confiance": "confirmee" if equipement["origine"] else "a_confirmer",
                "origine": equipement["origine"],
            }
            for equipement in infos["equipements"]
        ],
    }

    for index, chambre in enumerate(infos["chambres"]):
        champs[f"rooms.items[{index}].title"] = from_field(chambre["nom"], "nom de chambre du site")
        champs[f"rooms.items[{index}].text"] = from_field(
            chambre["description"], "description de chambre du site"
        )
        champs[f"rooms.items[{index}].photo_id"] = room_proposals(chambre["nom"]["valeur"], photos)

    return {
        "schema_version": 1,
        "roles": list(ROLES),
        "regles": list(REGLES),
        "champs": champs,
        "manques": infos["manques"],
        "a_confirmer": infos["a_confirmer"],
    }
