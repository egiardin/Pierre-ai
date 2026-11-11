"""Lecture du site sans modèle ni clé d'API.

Un rapport d'extraction entre ; six informations sortent, celles que le document
attend : nom, adresse, email, téléphone, équipements et chambres.

La méthode vient du workflow de Sacha : les coordonnées sont reconnues par
expression régulière. Les autres champs suivent la même règle — motif et petit
lexique — et ne sont jamais devinés : seules des chaînes réellement présentes
dans le texte des pages sont renvoyées. `organize.field` repasse ensuite sur
chacune d'elles : une valeur qu'il ne retrouve pas mot pour mot est marquée « à
confirmer » plutôt que présentée comme certaine.
"""

import re
from urllib.parse import urlsplit

from ingestion import relevant_pages, text

# Coordonnées : mêmes motifs que le workflow de Sacha.
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\d)(?:\+33|0)[\s.\-()]?[1-9](?:[\s.\-()]?\d){8}(?!\d)")

# Adresse : un code postal, une voie nommée.
POSTAL = re.compile(r"\b\d{5}\b")
POSTAL_CITY = re.compile(r"\b\d{5}\b\s+[A-ZÀ-Ý]")
STREET = re.compile(
    r"\b\d{1,4}\s?(?:bis|ter)?\s?"
    r"(?:rue|avenue|av\.|boulevard|bd|chemin|route|place|impasse|allée|allee|"
    r"quai|square|lieu-dit|lieudit)\b",
    re.I,
)

# Titre de page : les segments génériques ne sont pas le nom de l'établissement.
GENERIC_TITLE_WORDS = (
    "accueil",
    "home",
    "bienvenue",
    "welcome",
    "site officiel",
    "officiel",
    "index",
)
TITLE_SEPARATORS = re.compile(r",\s+|\s+[|/•·–—]+\s*|\s+-\s+|\s+:\s+")

# Une marque d'établissement porte presque toujours l'un de ces mots.
BRAND_MARKERS = (
    "hôtel",
    "hotel",
    "spa",
    "resort",
    "auberge",
    "gîte",
    "gite",
    "château",
    "chateau",
    "maison d'hôtes",
    "chambres d'hôtes",
    "résidence",
    "residence",
    "lodge",
    "inn",
)

# Lignes de structure du site : ni une marque, ni une chambre.
STRUCTURE_LINES = (
    "accueil",
    "home",
    "menu",
    "réserver",
    "reserver",
    "book",
    "booking",
    "contact",
    "nous contacter",
    "suivez-nous",
    "mentions légales",
    "mentions legales",
    "plan du site",
    "cookies",
    "tous droits réservés",
    "tous droits reserves",
    "en savoir plus",
    "lire la suite",
    "à partir de",
    "nos chambres",
    "les chambres",
    "chambres",
    "chambres et suites",
    "chambres & suites",
    "rooms & suites",
    "rooms",
    "nos suites",
    "voir les chambres",
    "chambre & suite",
    "galerie",
    "photos",
    "restaurant",
    "bar",
    "spa",
    "actualités",
    "news",
    "blog",
    "français",
    "english",
    "deutsch",
    "español",
    "italiano",
)

# Équipements reconnus. Le libellé rendu reste le texte de la page, jamais le terme du lexique.
AMENITIES = (
    "wifi",
    "wi-fi",
    "internet",
    "piscine",
    "spa",
    "sauna",
    "hammam",
    "jacuzzi",
    "climatisation",
    "climatisé",
    "chauffage",
    "parking",
    "garage",
    "restaurant",
    "bar",
    "petit-déjeuner",
    "petit dejeuner",
    "brunch",
    "salle de sport",
    "salle de fitness",
    "fitness",
    "massage",
    "plage privée",
    "terrasse",
    "ascenseur",
    "animaux acceptés",
    "blanchisserie",
    "pressing",
    "navette",
    "conciergerie",
    "jardin",
    "salle de réunion",
    "salle de séminaire",
    "séminaire",
    "coworking",
    "recharge",
    "minibar",
    "coffre-fort",
    "balcon",
    "vue mer",
    "vue montagne",
    "barbecue",
    "réception 24h",
    "service en chambre",
    "room service",
    "télévision",
)

