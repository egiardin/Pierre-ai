# Pierre-ai

Studio de démonstration pour hôtels. Un hôtel fournit l'adresse de son site ;
Pierre en relève le contenu et les photos, publie le tout, et renvoie un lien où
l'hôtelier construit sa démo.

Le dépôt contient deux ensembles :

- **`pipeline/` et les modules Python à la racine** — la collecte et la
  publication (le « backend »).
- **`web/`** — le parcours de démonstration (React + TypeScript + Vite).

---

## 1. Le flux complet

```
Site Pierre ──(formulaire)──▶ Google Sheet ──{"id","url"}──▶ POST /import
                                                                    │
                                                                    ▼
                                     collecte → tri → organisation → envoi R2
                                                                    │
                                                                    ▼
                                    POST {PIPELINE_WEBHOOK}  {"ID","lien demo"}
                                                                    │
                                                                    ▼
                                                        Google Sheet : colonne « lien demo »
                                                                    │
                            le client ouvre {DEMO_BASE}/{id}         ▼
                                   web : /demo/{id} → lit site.json depuis R2
                                   bienvenue → template → studio
```

Deux idées portent tout le reste :

1. **Le lien ne porte qu'un identifiant.** `{DEMO_BASE}/{id}` ; le même `id` est
   le nom du dossier dans le compartiment R2, donc la page se retrouve seule.
2. **Le dossier part sur R2, la machine se libère.** Les fichiers lourds
   (photos, logos) sont envoyés *puis* supprimés en local ; les JSON partent
   aussi mais restent en local, car ils sont légers et le studio les lit.

---

## 2. Arborescence

```
Pierre-ai/
├── main.py                API FastAPI : /import, /pipeline/{id}, /studio/{token}
├── dossier.py             Ancien mécanisme « magic link » (voir §7, legacy)
├── ingestion.py           Pont rapport d'extraction → SiteDocument
├── studio_schema.py       Contrat site.json (miroir de web/src/document/types.ts)
├── catalog.py, discover.js  Copies d'origine de l'extracteur (inactives)
│
├── pipeline/              Le traitement, étape par étape
│   ├── __init__.py        Chargement paresseux de l'extracteur
│   ├── runner.py          Orchestration + file séquentielle (un client à la fois)
│   ├── workspace.py       Dossier de travail par id + manifeste d'état
│   ├── assets.py          Tri des médias (photos retenues, logos de marque)
│   ├── lecture.py         Lecture locale du site (regex + lexique, sans modèle)
│   ├── organize.py        Écrit infos.json / sources.json / site.json / pierre.json
│   ├── pierre.py          Suggestions de l'assistant, calculées hors ligne
│   └── publish.py         Envoi R2 + webhook sortant
│
├── Extraction/            L'extracteur autonome (Playwright)
│   └── pierre_extract/    extractor.py, discover.js, catalog.py, network.py
│
├── tests/                 Tests hors ligne du pipeline
├── data/                  Dossiers de travail (créé à l'exécution, non versionné)
│
└── web/                   Le frontend
    └── src/
        ├── main.tsx, App.tsx
        ├── styles.css
        ├── document/      Contrat + validation + application des modifications
        ├── demo/          Le parcours de démonstration
        ├── studio/        L'atelier (barre, cadres, assistant)
        ├── editor/        Outils d'édition (texte, photo, sommaire)
        ├── template/      Le rendu du site + ses sections
        └── data/site.demo.json   Démonstration locale (repli)
```

---

## 3. Le contrat partagé

`site.json` est l'objet unique échangé entre le backend, le studio et plus tard
l'agent Pierre. Il est défini deux fois, à l'identique :

- Python : [`studio_schema.py`](studio_schema.py) (`SCHEMA_VERSION = 1`)
- TypeScript : [`web/src/document/types.ts`](web/src/document/types.ts)

Structure :

```jsonc
{
  "schema_version": 1,
  "slug": "hotel-cinq-terres",
  "version": 1,
  "status": "draft",              // "draft" | "published"
  "pages": [ { "id": "home", "sections": [ /* Section[] */ ] } ],
  "media": [ /* MediaItem[] : id, file, width, height, source, status, alt */ ]
}
```

