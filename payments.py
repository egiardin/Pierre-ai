"""Paiement Stripe du parcours de démonstration.

Une session Checkout est créée côté serveur : la clé secrète ne sort jamais du
backend. Le webhook signé confirme le paiement et passe le document du dossier
à « paye » sur R2 (et en local quand il y est). Les codes de réduction sont des
promotion codes Stripe, résolus côté serveur avant la création de la session,
pour que le montant soit juste dès le départ.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pipeline import publish
from studio_schema import validate_site


class PaymentError(RuntimeError):
    """Paiement impossible : configuration absente ou dossier inconnu."""


class PromoInvalide(PaymentError):
    """Code de réduction inconnu ou inactif."""


# Tarif par page, en centimes (49,00 € par défaut) ; surchargeable par PRIX_BASE_CENTS.
PRIX_BASE_DEFAUT = 4900
MAX_PAGES = 5


def prix_cents(pages, environ=None):
    """Prix total en centimes : tarif de base × nombre de pages (1 à 5)."""
    environ = environ or os.environ
    base = int(environ.get("PRIX_BASE_CENTS") or PRIX_BASE_DEFAUT)
    count = max(1, min(MAX_PAGES, int(pages or 1)))
    return base * count


def stripe_module(environ=None):
    """Module stripe chargé au dernier moment ; la clé secrète reste côté serveur."""
    environ = environ or os.environ
    key = environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        raise PaymentError("STRIPE_SECRET_KEY absente : paiement non configuré.")
    try:
        import stripe
    except ImportError as error:
        raise PaymentError("Le paquet stripe est requis (pip install stripe).") from error
    stripe.api_key = key
    return stripe


def dossier_existe(id, s3=None, environ=None):
    """Le dossier visé existe : son document est présent sur R2, ou en local."""
    environ = environ or os.environ
    bucket = environ.get("R2_BUCKET_NAME", "")
    if bucket:
        try:
            publish.client(environ=environ, s3=s3).head_object(
                Bucket=bucket,
                Key=publish.object_key(id, "site.json", publish.DOCUMENTS_FOLDER),
            )
            return True
        except Exception:
            pass
    return (Path("data") / id / "hotel" / "site.json").is_file()


def resoudre_promo(code, stripe_mod):
    """Le promotion code Stripe actif correspondant, ou None si inconnu."""
    code = (code or "").strip()
    if not code:
        return None
    found = stripe_mod.PromotionCode.list(code=code, active=True, limit=1)
    return found.data[0] if found.data else None


def creer_session(id, pages, promo, environ=None, stripe_mod=None, s3=None):
    """Crée une session Checkout pour un dossier et renvoie son URL de paiement."""
    environ = environ or os.environ
    if not dossier_existe(id, s3=s3, environ=environ):
        raise PaymentError("Dossier inconnu : " + str(id))
    stripe_mod = stripe_mod or stripe_module(environ)
    count = max(1, min(MAX_PAGES, int(pages or 1)))
    montant = prix_cents(count, environ)
    options = {
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": montant,
                    "product_data": {
                        "name": f"Site Pierre — dossier {id} ({count} page{'s' if count > 1 else ''})"
                    },
                },
                "quantity": 1,
            }
        ],
        "allow_promotion_codes": True,
        "success_url": f"{publish.demo_base()}/{id}?paid=1&session={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{publish.demo_base()}/{id}?paid=0",
        "metadata": {"id": id, "pages": str(count), "promo": (promo or "").strip()},
    }
    code = (promo or "").strip()
    if code:
        promotion = resoudre_promo(code, stripe_mod)
        if promotion is None:
            raise PromoInvalide(f"Code de réduction inconnu ou inactif : {code}")
        options["discounts"] = [{"promotion_code": promotion.id}]
    session = stripe_mod.checkout.Session.create(**options)
    return {"url": session.url, "session": session.id, "montant_cents": montant}


def marquer_paye(id, session, s3=None, environ=None):
    """Passe le document du dossier à « paye » sur R2, et en local s'il y est."""
    environ = environ or os.environ
    bucket = environ.get("R2_BUCKET_NAME", "")
    if not bucket:
        raise PaymentError("R2_BUCKET_NAME absente : impossible de marquer le paiement.")
    key = publish.object_key(id, "site.json", publish.DOCUMENTS_FOLDER)
    s3 = publish.client(environ=environ, s3=s3)
    document = json.loads(
        s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    )
    document["status"] = "paye"
    document["paiement"] = {
        "session": session.get("id"),
        "montant_cents": session.get("amount_total"),
        "devise": session.get("currency"),
        "promo": (session.get("metadata") or {}).get("promo") or "",
        "paye_le": datetime.now(timezone.utc).isoformat(),
    }
    validate_site(document)
    corps = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=corps,
        ContentType="application/json; charset=utf-8",
        CacheControl="no-cache",
    )
    local = Path("data") / id / "hotel" / "site.json"
    if local.is_file():
        local.write_text(corps.decode("utf-8"), encoding="utf-8")
    return document


def traiter_webhook(payload, signature, environ=None, stripe_mod=None, s3=None):
    """Vérifie la signature Stripe, applique l'événement ; renvoie l'id payé ou None."""
    environ = environ or os.environ
    secret = environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise PaymentError("STRIPE_WEBHOOK_SECRET absente.")
    stripe_mod = stripe_mod or stripe_module(environ)
    event = stripe_mod.Webhook.construct_event(payload, signature, secret)
    if event["type"] != "checkout.session.completed":
        return None
    session = event["data"]["object"]
    id = (session.get("metadata") or {}).get("id", "")
    if not id or session.get("payment_status") != "paid":
        return None
    marquer_paye(id, session, s3=s3, environ=environ)
    return id