# Types d'hébergement : une ligne qui commence ainsi peut être un nom de chambre.
ROOM_HEAD = re.compile(
    r"^(?:la |le |les |l')?(?:chambre|suite|studio|appartement|duplex|loft|bungalow|"
    r"villa|chalet|roulotte|cabane|tente|gîte|gite|mobil-home)\b",
    re.I,
)
SURFACE = re.compile(r"^\d+([.,]\d+)?\s*(m²|m2|mètres?|metres?)\b", re.I)

# Adresses à ne pas proposer : boîtes techniques et domaines de prestataires.
NOISE_LOCALS = ("noreply", "no-reply", "donotreply", "postmaster", "abuse", "sentry")
NOISE_DOMAINS = ("example.com", "sentry.io", "wixpress.com", "wordpress.com", "godaddy.com")

# Pages où l'adresse a le plus de chances de se trouver, par ordre de préférence.
CONTACT_HINTS = ("contact", "acces", "accès", "nous-trouver", "trouver", "venir", "plan")

MAX_AMENITIES = 12
MAX_ROOMS = 8
MAX_LINE = 120
MAX_ROOM_LINE = 60
MAX_BRAND_LINE = 40


def lines(page):
    """Lignes utiles d'une page, sans puce ni marque de titre."""
    rows = []
    for raw in text(page.get("text")).splitlines():
        line = re.sub(r"^[\s>#*•·–—]+", "", raw).strip()
        if line:
            rows.append(line)
    return rows


def repeated(pages, minimum):
    """Lignes présentes sur au moins `minimum` pages : en-tête, menu ou pied de page."""
    counts = {}
    for page in pages:
        for line in set(lines(page)):
            counts[line] = counts.get(line, 0) + 1
    return {line for line, count in counts.items() if count >= minimum}


def dedupe(values):
    """Première occurrence conservée, ordre préservé, comparaison sans la casse."""
    rows, seen = [], set()
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(value)
    return rows


def title_name(pages):
    """Nom repris du titre de la page : segments génériques écartés."""
    for page in pages:
        parts = [
            part.strip(" \t→|/•·–—-:,")
            for part in TITLE_SEPARATORS.split(text(page.get("title")))
            if part.strip()
        ]
        parts = [part for part in parts if part.lower() not in GENERIC_TITLE_WORDS]
        if parts:
            return max(parts, key=len)
    return ""


