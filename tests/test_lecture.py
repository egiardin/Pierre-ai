"""Tests de la lecture locale du site (pipeline.lecture).

Aucun réseau, aucun modèle, aucune clé : le rapport d'extraction est simulé et la
lecture doit retrouver six informations, toutes présentes mot pour mot dans le
texte des pages — rien n'est deviné.
"""

import unittest

from pipeline.lecture import read_hotel


def report():
    """Site simulé : une marque répétée, des coordonnées, deux chambres."""
    return {
        "schema_version": 1,
        "source_url": "https://cinq-terres.fr/",
        "status": "complete_within_limits",
        "pages": [
            {
                "url": "https://cinq-terres.fr/",
                "title": "Hôtel des Cinq Terres | Accueil",
                "description": "Un hôtel de charme.",
                "text": (
                    "Hôtel des Cinq Terres\n"
                    "Accueil\nLa Winstub\nChambres\nContact\n"
                    "12 rue des Tilleuls\n14400 Bayeux\n"
                    "contact@cinq-terres.fr\n02 31 22 33 44\n"
                    "Wi-Fi gratuit\nPiscine\n"
                    "Chambre Classique 18 m²\nSuite Junior 32 m²\n"
                ),
            },
            {
                "url": "https://cinq-terres.fr/chambres",
                "title": "Chambres",
                "description": "",
                "text": (
                    "Hôtel des Cinq Terres\nAccueil\nLa Winstub\nChambres\nContact\n"
                    "12 rue des Tilleuls\n14400 Bayeux\n"
                    "Chambre Classique 18 m²\nSuite Junior 32 m²\nLa suite et les chambres\n"
                ),
            },
            {
                "url": "https://cinq-terres.fr/contact",
                "title": "Contact",
                "description": "",
                "text": (
                    "Hôtel des Cinq Terres\nAccueil\nLa Winstub\nChambres\nContact\n"
                    "12 rue des Tilleuls\n14400 Bayeux\n"
                    "contact@cinq-terres.fr\n02 31 22 33 44\n06 12 34 56 78\n"
                ),
            },
        ],
        "photos": [],
    }


class LectureTests(unittest.TestCase):
    def test_nom_repris_de_la_marque(self):
        self.assertEqual(read_hotel(report())["name"], "Hôtel des Cinq Terres")

    def test_email_du_domaine_du_site(self):
        self.assertEqual(read_hotel(report())["email"], "contact@cinq-terres.fr")

    def test_telephone_fixe_prefere_au_mobile(self):
        self.assertEqual(read_hotel(report())["phone"], "02 31 22 33 44")

    def test_telephone_international_normalise(self):
        rapport = {
            "source_url": "https://cinq-terres.fr/",
            "pages": [
                {"url": "https://cinq-terres.fr/", "title": "", "text": "+33388082844"}
            ],
            "photos": [],
        }
        self.assertEqual(read_hotel(rapport)["phone"], "03 88 08 28 44")

    def test_adresse_presente_dans_le_texte(self):
        adresse = read_hotel(report())["address"]
        self.assertIn("14400", adresse)

    def test_equipements_et_chambres(self):
        info = read_hotel(report())
        self.assertEqual(set(info["amenities"]), {"Piscine", "Wi-Fi gratuit"})
        self.assertEqual(
            info["rooms"],
            [
                {"name": "Chambre Classique", "description": "18 m²"},
                {"name": "Suite Junior", "description": "32 m²"},
            ],
        )

    def test_lien_reservation_repris_des_ancres(self):
        rapport = {
            "source_url": "https://cinq-terres.fr/",
            "pages": [
                {
                    "url": "https://cinq-terres.fr/",
                    "title": "",
                    "text": "Accueil\nRéserver\nContact\n",
                    "anchors": [
                        {"t": "Réserver", "h": "https://be.synxis.com/?hotel=1234"},
                        {"t": "Nos chambres", "h": "https://cinq-terres.fr/chambres"},
                        {"t": "Accueil", "h": "https://cinq-terres.fr/"},
                    ],
                }
            ],
            "photos": [],
        }
        info = read_hotel(rapport)
        self.assertEqual(info["booking"], "https://be.synxis.com/?hotel=1234")
        self.assertEqual(len(info["booking_links"]), 1)

    def test_lien_reservation_interne_reconnu(self):
        rapport = {
            "source_url": "https://cinq-terres.fr/",
            "pages": [
                {
                    "url": "https://cinq-terres.fr/",
                    "title": "",
                    "text": "",
                    "anchors": [
                        {"t": "Réserver en ligne", "h": "https://cinq-terres.fr/reservation"}
                    ],
                }
            ],
            "photos": [],
        }
        self.assertEqual(read_hotel(rapport)["booking"], "https://cinq-terres.fr/reservation")

    def test_rien_n_est_invente_sans_source(self):
        vide = {"source_url": "", "pages": [], "photos": []}
        info = read_hotel(vide)
        self.assertEqual(
            info,
            {
                "name": "",
                "address": "",
                "email": "",
                "phone": "",
                "amenities": [],
                "rooms": [],
                "booking": "",
                "booking_links": [],
            },
        )


if __name__ == "__main__":
    unittest.main()
