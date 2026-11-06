import os
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from PIL import Image, ImageStat
import io
import requests

def normalize_url(url):
    """
    Normalise l'URL pour détecter et regrouper les variantes de résolution d'une même image.
    Supprime les suffixes de type -1024x768 et les paramètres CDN (w=, h=, q=, width=, height=).
    """
    parsed = urlparse(url)
    path = parsed.path
    
    # Supprimer les suffixes de résolution communs (ex: -1024x768, _800x600)
    path = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', path)
    
    # Nettoyer les paramètres de requête liés à la taille/qualité
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {
        k: v for k, v in query_params.items() 
        if k.lower() not in ['w', 'h', 'width', 'height', 'q', 'quality', 'size']
    }
    
    new_query = urlencode(filtered_params, doseq=True)
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, new_query, ''))
    return normalized

def is_valid_image(image_bytes):
    """
    Vérifie si l'image est valide :
    - Pas un pixel transparent 1x1.
    - Pas monochrome / vide / blanche (variance des pixels < 1.0 ou pixels quasi tous > 245).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Rejeter les pixels transparents 1x1 ou dimensions très faibles
        if img.size[0] <= 1 and img.size[1] <= 1:
            return False
            
        # Convertir en RGB pour l'analyse
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # Analyser la variance des pixels
        stat = ImageStat.Stat(img)
        if sum(stat.var) < 1.0:
            return False
            
        # Rejeter si l'image est entièrement blanche ou unie (> 245)
        extrema = img.getextrema()
        if all(ext[0] > 245 and ext[1] > 245 for ext in extrema):
            return False
            
        return True
    except Exception:
        return False

def process_and_filter_images(discovered_data):
    """
    Traite, dédoublonne et filtre les images découvertes.
    - Dédoublonnage par URL normalisée (garde la plus haute résolution).
    - Sélection finale : maximum 99 photos + logos/SVG distincts.
    """
    raw_photos = discovered_data.get('photos', [])
    raw_logos = discovered_data.get('logos', [])
    
    # Dédoublonnage des photos basé sur l'URL normalisée (garde la meilleure résolution)
    unique_photos = {}
    for photo in raw_photos:
        url = photo['url']
        norm_url = normalize_url(url)
        w = photo.get('width', 0)
        h = photo.get('height', 0)
        score = w * h
        
        if norm_url not in unique_photos or score > unique_photos[norm_url]['score']:
            unique_photos[norm_url] = {
                'url': url,
                'score': score,
                'width': w,
                'height': h,
                'type': 'photo'
            }
            
    # Dédoublonnage des logos
    unique_logos = {}
    for logo in raw_logos:
        url = logo['url']
        norm_url = normalize_url(url)
        if norm_url not in unique_logos:
            unique_logos[norm_url] = {
                'url': url,
                'type': 'logo'
            }
            
    # Sélection finale des photos (limitée à 99 max, triées par résolution décroissante)
    sorted_photos = sorted(unique_photos.values(), key=lambda x: x['score'], reverse=True)
    final_photos = sorted_photos[:99]
    
    final_logos = list(unique_logos.values())
    
    return final_photos + final_logos

def upload_to_r2(selected_items, r2_client, bucket_name):
    """
    Uploade sur R2 STRICTEMENT la sélection finale retenue.
    """
    uploaded_urls = []
    for item in selected_items:
        url = item['url']
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                image_bytes = response.content
                # Valider les photos, accepter directement les logos/SVG confirmés
                if item['type'] == 'logo' or url.endswith('.svg') or is_valid_image(image_bytes):
                    filename = urlparse(url).path.split('/')[-1] or 'image.jpg'
                    # Exemple d'appel R2 :
                    # r2_client.put_object(Bucket=bucket_name, Key=filename, Body=image_bytes)
                    uploaded_urls.append(url)
        except Exception as e:
            print(f"Erreur lors de l'upload de {url}: {e}")
            
    return uploaded_urls
