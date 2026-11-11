"""Tests hors ligne du pipeline de collecte.

Aucun navigateur, aucune clé d'API, aucun réseau : la collecte, la lecture du
site, l'envoi R2 et le webhook sont simulés. On vérifie l'enchaînement réel des
étapes, l'ordre « envoi d'abord, suppression ensuite » et le contenu du dossier.
"""

import asyncio
import json
import os
import tempfile
import threading
import unittest
from functools import partial
from pathlib import Path
from unittest import mock

from ingestion import relevant_pages
from pipeline import assets, organize, pierre, publish, runner, workspace
from studio_schema import validate_site

LONG_LINE = "Présentation " * 20


def report(with_logo=True):
    """Rapport d'extraction simulé : deux photos, un logo de marque répété."""
    candidates = {
        "https://hotel-test.fr/img/facade.jpg": [
            {"page": "https://hotel-test.fr/", "kind": "src", "alt": "Façade de l'hôtel"}
        ],
        "https://hotel-test.fr/img/chambre.jpg": [
            {"page": "https://hotel-test.fr/chambres", "kind": "src", "alt": ""}
        ],
    }
    if with_logo:
        candidates["https://hotel-test.fr/img/logo.svg"] = [
            {"page": "https://hotel-test.fr/", "kind": "src", "alt": "Logo"},
            {"page": "https://hotel-test.fr/chambres", "kind": "src", "alt": "Logo"},
        ]
    return {
        "schema_version": 1,
        "source_url": "https://hotel-test.fr/",
        "status": "complete_within_limits",
        "limit": None,
        "page_count": 2,
        "requests": 12,
        "network_bytes": 4096,
        "pages": [
            {
                "url": "https://hotel-test.fr/",
                "title": "Hôtel Test",
                "description": "Un hôtel de charme au centre-ville.",
                "text": f"Accueil\nHôtel Test\nUn hôtel de charme au centre-ville.\nWi-Fi gratuit\n{LONG_LINE}",
            },
            {
                "url": "https://hotel-test.fr/chambres",
                "title": "Chambres",
                "description": "",
                "text": "Accueil\nChambre Classique 18 m²\nSuite Junior 32 m²",
            },
        ],
        "photos": [
            {
                "id": "aaaa",
                "file": "photos/aaaa.jpg",
                "width": 1600,
                "height": 1000,
                "bytes": 10,
                "sources": [
                    {
                        "page": "https://hotel-test.fr/",
                        "kind": "src",
                        "alt": "Façade de l'hôtel",
                        "url": "https://hotel-test.fr/img/facade.jpg",
                    }
                ],
            },
            {
                "id": "bbbb",
                "file": "photos/bbbb.jpg",
                "width": 700,
                "height": 700,
                "bytes": 9,
                "sources": [
                    {
                        "page": "https://hotel-test.fr/chambres",
                        "kind": "src",
                        "alt": "",
                        "url": "https://hotel-test.fr/img/chambre.jpg",
                    }
                ],
            },
        ],
        "candidates": candidates,
        "events": [],
    }


def extracted():
    return {
        "name": "Hôtel Test",
        "address": "1 rue du Test, 75001 Paris",
        "email": "contact@hotel-test.fr",
        "phone": "01 02 03 04 05",
        "amenities": ["Wi-Fi gratuit", "Piscine extérieure"],
        "rooms": [{"name": "Chambre Classique", "description": "18 m²"}],
    }


def photos():
    """Photos déjà rangées, au format produit par le tri."""
    return [
        {
            "id": "aaaa",
            "file": "photo-01.jpg",
            "url": "https://hotel-test.fr/img/facade.jpg",
            "local_file": "photos/aaaa.jpg",
            "width": 1600,
            "height": 1000,
            "bytes": 10,
            "alt": "Façade de l'hôtel",
            "pages": ["https://hotel-test.fr/"],
            "score": 0.92,
        },
        {
            "id": "bbbb",
            "file": "photo-02.jpg",
            "url": "https://hotel-test.fr/img/chambre.jpg",
            "local_file": "photos/bbbb.jpg",
            "width": 700,
            "height": 700,
            "bytes": 9,
            "alt": "",
            "pages": ["https://hotel-test.fr/chambres"],
            "score": 0.41,
        },
    ]


