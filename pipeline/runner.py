"""Traitement d'un client de bout en bout, une file à la fois.

Un identifiant et une URL entrent ; un dossier organisé sort. Le manifeste porte
l'état à chaque étape : un traitement interrompu reste diagnosticable, et un
nouvel essai repart de ce que le dossier contient déjà.

La file est séquentielle. Une collecte est gourmande en navigateur, en réseau et
en temps : les faire courir ensemble saturerait la machine et ferait échouer tout
le monde.

Tout ce qui sort de la machine — l'extracteur, la lecture du site, l'envoi R2, le
webhook — est injectable. Le déroulé complet se teste donc sans navigateur, sans
clé et sans réseau.
"""

import asyncio
import os
import queue
import shutil
import threading
from pathlib import Path

from ingestion import read_report
from pipeline import assets, organize, pierre, publish, workspace
from pipeline import extract_site as extractor_factory
from pipeline.lecture import read_hotel


def default_collect():
    """Collecte réelle : l'extracteur, chargé au dernier moment."""
    return extractor_factory()


async def collect(root, id, url, extract=None):
    """Lance la collecte, puis range son dossier brut sous data/{id}/crawl.

    L'extracteur écrit où il l'entend, hors du dossier de travail : on déplace son
    résultat pour tout garder au même endroit, puis le tri le supprimera.
    """
    extract = extract or default_collect()
    folder = workspace.workspace(root, id)
    crawl = folder / "crawl"
    produced = Path(await extract(url))
    if crawl.exists():
        shutil.rmtree(crawl)
    shutil.move(str(produced), str(crawl))
    return crawl


def tri(root, id, report, crawl):
    """Photos retenues, logos de marque et refus motivés, puis la collecte brute disparaît.

    Supprimer le brut dès le tri évite d'accumuler sur la machine des photos que
    l'on a déjà classées : seules les images retenues et les JSON restent.
    """
    folder = workspace.workspace(root, id)
    rows = assets.select_photos(report)
    photos = assets.copy_photos(rows, crawl, folder / "images")
    candidates = assets.logo_candidates(report, {row["url"] for row in rows})
    logos, refused = assets.download_logos(
        candidates, folder / "logos", photos_dir=folder / "images"
    )
    shutil.rmtree(crawl, ignore_errors=True)
    return photos, logos, refused


def organisation(root, id, report, extracted, photos, logos, refused, debut, fin):
    """Écrit infos.json, sources.json, site.json et pierre.json dans hotel/."""
    folder = workspace.workspace(root, id)
    infos = organize.build_infos(report, extracted, id, photos, logos, debut, fin)
    site, provenance = organize.build_site(report, extracted, id, photos)
    suggestions = pierre.build_pierre(infos)
    sources = {
        "source_url": report.get("source_url"),
        "collecte": {
            "debut": debut,
            "fin": fin,
            "statut": report.get("status"),
            "limite": report.get("limit"),
        },
        "pages": provenance["pages"],
        "media": provenance["media"],
        "defaults": provenance["defaults"],
        "logos": [
            {
                "file": logo["file"],
                "url": logo["url"],
                "pages": logo["pages"],
                "raison": logo["raison"],
            }
            for logo in logos
        ],
        "logos_refuses": refused,
    }
    organize.write_collection(folder, infos, sources, site, suggestions)
    return infos


async def run_one(root, id, url, extract=None, classify=None, upload=None, notify_url=None):
    """Traite un client de bout en bout et renvoie le manifeste final.

    L'ordre des étapes n'est pas négociable : la collecte alimente le tri, le tri
    alimente l'organisation, l'organisation alimente le document du studio, et
    l'envoi ne supprime les fichiers lourds qu'une fois ceux-ci partis.
    """
    root = Path(root)
    workspace.check_id(id)
    workspace.create(root, id)
    manifest = workspace.save(root, id, workspace.new_manifest(id, url))

    notify_url = notify_url if notify_url is not None else os.environ.get("PIPELINE_WEBHOOK", "")
    upload = upload or publish.publish_folder
    classify = classify or read_hotel

    try:
        debut = workspace.now()
        crawl = await collect(root, id, url, extract=extract)
        report = read_report(crawl)
        workspace.advance(
            root, id, manifest, "collecte", counts={"pages": report.get("page_count")}
        )

        photos, logos, refused = tri(root, id, report, crawl)
        workspace.advance(
            root, id, manifest, "tri", counts={"photos": len(photos), "logos": len(logos)}
        )

        extracted = classify(report)
        fin = workspace.now()
        infos = organisation(
            root, id, report, extracted, photos, logos, refused, debut, fin
        )
        workspace.advance(root, id, manifest, "organisation")

        sent = upload(workspace.workspace(root, id), id)
        workspace.advance(
            root,
            id,
            manifest,
            "envoi",
            counts={"envoyes": len(sent["sent"]), "octets_liberes": sent["freed_bytes"]},
        )

        workspace.advance(root, id, manifest, "prete")
        # Réponse attendue par Google Sheets : l'identifiant et le lien de la démo.
        publish.notify(notify_url, publish.sheet_payload(id))
        return manifest
    except Exception as error:
        workspace.fail(root, id, manifest, error)
        raise


class Runner:
    """File séquentielle : un client à la fois, dans l'ordre d'arrivée."""

    def __init__(self, root=workspace.DATA_DIR, worker=run_one):
        self.root = Path(root)
        self.worker = worker
        self.pending = queue.Queue()
        self.thread = None
        self.active = None
        self.lock = threading.Lock()

    def start(self):
        """Démarre le fil de traitement si besoin, et se renvoie pour l'enchaînement."""
        with self.lock:
            if not (self.thread and self.thread.is_alive()):
                self.thread = threading.Thread(
                    target=self._loop, daemon=True, name="pipeline"
                )
                self.thread.start()
        return self

    def known(self):
        """Identifiants déjà en attente ou en cours de traitement."""
        with self.lock:
            waiting = {item[0] for item in self.pending.queue}
            actifs = {self.active} if self.active else set()
        return waiting | actifs

    def submit(self, id, url):
        """Met un client en file. Refuse un identifiant déjà en attente ou en cours."""
        workspace.check_id(id)
        if id in self.known():
            return False
        self.pending.put((id, url))
        self.start()
        return True

    def _loop(self):
        while True:
            id, url = self.pending.get()
            with self.lock:
                self.active = id
            try:
                asyncio.run(self.worker(self.root, id, url))
            except Exception:
                # Le manifeste porte déjà la raison de l'échec : le fil doit survivre.
                pass
            finally:
                with self.lock:
                    self.active = None
                self.pending.task_done()