Types de section : `hero`, `rooms`, `services`, `gallery`, `contact`.
Le rendu ([`SiteRenderer.tsx`](web/src/template/SiteRenderer.tsx)) fait un
`switch` exhaustif sur `section.type` : ajouter une variante sans la rendre
produit une erreur de compilation.

**Aucune écriture directe sur le document.** Toute modification passe par un
`Patch` appliqué par [`applyPatch`](web/src/document/patch.ts) :

```ts
{ op: "setText",  sectionId, itemId?, field, value }
{ op: "setPhoto", sectionId, itemId?, photoId }
```

---

## 4. Le pipeline Python

### Étapes ([`pipeline/runner.py`](pipeline/runner.py))

L'ordre n'est pas négociable : chaque étape alimente la suivante.

| Étape          | Ce qu'elle fait                                              | Fichier |
| -------------- | ------------------------------------------------------------ | ------- |
| `recue`        | Crée `data/{id}/` et le manifeste                            | `workspace.py` |
| `collecte`     | Lance l'extracteur, range le brut dans `data/{id}/crawl/`    | `runner.collect` |
| `tri`          | Retient les photos, télécharge les logos, supprime le brut   | `assets.py` |
| `organisation` | Écrit `infos.json`, `sources.json`, `site.json`, `pierre.json` | `organize.py` |
| `envoi`        | Publie sur R2, puis libère les médias                        | `publish.py` |
| `prete`        | Écrit l'état final, prévient le webhook                      | `runner.run_one` |

Un échec écrit `echec` dans le manifeste et **laisse le dossier en place** pour
le diagnostic.

### Lecture du site

L'étape d'organisation commence par lire le site **sans modèle ni clé d'API** :
[`pipeline/lecture.py`](pipeline/lecture.py) retrouve six informations (nom,
adresse, email, téléphone, équipements, chambres) à partir du texte des pages, par
expression régulière et petits lexiques — la méthode du workflow de Sacha. Seules
des chaînes réellement présentes dans le texte sont renvoyées ; `organize.field`
repasse ensuite dessus pour marquer « à confirmer » ce qu'il ne retrouve pas mot
pour mot. Rien n'est inventé, et aucune requête sortante n'est facturée.

### Dossier de travail

```
data/{id}/
├── manifest.json     état + historique + compteurs + erreur éventuelle
├── images/           photos retenues (supprimées après envoi)
├── logos/            logos retenus (supprimés après envoi)
└── hotel/            infos.json, sources.json, site.json, pierre.json
```

`id` vient de l'extérieur : il est vérifié (`^[A-Za-z0-9_-]{1,64}$`) avant tout
usage, sinon il pourrait désigner un chemin hors du dossier de travail.

### File d'attente

`Runner` traite **un client à la fois**, dans un fil dédié. Une collecte sature
navigateur, réseau et mémoire : les faire courir ensemble ferait échouer tout le
monde. `submit` refuse un identifiant déjà en attente ou en cours.

### Provenance et prudence

`organize.py` attache à chaque valeur son origine (l'extrait de page où elle a
été trouvée) et un niveau de confiance : `confirmee`, `a_confirmer` ou `absente`.
`pierre.py` ne propose que des passages **verbatim** du site et ne devine jamais
une photo de chambre.

---

## 5. Publication et lien de démo ([`pipeline/publish.py`](pipeline/publish.py))

