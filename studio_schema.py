"""Contrat du document de site (site.json).

Miroir de web/src/document/types.ts. L'import, le brouillon, la publication et le
studio partagent ce seul contrat : un document refusé ici est refusé de la même
façon par web/src/document/validate.ts.

Les règles sont volontairement les mêmes que celles du frontend, sans en ajouter :
durcir d'un seul côté ferait diverger les deux validations.
"""

SCHEMA_VERSION = 1
STATUSES = ("draft", "paye", "published")


class SiteDocumentError(ValueError):
    """Document de site refusé."""


def _require(condition, message):
    if not condition:
        raise SiteDocumentError(message)


def validate_site(value):
    """Vérifie la structure du document et le renvoie tel quel."""
    _require(isinstance(value, dict), "site.json : objet attendu.")
    _require(
        value.get("schema_version") == SCHEMA_VERSION,
        f"site.json : schema_version doit valoir {SCHEMA_VERSION}.",
    )
    _require(
        isinstance(value.get("slug"), str) and value["slug"] != "",
        "site.json : slug manquant.",
    )
    version = value.get("version")
    _require(
        isinstance(version, (int, float)) and not isinstance(version, bool),
        "site.json : version manquante.",
    )
    _require(value.get("status") in STATUSES, "site.json : statut invalide.")

    pages = value.get("pages")
    _require(isinstance(pages, list) and len(pages) > 0, "site.json : pages manquantes.")
    _require(isinstance(value.get("media"), list), "site.json : media manquant.")

    for page in pages:
        _require(
            isinstance(page, dict) and isinstance(page.get("sections"), list),
            "site.json : une page n'a pas de sections.",
        )
        for section in page["sections"]:
            _require(
                isinstance(section, dict)
                and isinstance(section.get("id"), str)
                and isinstance(section.get("type"), str),
                "site.json : section sans id ou sans type.",
            )

    for media in value["media"]:
        _require(
            isinstance(media, dict)
            and isinstance(media.get("id"), str)
            and isinstance(media.get("file"), str),
            "site.json : média sans id ou sans fichier.",
        )

    return value
