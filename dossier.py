import os
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

DOSSIERS_DIR = "dossiers"

def create_hotel_dossier(slug: str, data: dict, media: list) -> dict:
    """
    Crée ou met à jour le dossier d'un hôtel sous dossiers/{slug}/project.json.
    Génère un token sécurisé et une date d'expiration à J+7 UTC.
    """
    dossier_path = Path(DOSSIERS_DIR) / slug
    dossier_path.mkdir(parents=True, exist_ok=True)
    
    project_file = dossier_path / "project.json"
    
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    
    if project_file.exists():
        try:
            with open(project_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if 'token' in existing_data:
                    token = existing_data['token']
                if 'expires_at' in existing_data:
                    expires_at = existing_data['expires_at']
        except Exception:
            pass
            
    project_data = {
        "slug": slug,
        "token": token,
        "expires_at": expires_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
        "media": media
    }
    
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump(project_data, f, ensure_ascii=False, indent=2)
        
    return project_data

def verify_token(token: str) -> dict:
    """
    Vérifie le token d'accès, charge le projet depuis dossiers/*/project.json
    et s'assure que la date d'expiration (expires_at) n'est pas dépassée.
    """
    dossiers_path = Path(DOSSIERS_DIR)
    if not dossiers_path.exists():
        return None
        
    for slug_dir in dossiers_path.iterdir():
        if slug_dir.is_dir():
            project_file = slug_dir / "project.json"
            if project_file.exists():
                try:
                    with open(project_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                        if project_data.get("token") == token:
                            expires_at_str = project_data.get("expires_at")
                            if expires_at_str:
                                expires_at = datetime.fromisoformat(expires_at_str)
                                if datetime.now(timezone.utc) <= expires_at:
                                    return project_data
                            return None
                except Exception:
                    continue
                    
    return None
