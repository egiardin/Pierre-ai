"""Pipeline de collecte Pierre.

Un identifiant client et une URL entrent ; un dossier organisé sort, avec ses
photos, ses logos, son JSON d'information et les suggestions de Pierre.

L'extracteur vit dans son propre dossier et reste autonome : il n'est chargé
qu'à l'appel, là où il sert. Les parties pures de ce paquet restent ainsi
testables sans navigateur, sans clé d'API et sans réseau.
"""

import importlib.util
import sys
from pathlib import Path

EXTRACTION_DIR = Path(__file__).resolve().parent.parent / "Extraction"


def _path_ready():
    if str(EXTRACTION_DIR) not in sys.path:
        sys.path.insert(0, str(EXTRACTION_DIR))


def extract_site():
    """Fonction de collecte de l'extracteur, avec ses budgets et sa protection réseau."""
    _path_ready()
    from pierre_extract import extract_site as run

    return run


def network():
    """Validation SSRF et téléchargement borné de l'extracteur.

    Le module est chargé directement depuis son fichier : il ne dépend que de la
    bibliothèque standard, alors qu'importer le paquet complet tirerait Playwright
    et Pillow pour un simple contrôle d'adresse.
    """
    module = sys.modules.get("pierre_extract_network")
    if module is not None:
        return module
    path = EXTRACTION_DIR / "pierre_extract" / "network.py"
    spec = importlib.util.spec_from_file_location("pierre_extract_network", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["pierre_extract_network"] = module
    return module
