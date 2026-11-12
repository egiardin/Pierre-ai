"""Tests du paiement Stripe (payments.py).

Aucun réseau, aucune vraie clé : le module stripe est remplacé par un faux, et
le compartiment R2 par un faux client en mémoire.
"""

import json
import unittest

from payments import (
    PaymentError,
    PromoInvalide,
    creer_session,
    marquer_paye,
    prix_cents,
    traiter_webhook,
)


class FauxS3:
    """Compartiment en mémoire : un seul objet, site.json."""

    def __init__(self, site=None, present=True):
        self.site = site or {
            "schema_version": 1,
            "slug": "demo-test",
            "version": 1,
            "status": "draft",
            "pages": [{"id": "home", "sections": []}],
            "media": [],
        }
        self.present = present
        self.ecrits = {}

    def head_object(self, Bucket, Key):
        if not self.present:
            raise Exception("NoSuchKey")
        return {}

    def get_object(self, Bucket, Key):
        class Body:
            def read(inner):
                return json.dumps(self.site).encode("utf-8")

        return {"Body": Body()}

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        self.ecrits[Key] = Body.decode("utf-8")


class FauxStripe:
    """Module stripe factice : capture la session créée, simule le webhook."""

    derniere_session = None

    class PromotionCode:
        @staticmethod
        def list(code, active, limit):
            class R:
                data = (
                    [type("PC", (), {"id": "promo_123"})()]
                    if code == "PIERRE10"
                    else []
                )

            return R()

    class checkout:
        class Session:
            @staticmethod
            def create(**options):
                FauxStripe.derniere_session = options

                class S:
                    url = "https://checkout.stripe.com/c/pay/cs_test"
                    id = "cs_test"

                return S()

    class Webhook:
        @staticmethod
        def construct_event(payload, signature, secret):
            return json.loads(payload)


ENV = {
    "STRIPE_SECRET_KEY": "sk_test_faux",
    "STRIPE_WEBHOOK_SECRET": "whsec_faux",
    "R2_BUCKET_NAME": "pierre-demo",
    "R2_ACCOUNT_ID": "x",
    "R2_ACCESS_KEY_ID": "x",
    "R2_SECRET_ACCESS_KEY": "x",
}


class PrixTests(unittest.TestCase):
    def test_tarif_par_page(self):
        self.assertEqual(prix_cents(1, {}), 4900)
        self.assertEqual(prix_cents(3, {}), 14700)

    def test_prix_plafonne_et_plancher(self):
        self.assertEqual(prix_cents(99, {}), 4900 * 5)
        self.assertEqual(prix_cents(0, {}), 4900)

    def test_tarif_surcharge_par_env(self):
        self.assertEqual(prix_cents(2, {"PRIX_BASE_CENTS": "1000"}), 2000)


class SessionTests(unittest.TestCase):
    def test_sans_cle_paiement_non_configure(self):
        with self.assertRaises(PaymentError):
            creer_session("demo-test", 1, "", environ={}, stripe_mod=FauxStripe, s3=FauxS3())

    def test_dossier_inconnu_refuse(self):
        with self.assertRaises(PaymentError):
            creer_session(
                "inconnu", 1, "", environ=ENV, stripe_mod=FauxStripe, s3=FauxS3(present=False)
            )

    def test_session_montant_et_metadata(self):
        resultat = creer_session(
            "demo-test", 2, "", environ=ENV, stripe_mod=FauxStripe, s3=FauxS3()
        )
        options = FauxStripe.derniere_session
        self.assertEqual(resultat["montant_cents"], 9800)
        self.assertEqual(options["line_items"][0]["price_data"]["unit_amount"], 9800)
        self.assertEqual(options["metadata"], {"id": "demo-test", "pages": "2", "promo": ""})
        self.assertNotIn("discounts", options)
        self.assertTrue(options["success_url"].startswith("https://"))
        self.assertIn("demo-test?paid=1", options["success_url"])

    def test_promo_invalide_refusee(self):
        with self.assertRaises(PromoInvalide):
            creer_session(
                "demo-test", 1, "INCONNU", environ=ENV, stripe_mod=FauxStripe, s3=FauxS3()
            )

    def test_promo_valide_appliquee(self):
        creer_session("demo-test", 1, "PIERRE10", environ=ENV, stripe_mod=FauxStripe, s3=FauxS3())
        self.assertEqual(FauxStripe.derniere_session["discounts"], [{"promotion_code": "promo_123"}])
        self.assertEqual(FauxStripe.derniere_session["metadata"]["promo"], "PIERRE10")


class WebhookTests(unittest.TestCase):
    def test_checkout_complete_marque_le_dossier_paye(self):
        s3 = FauxS3()
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test",
                    "payment_status": "paid",
                    "amount_total": 4900,
                    "currency": "eur",
                    "metadata": {"id": "demo-test", "promo": "PIERRE10"},
                }
            },
        }
        id = traiter_webhook(
            json.dumps(event).encode(), "sig", environ=ENV, stripe_mod=FauxStripe, s3=s3
        )
        self.assertEqual(id, "demo-test")
        ecrit = json.loads(list(s3.ecrits.values())[0])
        self.assertEqual(ecrit["status"], "paye")
        self.assertEqual(ecrit["paiement"]["session"], "cs_test")
        self.assertEqual(ecrit["paiement"]["promo"], "PIERRE10")

    def test_evenement_non_paiement_ignore(self):
        s3 = FauxS3()
        event = {"type": "payment_intent.created", "data": {"object": {}}}
        self.assertIsNone(
            traiter_webhook(json.dumps(event).encode(), "sig", environ=ENV, stripe_mod=FauxStripe, s3=s3)
        )
        self.assertEqual(s3.ecrits, {})

    def test_session_non_payee_ignoree(self):
        s3 = FauxS3()
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_x", "payment_status": "unpaid", "metadata": {"id": "demo-test"}}},
        }
        self.assertIsNone(
            traiter_webhook(json.dumps(event).encode(), "sig", environ=ENV, stripe_mod=FauxStripe, s3=s3)
        )


if __name__ == "__main__":
    unittest.main()