- Préfixe des objets : `demos/{id}/…`.
- `images/` et `logos/` sont **envoyés puis effacés** (envoi confirmé d'abord).
- `hotel/` est **envoyé mais conservé** : c'est ce que la page de démo lit.
- Contenu envoyé :

```
demos/{id}/images/photo-01.jpg
demos/{id}/logos/logo.svg
demos/{id}/hotel/infos.json
demos/{id}/hotel/sources.json
demos/{id}/hotel/site.json
demos/{id}/hotel/pierre.json
```

- L'adresse publique d'un média est **calculée**, jamais devinée :
  `{R2_PUBLIC_BASE}/demos/{id}/images/photo-01.jpg`. Elle est écrite dans
  `site.json` avant même l'envoi.
- Le lien remis au client : `{DEMO_BASE}/{id}`
  (défaut `https://demo.pierre-ai.com`).
- Le payload du webhook : `{"ID": id, "lien demo": "{DEMO_BASE}/{id}"}`.

---

## 6. Le frontend (`web/`)

### Parcours de démonstration

[`DemoFlow.tsx`](web/src/demo/DemoFlow.tsx) tient un état `Etape` — pas de
routeur : `bienvenue → templates → studio`.

1. **Bienvenue** — [`WelcomePage.tsx`](web/src/demo/WelcomePage.tsx) : Pierre
   annonce les 6 étapes du parcours.
2. **Template** — [`TemplatePage.tsx`](web/src/demo/TemplatePage.tsx) : carrousel
   avec flèches, aperçu réel de chaque template, sélection en vert.
   Le template **range** les sections, il n'invente rien
   ([`templates.ts`](web/src/demo/templates.ts)).
3. **Studio** — [`StudioShell.tsx`](web/src/studio/StudioShell.tsx) : édition et
   aperçu du site, avec les mêmes boutons Retour / Suivant en bas.

### Chargement du dossier

[`dossier.ts`](web/src/demo/dossier.ts) lit l'identifiant dans l'URL
(`/demo/{id}` ou `?id={id}`) et va chercher
`{VITE_R2_PUBLIC_BASE}/demos/{id}/hotel/site.json`.
Sans `VITE_R2_PUBLIC_BASE`, ou si R2 ne répond pas, la page retombe sur la
démonstration locale `web/src/data/site.demo.json` : mieux vaut un aperçu qu'une
page blanche.

### Studio

- Un seul document, un seul chemin d'écriture : un réducteur pur
  ([`StudioShell.tsx`](web/src/studio/StudioShell.tsx)) applique les `Patch`, ce
  qui rend l'annulation fiable (Ctrl/Cmd + Z).
- Le template ne modifie rien : il **demande** une action via
  [`studio-context.ts`](web/src/studio/studio-context.ts) `useStudio()`.
- La barre de sections ([`SectionOutline.tsx`](web/src/editor/SectionOutline.tsx))
  liste **toutes** les pages et leurs sections.

---

## 7. Legacy

- [`dossier.py`](dossier.py) + les routes `/studio/{token}` de `main.py`
  appartiennent à un **ancien mécanisme de « magic link »** (token à expiration
  à J+7). Il n'est **pas** utilisé par le parcours de démonstration actuel, qui
  passe par R2. À retirer ou à raccorder plus tard, au choix.
- `catalog.py` et `discover.js` à la racine sont des copies d'origine de
  l'extracteur ; l'extracteur actif est `Extraction/pierre_extract/`.

---

## 8. Variables d'environnement

| Variable | Côté | Rôle |
| --- | --- | --- |
| `PIPELINE_TOKEN` | backend | Jeton partagé exigé par `/import` et `/pipeline/{id}` (en-tête `X-Pipeline-Token`). Absent, l'import est fermé (503). |
| `R2_ACCOUNT_ID` | backend | Identifiant de compte Cloudflare. |
| `R2_ACCESS_KEY_ID` | backend | Clé d'accès R2 (jeton API S3). |
| `R2_SECRET_ACCESS_KEY` | backend | Secret d'accès R2. |
| `R2_BUCKET_NAME` | backend | Nom du compartiment. |
| `R2_PUBLIC_BASE` | backend | Base publique du compartiment, écrite dans `site.json`. |
| `DEMO_BASE` | backend | Base du lien de démo. Défaut `https://demo.pierre-ai.com`. |
| `PIPELINE_WEBHOOK` | backend | URL qui reçoit `{"ID","lien demo"}`. Vide = aucun appel. |
| `VITE_R2_PUBLIC_BASE` | frontend | **La même** base publique, lue par la page de démo. |

> `R2_PUBLIC_BASE` (backend) et `VITE_R2_PUBLIC_BASE` (frontend) doivent
> désigner **la même** adresse publique.

---

## 9. Démarrage en local

### 9.1 Backend (pipeline)

```bash
cd /Users/enzo/Desktop/Pierre-ai
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic boto3 playwright pillow python-dotenv
python -m playwright install chromium
```

Les variables se lisent dans un fichier **`.env`** à la racine (chargé
automatiquement par `main.py`) :

```ini
PIPELINE_TOKEN=un-secret-partage
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=pierre-demo
R2_PUBLIC_BASE=https://pub-xxxxxxxx.r2.dev     # voir §10
DEMO_BASE=http://localhost:5173                # en local
PIPELINE_WEBHOOK=                              # URL de l'Apps Script
```

Lancer l'API :

```bash
uvicorn main:app --reload --port 8000
```

Déclencher un traitement (ce que fera Google Sheets) :

```bash
curl -X POST http://localhost:8000/import \
  -H "Content-Type: application/json" \
  -H "X-Pipeline-Token: un-secret-partage" \
  -d '{"id":"hotel-test","url":"https://adresse-de-votre-hotel.fr/"}'
```

Suivre l'avancement :

```bash
curl -H "X-Pipeline-Token: un-secret-partage" \
  http://localhost:8000/pipeline/hotel-test
```

Le traitement tourne en tâche de fond ; `manifest.json` porte l'étape courante.
À la fin : les fichiers sont sur R2, et le webhook a reçu le lien.

### 9.2 Frontend (page de démonstration)

```bash
cd /Users/enzo/Desktop/Pierre-ai/web
npm install
echo 'VITE_R2_PUBLIC_BASE=https://pub-xxxxxxxx.r2.dev' > .env.local
npm run dev
```

Ouvrir la démo du dossier traité :

```
http://localhost:5173/demo/hotel-test
```

(`http://localhost:5173/?id=hotel-test` fonctionne aussi.)

Pour vérifier la page sans R2, ouvrir simplement `http://localhost:5173/` :
la démonstration locale s'affiche.

---

## 10. Configurer Cloudflare R2

1. **Compartiment** : créer le compartiment qui porte `R2_BUCKET_NAME`.
2. **Accès public** : activer « Public access » (sous-domaine `r2.dev`) ou
   brancher un domaine personnalisé. C'est cette adresse qui va dans
   `R2_PUBLIC_BASE` / `VITE_R2_PUBLIC_BASE`.
3. **Jeton API S3** : créer un jeton avec droit de lecture/écriture sur ce
   compartiment. Renseigner `R2_ACCESS_KEY_ID` et `R2_SECRET_ACCESS_KEY`.
   `R2_ACCOUNT_ID` est l'identifiant du compte Cloudflare.
4. **CORS** : la page de démo (autre origine) lit `site.json` en `fetch` ; le
   compartiment doit l'autoriser. Exemple de règle :

```json
[
  {
    "AllowedOrigins": ["http://localhost:5173", "https://demo.pierre-ai.com"],
    "AllowedMethods": ["GET"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## 11. Brancher Google Sheets

Deux sens de communication, prêts à l'emploi via [`scripts/apps_script.gs`](scripts/apps_script.gs).

**Prérequis : le backend doit être en ligne** (le Sheet ne peut pas atteindre
`localhost`). Voir la section 11.3 — déploiement Docker (Fly.io, Railway…).

### 11.1 La feuille

Nommer la première feuille **`Imports`**, ligne 1 = en-têtes :

| A : ID | B : URL | C : Statut | D : Lien demo |
|---|---|---|---|
| `demo-5terres` | `https://5terres-hotel.fr/fr/` | *(laissé vide = nouveau)* | *(rempli auto)* |

### 11.2 L'Apps Script

Dans le Sheet : *Extensions → Apps Script*, coller le contenu de
[`scripts/apps_script.gs`](scripts/apps_script.gs), puis dans les **propriétés
du script** (roue dentée) définir :

- `BACKEND_URL` = URL publique du backend (ex. `https://pierre-backend.fly.dev`)
- `PIPELINE_TOKEN` = même valeur que `PIPELINE_TOKEN` dans le `.env` du backend

Exécuter une fois la fonction **`installer()`** pour poser le déclencheur
`onEdit`. Ensuite : remplir ID + URL → le script appelle `POST /import` et
écrit « envoyé » ; quand le traitement est terminé, le backend appelle le
webhook et le script écrit « prêt » + le lien `https://studio.pierre-ai.fr/{id}`.

Pour le sens retour (backend → Sheet), déployer le script en **Web App**
(*Déployer → Nouvelle déploiement → Web App*, accès « Tous les utilisateurs ») :
l'URL en `…/exec` va dans `PIPELINE_WEBHOOK` côté backend.

> Le backend envoie exactement `{"ID": "...", "lien demo": "..."}`.

### 11.3 Déployer le backend en ligne (Docker)

Le dépôt contient un [`Dockerfile`](Dockerfile) (Python 3.12 + Chromium pour
Playwright) et un [`requirements.txt`](requirements.txt). Exemple avec Fly.io :

```bash
fly launch --dockerfile Dockerfile --name pierre-backend   # une fois
fly volumes create pierre_data --size 3 --region cdg        # disque persistant pour data/
fly secrets set PIPELINE_TOKEN=... R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... \
  R2_SECRET_ACCESS_KEY=... R2_BUCKET_NAME=pierre-demo \
  R2_PUBLIC_BASE=https://pub-....r2.dev DEMO_BASE=https://studio.pierre-ai.fr \
  PIPELINE_WEBHOOK=https://script.google.com/macros/s/.../exec
fly deploy
```

Le volume est monté sur `/app/data` dans `fly.toml` : sans lui, les dossiers
traités disparaîtraient au redémarrage et `/pipeline/{id}` renverrait 404.

Ensuite : `BACKEND_URL = https://pierre-backend.fly.dev` dans les propriétés
du script Apps Script.

---

## 12. Paiement Stripe (étape 4 du parcours)

Le bouton **Suivant** du studio mène à la page de paiement
([`web/src/demo/PaymentPage.tsx`](web/src/demo/PaymentPage.tsx)) : choix du
nombre de pages, **code de réduction facultatif**, puis redirection vers le
Checkout Stripe hébergé (la clé secrète ne sort jamais du backend).

Flux : `POST /checkout {id, pages, promo}` → session Stripe → retour
`{DEMO_BASE}/{id}?paid=1` → webhook signé `POST /stripe/webhook`
(`checkout.session.completed`) → `demos/{id}/hotel/site.json` passe à
`status: "paye"` sur R2 ([`payments.py`](payments.py)). Le front relit le
document en `no-cache`, donc la confirmation s'affiche toute seule.

**Configuration** :

| Variable | Où | Rôle |
|---|---|---|
| `STRIPE_SECRET_KEY` | `.env` backend | création des sessions (mode `sk_test_…` d'abord) |
| `STRIPE_WEBHOOK_SECRET` | `.env` backend | vérification de la signature du webhook |
| `PRIX_BASE_CENTS` | `.env` backend | tarif par page en centimes (défaut 4900 = 49 €) |
| `VITE_BACKEND_URL` | build front | ex. `https://pierre-backend.fly.dev` |
| `VITE_PRIX_BASE_CENTS` | build front | affichage du prix (le montant réel est imposé par le backend) |

**À faire dans le dashboard Stripe** :
1. Mode test d'abord (clés `sk_test_…` / `pk_test_…`).
2. *Coupons → Promotion codes* : créer ex. `PIERRE10` (-10 %) — c'est ce que
   l'hôtelier tape dans le champ « code de réduction » ; un code inconnu est
   refusé côté serveur (400) avant la création de la session.
3. *Developers → Webhooks* : ajouter l'endpoint `https://<backend>/stripe/webhook`
   sur l'événement `checkout.session.completed`, puis copier le secret dans
   `STRIPE_WEBHOOK_SECRET`.

**Test en local** : `stripe listen --forward-to localhost:8001/stripe/webhook`,
puis payer avec la carte de test `4242 4242 4242 4242`.

---

## 13. Tests

Pipeline (hors ligne : ni navigateur, ni clé, ni réseau) :

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Frontend (compilation TypeScript + build) :

```bash
cd web
npm run build
```

---

## 14. Points ouverts

- L'étape **5 Mise en ligne** (publication sur le domaine de l'hôtel) et
  **6 Dashboard** restent à implémenter ; la page « Merci » affichée après le
  paiement en tient lieu provisoirement.
- `.env` et `web/.env.local` sont fournis avec les valeurs R2 déjà remplies ; il
  reste à renseigner `PIPELINE_TOKEN` et les deux clés du jeton API R2.
- `boto3` n'est pas installé par défaut (il n'est chargé qu'au moment de
  l'envoi) : `pip install boto3` est nécessaire pour publier.
- `/studio/{token}` (legacy, §7) reste à retirer ou à raccorder.
