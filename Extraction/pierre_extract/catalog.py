"""Inventaire, dédoublonnage et galerie. Aucune dépendance navigateur."""

import hashlib
import html
import io
import json
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 30_000_000


class Catalog:
    def __init__(self, folder):
        self.folder = Path(folder)
        (self.folder / "photos").mkdir(parents=True, exist_ok=True)
        (self.folder / "previews").mkdir(exist_ok=True)
        self.photos, self.rejected, self.by_pixels = [], [], {}
        self.bytes_saved = 0

    def ingest(self, raw, source):
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                fmt = image.format
                if fmt not in ("JPEG", "PNG", "WEBP", "AVIF"):
                    return self.reject(source, "format_non_pris_en_charge")
                normalized = ImageOps.exif_transpose(image).convert("RGB")
                width, height = normalized.size
                # Ne pas éliminer automatiquement une photo portrait ou panoramique.
                if min(width, height) < 160 or width * height < 120000:
                    return self.reject(source, "petit_media_ou_icone")
                pixels = hashlib.sha256(
                    f"{width}x{height}:".encode() + normalized.tobytes()
                ).hexdigest()
                if pixels in self.by_pixels:
                    self.by_pixels[pixels]["sources"].append(source)
                    return "duplicate"
                if len(self.photos) >= 99:
                    return self.reject(source, "limite_99_photos")
                digest = hashlib.sha256(raw).hexdigest()
                ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}[fmt]
                file = f"photos/{digest}.{ext}"
                preview = f"previews/{digest}.jpg"
                (self.folder / file).write_bytes(raw)
                normalized.thumbnail((600, 400))
                normalized.save(self.folder / preview, quality=82)
                row = {
                    "id": digest,
                    "file": file,
                    "preview": preview,
                    "width": width,
                    "height": height,
                    "bytes": len(raw),
                    "sources": [source],
                }
                self.photos.append(row)
                self.by_pixels[pixels] = row
                self.bytes_saved += len(raw)
                return "saved"
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ):
            return self.reject(source, "image_invalide_ou_trop_grande")

    def reject(self, source, reason):
        self.rejected.append({"source": source, "reason": reason})
        return reason

    def write(self, report):
        report.update(
            photos=self.photos,
            rejected=self.rejected,
            photo_count=len(self.photos),
            original_bytes=self.bytes_saved,
        )
        temporary = self.folder / "report.tmp"
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.folder / "report.json")
        cards = []
        for p in self.photos:
            caption = html.escape(p["sources"][0].get("alt") or "Photo sans légende")
            cards.append(
                f'<figure><a href="{p["file"]}"><img loading="lazy" src="{p["preview"]}" alt="{caption}"></a>'
                f'<figcaption>{caption}<br>{p["width"]} × {p["height"]} · {len(p["sources"])} source(s)</figcaption></figure>'
            )
        document = """<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
<title>Photothèque Pierre</title><style>body{font:16px system-ui;background:#f1f7f3;color:#173f32;margin:30px}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px}
figure{margin:0;background:white;border-radius:12px;overflow:hidden}img{width:100%;height:200px;object-fit:contain}
figcaption{padding:12px;overflow-wrap:anywhere}</style>"""
        document += f"<h1>Photothèque Pierre — {len(self.photos)} photos</h1><p>Cliquer pour ouvrir le fichier original récupéré. Bilan dans report.json.</p><main>"
        (self.folder / "gallery.html").write_text(
            document + "".join(cards) + "</main></html>", encoding="utf-8"
        )
