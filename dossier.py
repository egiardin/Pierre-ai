import os
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

DOSSIERS_DIR = "dossiers"

def create_hotel_dossier(slug: str, text_data: dict, media_data: list) -> dict:
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
            
    magic_link = f"/studio/{token}"
    
    project_data = {
        "slug": slug,
        "token": token,
        "magic_link": magic_link,
        "expires_at": expires_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data": text_data,
        "media": media_data
    }
    
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump(project_data, f, ensure_ascii=False, indent=2)
        
    log_for_google_sheet(project_data)
    return project_data

def get_dossier_by_token(token: str) -> dict:
    """
    Vérifie le token d'accès, charge le projet depuis dossiers/*/project.json
    et s'assure que la date d'expiration (expires_at) n'est pas dépassée.
    Alias/redirection logique de verify_token.
    """
    return verify_token(token)

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

def log_for_google_sheet(dossier: dict):
    """
    Prépare ou pousse le payload pour automatiser l'envoi d'email depuis Google Sheets.
    """
    data = dossier.get("data", {})
    if isinstance(data, dict):
        email = data.get("email")
        name = data.get("name")
    else:
        email = getattr(data, "email", None)
        name = getattr(data, "name", None)
        
    slug = dossier.get("slug")
    token = dossier.get("token")
    expires_at = dossier.get("expires_at")
    magic_link = dossier.get("magic_link", f"/studio/{token}")
    
    payload = {
        "hotel_name": name,
        "email": email,
        "magic_link": magic_link,
        "expires_at": expires_at,
        "slug": slug
    }
    
    # Placeholder pour intégration Google Sheets / webhook
    print(f"[GoogleSheet Log] Payload préparé pour {slug}: {payload}")
    return payload
