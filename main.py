import os
import secrets
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Header, HTTPException
from pydantic import BaseModel

from dossier import get_dossier_by_token
from pipeline import runner, workspace

# Charge le .env s'il existe. À appeler avant de lire les variables plus bas.
load_dotenv()

app = FastAPI(title="Pierre-ai Studio API")

# Jeton partagé avec l'appelant (tableur ou site). Absent, l'import reste fermé.
IMPORT_TOKEN = os.environ.get("PIPELINE_TOKEN", "")

# File de traitement : un client à la fois, partagée par tout le service.
queue = runner.Runner()


def require_token(token):
    """L'import crée un dossier et lance un crawl : il n'est jamais ouvert."""
    if not IMPORT_TOKEN:
        raise HTTPException(status_code=503, detail="Import non configuré : jeton absent.")
    if not token or not secrets.compare_digest(token, IMPORT_TOKEN):
        raise HTTPException(status_code=401, detail="Jeton d'import invalide.")


def check_url(value):
    parts = urlsplit(value or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(status_code=400, detail="URL HTTP(S) complète requise.")
    return value


class ImportRequest(BaseModel):
    id: str
    url: str


@app.get("/studio/{token}")
def get_studio(token: str):
    """
    Vérifie la validité du token. Si valide, renvoie les données pré-remplies.
    Si expiré ou invalide, renvoie une 404/410 explicite.
    """
    dossier = get_dossier_by_token(token)
    if not dossier:
        raise HTTPException(status_code=410, detail="Token invalide ou expiré.")
    return dossier


@app.post("/studio/{token}/update")
def update_studio(token: str, payload: dict = Body(...)):
    """
    Sauvegarde les modifications faites par le client sur son template et ses textes.
    """
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    dossier = get_dossier_by_token(token)
    if not dossier:
        raise HTTPException(status_code=410, detail="Token invalide ou expiré.")

    slug = dossier.get("slug")
    dossier_path = Path("dossiers") / slug
    project_file = dossier_path / "project.json"

    if not project_file.exists():
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    # Mettre à jour les données et/ou les médias
    if "data" in payload:
        dossier["data"] = payload["data"]
    if "media" in payload:
        dossier["media"] = payload["media"]

    dossier["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        with open(project_file, "w", encoding="utf-8") as f:
            json.dump(dossier, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde: {str(e)}")

    return {"status": "success", "updated_at": dossier["updated_at"]}


@app.post("/import", status_code=202)
def start_import(request: ImportRequest, x_pipeline_token: str = Header(default="")):
    """Reçoit {id, url} du tableur et met le client en file de traitement."""
    require_token(x_pipeline_token)
    check_url(request.url)
    try:
        accepted = queue.submit(request.id, request.url)
    except workspace.InvalidId as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not accepted:
        raise HTTPException(status_code=409, detail="Ce dossier est déjà en traitement.")
    return {"id": request.id, "step": "recue"}


@app.get("/pipeline/{id}")
def pipeline_status(id: str, x_pipeline_token: str = Header(default="")):
    """État d'avancement d'un dossier, tel que le manifeste le porte."""
    require_token(x_pipeline_token)
    try:
        manifest = workspace.load(workspace.DATA_DIR, id)
    except workspace.InvalidId as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not manifest:
        raise HTTPException(status_code=404, detail="Aucun traitement pour cet identifiant.")
    return manifest
