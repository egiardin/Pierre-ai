"""Tests du pont extraction → document du studio.

Aucun accès réseau ni modèle : le rapport d'extraction est simulé et les
informations lues sont fournies directement.
"""

import json
import tempfile
import unittest
from pathlib import Path

from ingestion import (
    build_document,
    build_media,
    relevant_pages,
    slugify,
    write_draft,
)
from studio_schema import SiteDocumentError, validate_site


def report():
    return {
        "schema_version": 1,
        "source_url": "https://hotel-test.fr/",
        "status": "complete_within_limits",
        "pages": [
            {
                "url": "https://hotel-test.fr/",
                "title": "Hôtel Test",
                "description": "Un hôtel de charme au centre-ville.",
                "text": "Accueil\nUn hôtel de charme au centre-ville.\nChambres",
            },
            {
                "url": "https://hotel-test.fr/chambres",
                "title": "Chambres",
                "description": "",
                "text": "Accueil\nChambre Classique 18 m²\nSuite Junior 32 m²",
            },
            {
                "url": "https://hotel-test.fr/mentions-legales",
                "title": "Mentions légales",
                "description": "",
                "text": "Accueil\nÉditeur du site",
            },
        ],
        "photos": [
            {
                "id": "aaaa",
                "file": "photos/aaaa.jpg",
                "preview": "previews/aaaa.jpg",
                "width": 1600,
                "height": 1200,
                "bytes": 1200,
                "sources": [
                    {
                        "page": "https://hotel-test.fr/",
                        "kind": "img",
                        "alt": "Façade de l'hôtel",
                        "url": "https://hotel-test.fr/img/facade.jpg",
                    }
                ],
            },
            {
                "id": "bbbb",
                "file": "photos/bbbb.jpg",
                "preview": "previews/bbbb.jpg",
                "width": 1200,
                "height": 1600,
                "bytes": 900,
                "sources": [
                    {
                        "page": "https://hotel-test.fr/chambres",
                        "kind": "img",
                        "alt": "",
                        "url": "https://hotel-test.fr/img/chambre.jpg",
                    }
                ],
            },
        ],
    }


def extracted():
    return {
        "name": "Hôtel Test",
        "address": "1 rue du Test, 75001 Paris",
        "email": "contact@hotel-test.fr",
        "phone": "01 02 03 04 05",
        "amenities": ["Wi-Fi gratuit", "Piscine extérieure"],
        "rooms": [{"name": "Chambre Classique", "description": "18 m²"}],
        "booking": "https://be.synxis.com/?hotel=42",
        "booking_links": [{"url": "https://be.synxis.com/?hotel=42", "libelle": "Réserver", "score": 5}],
    }


