from fastapi import FastAPI, HTTPException, Body
from dossier import get_dossier_by_token
from pathlib import Path
import json
from datetime import datetime, timezone

app = FastAPI(title="Pierre-ai Studio API")

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
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(dossier, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde: {str(e)}")
        
    return {"status": "success", "updated_at": dossier["updated_at"]}
