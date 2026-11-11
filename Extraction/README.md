# Extracteur Pierre V0.2 — un bloc autonome

Entrée unique : URL d'un site. Sortie : dossier local avec au maximum **99 photos**,
les textes des pages visitées, un inventaire sourcé et une galerie de contrôle.
Aucun appel Gemini, Sacha, R2, paiement ou email. Aucun ancien fichier remplacé.
Python 3.11+.

## Installer sur Mac

Décompresser et ouvrir le terminal dans le dossier `pierre-extracteur`.
Utiliser un environnement distinct pour ne pas changer l'installation précédente :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Extraire

```bash
python -m pierre_extract "https://5terres-hotel.fr/fr/"
```

L'appel Python équivalent, depuis un programme asynchrone :

```python
from pierre_extract import extract_site
folder = await extract_site("https://5terres-hotel.fr/fr/")
```

Le programme affiche les pages visitées puis la progression des téléchargements.
Il indique le chemin du résultat. Ouvrir `gallery.html` dans ce dossier.
Sur Mac, `open extractions` ouvre la liste des extractions dans le Finder.
Le fichier `report.json` détaille textes, photos, sources, échecs et limites.
Les fichiers originaux récupérés sont dans `photos/`, les aperçus dans `previews/`.

## Ce qui est extrait

- Pages du domaine de départ et de son éventuelle redirection initiale.
- Liens internes et sitemap standard `/sitemap.xml` (jusqu'à 4 documents).
- Priorité aux galeries, chambres, suites, spa, restaurant et services.
- `img`, `source`, `srcset`, attributs lazy usuels, `currentSrc`.
- Images de fond calculées, y compris pseudo-éléments.
- Liens explicites vers les images et métadonnées sociales.
- URL d'images demandées par le JavaScript.
- Défilement et quelques contrôles explicites de carrousel ; refus de cookies
  lorsque le bouton porte un libellé reconnu.
- Textes visibles et descriptions des pages visitées.

Une image chargée par un CDN externe peut être récupérée, mais nous ne crawlons
pas les pages HTML des sites externes. Les URL proviennent du site exploré :
leur pertinence pour l'hôtel doit être vérifiée dans la galerie.

## Limites et choix

- Maximum 99 fichiers photos uniques retenus, pas 99 URL candidates.
- Maximum 24 pages, 1500 URL candidates, 1800 requêtes.
- Budget découverte : 330 secondes ; budget global coopératif : 600 secondes.
  La fermeture du navigateur ou un téléchargement en cours peut dépasser légèrement.
- Budget réseau 350 Mo (jusqu'à 3 requêtes déjà en vol peuvent le dépasser).
- 12 Mo par téléchargement photo ; 4 Mo par ressource de rendu.
- JPEG, PNG, WebP et AVIF si pris en charge par Pillow installé.
- Petits médias ignorés : côté minimum 160 pixels ou surface <120000 pixels.
  Logos, SVG et icônes ne sont donc pas la cible de ce bloc photo.
- Original signifie fichier accessible téléchargé, pas original de l'appareil photo.
- Variantes `srcset` examinées par résolution décroissante. Dédoublonnage exact
  des pixels décodés : les versions redimensionnées ou recompressées peuvent
  rester plusieurs photos. Pas de suppression approximative risquant de perdre
  un cadrage utile. Choisir systématiquement la meilleure variante d'une même
  scène nécessitera une évolution du regroupement.
- Les images sont bloquées pendant le rendu pour économiser la bande passante,
  puis téléchargées une fois découvertes. Certaines galeries dépendant de l'état
  de chargement des images peuvent demander une adaptation.
- Pas de garantie d'exhaustivité : protections antibot, galeries personnalisées,
  iframes, shadow DOM et médias non exposés peuvent limiter la collecte.
- Un statut `complete_within_limits` signifie que le parcours borné s'est terminé,
  pas que toutes les photos du site ont été trouvées. Les événements détaillent
  limites de pages, candidats et photos. `partial` indique une interruption de temps/budget.
- Les relances créent un nouveau dossier sans écraser les résultats précédents.
- Utilisation CLI locale ; pas un service public prêt à être exposé.

## Sécurité réseau

Toutes les requêtes HTTP du navigateur sont interceptées et servies par un
client qui valide chaque destination/redirection et se connecte à l'IP validée
avec vérification TLS. Requêtes en écriture, WebSockets et service workers bloqués.
Ne pas exposer ce collecteur à des utilisateurs anonymes ; quotas par utilisateur,
isolation réseau/OS et politique de conservation restent nécessaires pour une API.
La galerie échappe les textes et ne charge aucun script ou image externe.
Les URL sources du rapport peuvent contenir des paramètres sensibles : garder
le dossier privé. R2 et politique de stockage feront l'objet d'un bloc séparé.

## Tests

```bash
python -m unittest discover -s tests -v
```

Le test navigateur utilise Chromium avec des réponses simulées, sans site externe.
Il vérifie HTML, CSS, srcset, lazy loading et image ajoutée par JavaScript.
Les autres tests vérifient la limite de 99, les doublons, les sources, les erreurs,
les adresses privées et les budgets.

## Organisation

- `extractor.py` : orchestration, navigation, découverte, budgets et téléchargements.
- `discover.js` : inspection du DOM rendu.
- `catalog.py` : validation images, fichiers, inventaire et galerie.
- `network.py` : transport HTTP borné et contrôle des adresses réseau.
- `__main__.py` : commande avec une URL.

Ce paquet est volontairement indépendant du worker V0.1. On le raccordera à
Pierre après validation de la collecte sur vos hôtels, sans migration de base.