class MappingTests(unittest.TestCase):
    def test_document_conforme_au_contrat_partage(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        self.assertEqual(validate_site(document), document)
        self.assertEqual(document["status"], "draft")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(
            [section["type"] for section in document["pages"][0]["sections"]],
            ["hero", "rooms", "services", "gallery", "contact"],
        )

    def test_contenus_issus_de_la_source(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        sections = {section["id"]: section for section in document["pages"][0]["sections"]}
        self.assertEqual(sections["hero"]["content"]["title"], "Hôtel Test")
        self.assertEqual(
            sections["hero"]["content"]["intro"], "Un hôtel de charme au centre-ville."
        )
        self.assertEqual(
            [item["label"] for item in sections["services"]["items"]],
            ["Wi-Fi gratuit", "Piscine extérieure"],
        )
        self.assertEqual(sections["rooms"]["items"][0]["title"], "Chambre Classique")
        self.assertEqual(sections["contact"]["content"]["email"], "contact@hotel-test.fr")
        self.assertEqual(sections["contact"]["content"]["phone"], "01 02 03 04 05")
        self.assertEqual(
            sections["contact"]["content"]["address"], "1 rue du Test, 75001 Paris"
        )

    def test_lien_reservation_branche_sur_le_cta_et_le_contact(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        sections = {section["id"]: section for section in document["pages"][0]["sections"]}
        self.assertEqual(
            sections["hero"]["content"]["cta_url"], "https://be.synxis.com/?hotel=42"
        )
        self.assertEqual(
            sections["contact"]["content"]["booking_url"], "https://be.synxis.com/?hotel=42"
        )

    def test_rien_n_est_invente(self):
        vide = {"name": None, "address": None, "email": None, "phone": None, "amenities": [], "rooms": []}
        document, _ = build_document(report(), vide, "hotel-test")
        validate_site(document)
        sections = {section["id"]: section for section in document["pages"][0]["sections"]}
        self.assertEqual(sections["rooms"]["items"], [])
        self.assertEqual(sections["services"]["items"], [])
        self.assertEqual(sections["contact"]["content"]["email"], "")
        self.assertEqual(sections["contact"]["content"]["address"], "")
        self.assertEqual(sections["contact"]["content"]["booking_url"], "")
        self.assertEqual(sections["hero"]["content"]["title"], "Hôtel Test")
        self.assertEqual(sections["hero"]["content"]["cta_url"], "")

    def test_galerie_et_hero_utilisent_les_photos_extraites(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        sections = {section["id"]: section for section in document["pages"][0]["sections"]}
        self.assertEqual([item["photo_id"] for item in sections["gallery"]["items"]], ["aaaa", "bbbb"])
        self.assertEqual(sections["hero"]["media"]["photo_id"], "aaaa")
        self.assertEqual(document["media"][0]["source"], "extraction")
        self.assertEqual(document["media"][0]["status"], "extracted")
        self.assertEqual(document["media"][0]["alt"], "Façade de l'hôtel")

    def test_les_photos_de_chambre_ne_sont_pas_devinees(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        sections = {section["id"]: section for section in document["pages"][0]["sections"]}
        self.assertEqual(sections["rooms"]["items"][0]["photo_id"], "")

    def test_provenance_des_textes_et_des_photos(self):
        _, provenance = build_document(report(), extracted(), "hotel-test")
        self.assertEqual(provenance["source_url"], "https://hotel-test.fr/")
        self.assertEqual(
            [page["url"] for page in provenance["pages"]],
            ["https://hotel-test.fr/", "https://hotel-test.fr/chambres"],
        )
        self.assertEqual(
            provenance["media"]["aaaa"],
            {
                "original_url": "https://hotel-test.fr/img/facade.jpg",
                "page": "https://hotel-test.fr/",
                "local_file": "photos/aaaa.jpg",
            },
        )
        self.assertIn("hero.content.cta_label", provenance["defaults"])


class TextTests(unittest.TestCase):
    def test_pages_hors_sujet_ignorees(self):
        urls = [page["url"] for page in relevant_pages(report())]
        self.assertEqual(urls, ["https://hotel-test.fr/", "https://hotel-test.fr/chambres"])

    def test_slug(self):
        self.assertEqual(slugify("Hôtel des Cinq Terres"), "hotel-des-cinq-terres")
        self.assertEqual(slugify(""), "hotel")
        self.assertEqual(slugify("***"), "hotel")


class ContratTests(unittest.TestCase):
    def test_document_incomplet_refuse(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        document["status"] = "en_cours"
        with self.assertRaises(SiteDocumentError):
            validate_site(document)

    def test_media_sans_fichier_refuse(self):
        document, _ = build_document(report(), extracted(), "hotel-test")
        document["media"][0].pop("file")
        with self.assertRaises(SiteDocumentError):
            validate_site(document)


class EcritureTests(unittest.TestCase):
    def test_ecrit_le_brouillon_et_sa_provenance(self):
        document, provenance = build_document(report(), extracted(), "hotel-test")
        with tempfile.TemporaryDirectory() as dossier:
            folder = write_draft(document, provenance, dossiers_dir=dossier)
            self.assertEqual(folder.name, "hotel-test")
            written = json.loads((folder / "site.json").read_text(encoding="utf-8"))
            self.assertEqual(written, document)
            sources = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
            self.assertEqual(sources["media"]["bbbb"]["page"], "https://hotel-test.fr/chambres")

    def test_media_sans_source_ignore(self):
        rapport = report()
        rapport["photos"].append(
            {"id": "cccc", "file": "photos/cccc.jpg", "width": 800, "height": 800, "sources": []}
        )
        media, origins = build_media(rapport)
        self.assertEqual([item["id"] for item in media], ["aaaa", "bbbb"])
        self.assertNotIn("cccc", origins)


if __name__ == "__main__":
    unittest.main()