def brand_name(pages):
    """Marque : la ligne courte qui revient d'une page à l'autre **et** figure dans
    un titre de page.

    Le nom de l'établissement est en tête de toutes les pages et dans les titres ;
    le croiser avec les titres évite de prendre une entrée de menu (« La Winstub »)
    ou une coordonnée répétée en pied de page.
    """
    if len(pages) < 2:
        return ""
    titles = " ".join(text(page.get("title")) for page in pages).lower()
    counts = {}
    for page in pages:
        for line in set(lines(page)):
            lowered = line.lower()
            if len(line) > MAX_BRAND_LINE or len(line.split()) < 2:
                continue
            if lowered in STRUCTURE_LINES or lowered in GENERIC_TITLE_WORDS:
                continue
            # Un code postal + ville ou une voie en pied de page n'est pas une marque.
            if POSTAL_CITY.search(line) or STREET.search(line):
                continue
            # Une entrée de menu commence souvent par un article défini.
            if re.match(r"^(la|le|les|l')\s", lowered):
                continue
            # Seul un mot d'établissement fait une marque (« Table du 5 » n'en est pas).
            if not any(marker in lowered for marker in BRAND_MARKERS):
                continue
            if not any(character.isalpha() for character in line):
                continue
            counts[line] = counts.get(line, 0) + 1
    retained = [
        line
        for line, count in counts.items()
        if count >= max(2, len(pages) // 2) and line.lower() in titles
    ]
    if not retained:
        return ""
    retained.sort(key=lambda line: (-counts[line], len(line)))
    return retained[0]


def hotel_name(pages):
    return brand_name(pages) or title_name(pages)


def address(pages):
    """Adresse : la ligne qui porte le code postal, sinon celle qui porte une voie."""
    ordered = sorted(
        pages,
        key=lambda page: 0
        if any(hint in text(page.get("url")).lower() for hint in CONTACT_HINTS)
        else 1,
    )
    tests = (
        lambda line: bool(POSTAL.search(line) and STREET.search(line)),
        lambda line: bool(POSTAL_CITY.search(line)),
        lambda line: bool(STREET.search(line)),
    )
    for test in tests:
        for page in ordered:
            for line in lines(page):
                if len(line) <= MAX_LINE and test(line):
                    return line
    return ""


def emails(pages, source_url):
    """Adresse de contact : celle du domaine du site est préférée."""
    found = []
    for page in pages:
        found.extend(EMAIL.findall(text(page.get("text"))))
    found = [mail for mail in dedupe(found) if not is_noise(mail)]
    host = urlsplit(text(source_url)).hostname or ""
    domain = host[4:] if host.startswith("www.") else host
    own = [mail for mail in found if domain and mail.lower().endswith("@" + domain)]
    retained = own or found
    return retained[0] if retained else ""


def is_noise(mail):
    local, _, domain = mail.lower().partition("@")
    return local in NOISE_LOCALS or domain in NOISE_DOMAINS


def phone(pages):
    """Téléphone : les numéros fixes d'abord, les mobiles ensuite, en XX XX XX XX XX."""
    found = []
    for page in pages:
        for raw in PHONE.findall(text(page.get("text"))):
            number = re.sub(r"\D", "", raw)
            if number.startswith("33"):
                number = "0" + number[2:]
            if len(number) == 10 and number.startswith("0"):
                found.append(" ".join(number[i : i + 2] for i in range(0, 10, 2)))
    found = dedupe(found)
    fixed = [value for value in found if value.startswith(("01", "02", "03", "04", "05", "09"))]
    mobile = [value for value in found if value.startswith(("06", "07"))]
    retained = fixed or mobile
    return retained[0] if retained else ""


def contains(line, term):
    """Terme reconnu dans la ligne. Les plus courts exigent une frontière de mot."""
    lowered = line.lower()
    if len(term) <= 3:
        return re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", lowered) is not None
    return term in lowered


def amenities(pages):
    """Équipements : les lignes les plus courtes sont les plus lisibles."""
    rows = []
    for page in pages:
        for line in lines(page):
            if len(line) > 80:
                continue
            if any(contains(line, term) for term in AMENITIES):
                rows.append(line)
    rows = dedupe(rows)
    rows.sort(key=len)
    return rows[:MAX_AMENITIES]


def split_room(line):
    """« Chambre Classique 18 m² » → nom, puis description."""
    parts = line.split()
    cut = len(parts)
    for index, part in enumerate(parts):
        if any(character.isdigit() for character in part):
            cut = index
            break
    name = " ".join(parts[:cut]).strip(" -–—:·,")
    rest = " ".join(parts[cut:]).strip(" -–—:·,")
    return name, rest


def room_description(line, repeated_lines):
    """Description d'une chambre : la ligne suivante, si elle décrit sans être un titre."""
    if not line or line in repeated_lines or ROOM_HEAD.match(line):
        return ""
    if len(line) <= 20 and SURFACE.match(line):
        return line
    if 25 <= len(line) <= 200 and " " in line and not line.endswith((":", " :")):
        return line
    return ""


def rooms(pages):
    """Chambres : les titres qui commencent par un type d'hébergement, texte de la page."""
    central = repeated(pages, max(3, len(pages) // 2))
    rows, seen = [], set()
    for page in pages:
        page_lines = lines(page)
        for index, line in enumerate(page_lines):
            if len(line) > MAX_ROOM_LINE or not ROOM_HEAD.match(line) or line in central:
                continue
            # « La suite et les chambres » est un titre de menu, pas une chambre.
            if re.match(r"^(la|le|les|l')\s", line.lower()):
                continue
            name, rest = split_room(line)
            if len(name.split()) < 2 or name.lower() in STRUCTURE_LINES:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            following = page_lines[index + 1] if index + 1 < len(page_lines) else ""
            rows.append(
                {"name": name, "description": rest or room_description(following, central)}
            )
    return rows[:MAX_ROOMS]


def read_hotel(report):
    """Les six informations que le document attend, lues dans la collecte."""
    pages = relevant_pages(report)
    return {
        "name": hotel_name(pages),
        "address": address(pages),
        "email": emails(pages, report.get("source_url")),
        "phone": phone(pages),
        "amenities": amenities(pages),
        "rooms": rooms(pages),
    }