def build_infos(report_data=None):
    return organize.build_infos(
        report_data or report(), extracted(), "cli-1", photos(), [], "2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"
    )


class FakeS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.uploads.append({"bucket": bucket, "key": key, "path": str(path)})


class WorkspaceTests(unittest.TestCase):
    def test_identifiants_refuses(self):
        for bad in ("../etc", "a/b", "", "x" * 65, "a b", None, 12):
            with self.assertRaises(workspace.InvalidId):
                workspace.check_id(bad)

    def test_identifiant_accepte(self):
        self.assertEqual(workspace.check_id("cli_01-A"), "cli_01-A")

    def test_creation_manifeste_et_avancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = workspace.create(tmp, "cli-1")
            for name in ("images", "logos", "hotel"):
                self.assertTrue((folder / name).is_dir(), name)

            manifest = workspace.save(tmp, "cli-1", workspace.new_manifest("cli-1", "https://x.fr/"))
            self.assertEqual(workspace.load(tmp, "cli-1")["step"], "recue")

            workspace.advance(tmp, "cli-1", manifest, "collecte", counts={"pages": 3})
            loaded = workspace.load(tmp, "cli-1")
            self.assertEqual(loaded["step"], "collecte")
            self.assertEqual(loaded["counts"]["pages"], 3)
            self.assertEqual([step["step"] for step in loaded["history"]], ["collecte"])

    def test_echec_conserve_le_dossier(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = workspace.save(tmp, "cli-1", workspace.new_manifest("cli-1", "https://x.fr/"))
            workspace.fail(tmp, "cli-1", manifest, "réseau indisponible")
            loaded = workspace.load(tmp, "cli-1")
            self.assertEqual(loaded["step"], workspace.FAILED)
            self.assertEqual(loaded["error"], "réseau indisponible")

    def test_aucun_manifeste(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(workspace.load(tmp, "absent"))


class AssetsTests(unittest.TestCase):
    def test_photos_classees_par_interet(self):
        rows = assets.select_photos(report())
        self.assertEqual([row["id"] for row in rows], ["aaaa", "bbbb"])
        self.assertGreater(rows[0]["score"], rows[1]["score"])

    def test_copie_renomme_et_ecarte_les_fichiers_absents(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "crawl"
            (source / "photos").mkdir(parents=True)
            (source / "photos" / "aaaa.jpg").write_bytes(b"a")
            kept = assets.copy_photos(assets.select_photos(report()), source, Path(tmp) / "images")
            self.assertEqual([row["file"] for row in kept], ["photo-01.jpg"])

    def test_candidates_logo_ecartent_les_photos(self):
        rows = assets.select_photos(report())
        urls = [row["url"] for row in assets.logo_candidates(report(), {r["url"] for r in rows})]
        self.assertIn("https://hotel-test.fr/img/logo.svg", urls)
        self.assertNotIn("https://hotel-test.fr/img/facade.jpg", urls)

    def test_telechargement_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = assets.select_photos(report())
            candidates = assets.logo_candidates(report(), {r["url"] for r in rows})

            def fetch(url, max_bytes):
                return b"<svg>marque</svg>", "image/svg+xml", url

            saved, refused = assets.download_logos(candidates, Path(tmp) / "logos", fetch=fetch)
            self.assertEqual([row["file"] for row in saved], ["logo-01.svg"])
            self.assertEqual(refused, [])
            self.assertTrue((Path(tmp) / "logos" / "logo-01.svg").is_file())

    def test_logo_deja_present_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "images"
            images.mkdir()
            (images / "photo-01.svg").write_bytes(b"<svg>marque</svg>")
            rows = assets.select_photos(report())
            candidates = assets.logo_candidates(report(), {r["url"] for r in rows})

            def fetch(url, max_bytes):
                return b"<svg>marque</svg>", "image/svg+xml", url

            saved, refused = assets.download_logos(
                candidates, Path(tmp) / "logos", photos_dir=images, fetch=fetch
            )
            self.assertEqual(saved, [])
            self.assertEqual(refused[0]["raison"], "image déjà conservée")

    def test_logo_injoignable_n_interrompt_pas(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = assets.select_photos(report())
            candidates = assets.logo_candidates(report(), {r["url"] for r in rows})

            def fetch(url, max_bytes):
                raise OSError("réseau indisponible")

            saved, refused = assets.download_logos(candidates, Path(tmp) / "logos", fetch=fetch)
            self.assertEqual(saved, [])
            self.assertIn("téléchargement impossible", refused[0]["raison"])


class OrganizeTests(unittest.TestCase):
    def test_valeur_confirmee_si_retrouvee(self):
        entry = organize.field(relevant_pages(report()), "Hôtel Test")
        self.assertEqual(entry["confiance"], "confirmee")
        self.assertEqual(entry["origine"]["page"], "https://hotel-test.fr/")

    def test_valeur_absente_de_la_source_a_confirmer(self):
        entry = organize.field(relevant_pages(report()), "Palace Imaginaire")
        self.assertEqual(entry["confiance"], "a_confirmer")
        self.assertIsNone(entry["origine"])

    def test_valeur_vide_absente(self):
        self.assertEqual(organize.field([], "")["confiance"], "absente")

    def test_infos_organisees(self):
        infos = build_infos()
        self.assertEqual(infos["etablissement"]["nom"]["valeur"], "Hôtel Test")
        self.assertEqual(infos["etablissement"]["nom"]["confiance"], "confirmee")
        self.assertEqual(infos["etablissement"]["adresse"]["confiance"], "a_confirmer")
        self.assertIn("etablissement.adresse", infos["a_confirmer"])
        # Jamais repris de la source : toujours réclamés à l'hôtelier.
        for manque in ("tarifs", "horaires", "coordonnees_gps", "conditions_de_reservation"):
            self.assertIn(manque, infos["manques"])
        self.assertIn("photos_de_chambres", infos["manques"])

    def test_site_conforme_et_media_publie(self):
        site, provenance = organize.build_site(report(), extracted(), "cli-1", photos())
        self.assertEqual(validate_site(site), site)
        self.assertEqual(site["media"][0]["id"], "aaaa")
        self.assertTrue(site["media"][0]["file"].endswith("demos/cli-1/images/photo-01.jpg"))
        self.assertIn("aaaa", provenance["media"])

    def test_collection_ecrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            infos = build_infos()
            site, _ = organize.build_site(report(), extracted(), "cli-1", photos())
            organize.write_collection(tmp, infos, {"source_url": "x"}, site, pierre.build_pierre(infos))
            for name in ("infos.json", "sources.json", "site.json", "pierre.json"):
                self.assertTrue((Path(tmp) / "hotel" / name).is_file(), name)


class PierreTests(unittest.TestCase):
    def test_roles_regles_et_champs(self):
        data = pierre.build_pierre(build_infos())
        self.assertEqual(set(data["roles"]), set(pierre.ROLES))
        for champ in (
            "hero.content.title",
            "hero.media.photo_id",
            "contact.content.email",
            "services.items",
            "rooms.items[0].title",
            "rooms.items[0].photo_id",
        ):
            self.assertIn(champ, data["champs"])

    def test_suggestion_de_texte_verbatim(self):
        data = pierre.build_pierre(build_infos())
        for proposition in data["champs"]["hero.content.intro"]:
            self.assertIn(proposition["valeur"], report()["pages"][0]["text"])

    def test_nom_du_site_repris_comme_suggestion(self):
        data = pierre.build_pierre(build_infos())
        self.assertEqual(data["champs"]["hero.content.title"][0]["valeur"], "Hôtel Test")
        self.assertEqual(data["champs"]["hero.content.title"][0]["confiance"], "confirmee")

    def test_photo_de_chambre_proposee_avec_raison(self):
        # La photo vient de la page « chambres » : elle est proposée, jamais imposée.
        data = pierre.build_pierre(build_infos())
        propositions = data["champs"]["rooms.items[0].photo_id"]
        self.assertEqual([item["valeur"] for item in propositions], ["bbbb"])
        self.assertIn("chambre", propositions[0]["raison"])

    def test_aucune_photo_proposee_sans_correspondance(self):
        self.assertEqual(pierre.room_proposals("Suite Panoramique", photos()), [])


class PublishTests(unittest.TestCase):
    def test_media_url_avec_et_sans_base(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("R2_PUBLIC_BASE", None)
            self.assertEqual(
                publish.media_url("cli", "photo-01.jpg", "images"),
                "/demos/cli/images/photo-01.jpg",
            )
        with mock.patch.dict(os.environ, {"R2_PUBLIC_BASE": "https://cdn.test/"}, clear=False):
            self.assertEqual(
                publish.media_url("cli", "photo-01.jpg", "images"),
                "https://cdn.test/demos/cli/images/photo-01.jpg",
            )

    def test_lien_de_demo_porte_l_identifiant(self):
        with mock.patch.dict(os.environ, {"DEMO_BASE": "https://demo.test/"}, clear=False):
            self.assertEqual(publish.demo_url("cli-1"), "https://demo.test/cli-1")
            self.assertEqual(
                publish.sheet_payload("cli-1"),
                {"ID": "cli-1", "lien demo": "https://demo.test/cli-1"},
            )

    def test_documents_publies_et_conserves(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "cli"
            (folder / "hotel").mkdir(parents=True)
            (folder / "hotel" / "site.json").write_text('{"a": 1}', encoding="utf-8")

            fake = FakeS3()
            compte_rendu = publish.publish_documents(folder, "cli", s3=fake, bucket="test")

            self.assertEqual(
                [item["key"] for item in fake.uploads], ["demos/cli/hotel/site.json"]
            )
            self.assertEqual(compte_rendu["sent"][0]["file"], "site.json")
            # Le document reste sur la machine : le studio le lit en local.
            self.assertTrue((folder / "hotel" / "site.json").is_file())

    def test_envoi_complet_liberent_les_medias_et_garde_les_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "cli"
            (folder / "images").mkdir(parents=True)
            (folder / "hotel").mkdir()
            (folder / "images" / "photo-01.jpg").write_bytes(b"x" * 10)
            (folder / "hotel" / "site.json").write_text("{}", encoding="utf-8")

            fake = FakeS3()
            compte_rendu = publish.publish_folder(folder, "cli", s3=fake, bucket="test")

            keys = [item["key"] for item in fake.uploads]
            self.assertEqual(
                keys, ["demos/cli/images/photo-01.jpg", "demos/cli/hotel/site.json"]
            )
            self.assertEqual(list((folder / "images").iterdir()), [])
            self.assertTrue((folder / "hotel" / "site.json").is_file())
            self.assertEqual(compte_rendu["freed_bytes"], 10)

    def test_envoi_puis_suppression_des_fichiers_lourds(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "cli"
            (folder / "images").mkdir(parents=True)
            (folder / "logos").mkdir()
            (folder / "hotel").mkdir()
            (folder / "images" / "photo-01.jpg").write_bytes(b"x" * 10)
            (folder / "logos" / "logo-01.svg").write_bytes(b"<svg/>")
            (folder / "hotel" / "infos.json").write_text("{}", encoding="utf-8")

            fake = FakeS3()
            compte_rendu = publish.publish_media(folder, "cli", s3=fake, bucket="test")

            keys = [upload["key"] for upload in fake.uploads]
            self.assertIn("demos/cli/images/photo-01.jpg", keys)
            self.assertIn("demos/cli/logos/logo-01.svg", keys)
            self.assertEqual(list((folder / "images").iterdir()), [])
            self.assertEqual(list((folder / "logos").iterdir()), [])
            # Les JSON restent : ils ne pèsent rien et le studio les lit.
            self.assertTrue((folder / "hotel" / "infos.json").is_file())
            self.assertEqual(compte_rendu["freed_bytes"], 16)

    def test_echec_d_envoi_ne_supprime_rien(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "cli"
            (folder / "images").mkdir(parents=True)
            (folder / "images" / "photo-01.jpg").write_bytes(b"x" * 10)

            class Broken(FakeS3):
                def upload_file(self, *args, **kwargs):
                    raise RuntimeError("réseau indisponible")

            with self.assertRaises(RuntimeError):
                publish.publish_media(folder, "cli", s3=Broken(), bucket="test")
            self.assertTrue((folder / "images" / "photo-01.jpg").is_file())

    def test_webhook_vide_ne_fait_rien(self):
        self.assertFalse(publish.notify("", {"id": "x"}))

    def test_webhook_rejoint(self):
        appels = []

        class Reponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def envoyer(request, timeout=None):
            appels.append(request.full_url)
            return Reponse()

        self.assertTrue(publish.notify("https://hook.test/x", {"id": "x"}, send=envoyer))
        self.assertEqual(appels, ["https://hook.test/x"])

    def test_webhook_injoignable_ne_leve_pas(self):
        def envoyer(request, timeout=None):
            raise OSError("injoignable")

        self.assertFalse(publish.notify("https://hook.test/x", {"id": "x"}, send=envoyer))


class RunOneTests(unittest.TestCase):
    def prepare(self, tmp, report_data):
        crawl = Path(tmp) / "extraction"
        (crawl / "photos").mkdir(parents=True)
        (crawl / "photos" / "aaaa.jpg").write_bytes(b"a" * 10)
        (crawl / "photos" / "bbbb.jpg").write_bytes(b"b" * 9)
        (crawl / "report.json").write_text(json.dumps(report_data), encoding="utf-8")
        return crawl

    def test_deroule_complet_jusqu_a_prete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            crawl = self.prepare(tmp, report(with_logo=False))

            async def extract(url):
                return str(crawl)

            fake = FakeS3()
            upload = partial(publish.publish_media, s3=fake, bucket="test")
            manifest = asyncio.run(
                runner.run_one(
                    root,
                    "cli-1",
                    "https://hotel-test.fr/",
                    extract=extract,
                    classify=lambda data: extracted(),
                    upload=upload,
                    notify_url="",
                )
            )

            self.assertEqual(manifest["step"], "prete")
            self.assertEqual(manifest["error"], None)
            self.assertEqual(
                [step["step"] for step in manifest["history"]],
                ["collecte", "tri", "organisation", "envoi", "prete"],
            )
            self.assertEqual(manifest["counts"]["photos"], 2)

            folder = root / "cli-1"
            # La collecte brute a disparu, les photos sont parties et ont été libérées.
            self.assertFalse((folder / "crawl").exists())
            self.assertEqual(list((folder / "images").iterdir()), [])
            # Les JSON restent, y compris le document du studio.
            for name in ("infos.json", "sources.json", "site.json", "pierre.json"):
                self.assertTrue((folder / "hotel" / name).is_file(), name)

            site = json.loads((folder / "hotel" / "site.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_site(site), site)
            self.assertTrue(site["media"][0]["file"].endswith("demos/cli-1/images/photo-01.jpg"))

            keys = [upload["key"] for upload in fake.uploads]
            self.assertIn("demos/cli-1/images/photo-01.jpg", keys)
            self.assertIn("demos/cli-1/images/photo-02.jpg", keys)

    def test_echec_marque_le_manifeste_et_conserve_le_dossier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"

            async def extract(url):
                raise RuntimeError("site injoignable")

            with self.assertRaises(RuntimeError):
                asyncio.run(runner.run_one(root, "cli-2", "https://x.fr/", extract=extract))

            manifest = workspace.load(root, "cli-2")
            self.assertEqual(manifest["step"], "echec")
            self.assertIn("site injoignable", manifest["error"])

    def test_file_refuse_le_meme_identifiant_deux_fois(self):
        started = threading.Event()
        release = threading.Event()

        async def worker(root, id, url):
            started.set()
            release.wait(timeout=5)

        file = runner.Runner(root="/tmp/data-test", worker=worker)
        self.assertTrue(file.submit("cli-3", "https://x.fr/"))
        self.assertTrue(started.wait(timeout=5))
        self.assertFalse(file.submit("cli-3", "https://x.fr/"))
        release.set()
        file.pending.join()

    def test_file_refuse_un_identifiant_invalide(self):
        file = runner.Runner(root="/tmp/data-test", worker=lambda *a: None)
        with self.assertRaises(workspace.InvalidId):
            file.submit("../evasion", "https://x.fr/")


if __name__ == "__main__":
    unittest.main()
