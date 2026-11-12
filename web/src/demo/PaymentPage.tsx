import { useState } from "react";

import type { Dossier } from "./dossier";

/** Adresse du backend (création de la session Stripe), renseignée au déploiement. */
const BACKEND = (import.meta.env.VITE_BACKEND_URL ?? "").replace(/\/+$/, "");

/** Tarif par page en centimes, même valeur que PRIX_BASE_CENTS côté backend. */
const BASE_CENTS = Number(import.meta.env.VITE_PRIX_BASE_CENTS ?? 4900);

function eur(cents: number): string {
  return (cents / 100).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
}

interface PaymentPageProps {
  dossier: Dossier;
  onBack(): void;
  onDone(): void;
}

/**
 * Étape paiement du parcours : choix du nombre de pages, code de réduction
 * facultatif, puis redirection vers le Checkout Stripe hébergé.
 * Si le document porte déjà le statut « paye », la page affiche la confirmation.
 */
export default function PaymentPage({ dossier, onBack, onDone }: PaymentPageProps) {
  const [pages, setPages] = useState(Math.max(1, dossier.site.pages.length));
  const [promo, setPromo] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState("");
  const paye = dossier.site.status === "paye";

  const payer = async () => {
    setEnvoi(true);
    setErreur("");
    try {
      const reponse = await fetch(`${BACKEND}/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: dossier.id, pages, promo }),
      });
      const data = await reponse.json();
      if (!reponse.ok) {
        setErreur(typeof data.detail === "string" ? data.detail : "Paiement indisponible.");
        setEnvoi(false);
        return;
      }
      window.location.href = data.url;
    } catch {
      setErreur("Backend injoignable.");
      setEnvoi(false);
    }
  };

  return (
    <div className="demo-shell">
      <header className="demo-top">
        <div className="brand">
          <span className="mascot brand-mascot" aria-hidden="true">
            <i />
            <i />
          </span>
          <span className="brand-logo">
            pierre<span className="brand-dot">.</span>
          </span>
          <span className="brand-tag">Studio</span>
        </div>
      </header>

      <main className="demo-main">
        <section className="demo-welcome demo-pay">
          <span className="mascot demo-mascot" aria-hidden="true">
            <i />
            <i />
          </span>

          {paye ? (
            <>
              <h1>Paiement confirmé</h1>
              <p className="demo-lead">
                Merci ! Votre site est réglé. Il ne reste plus qu'à le mettre en ligne.
              </p>
              <button type="button" className="btn btn-primary demo-start" onClick={onDone}>
                Continuer
              </button>
            </>
          ) : (
            <>
              <h1>Dernière étape avant la mise en ligne</h1>
              <p className="demo-lead">
                Réglez votre site pour le publier sur le domaine de votre établissement.
              </p>

              <div className="pay-box">
                <label className="pay-field">
                  <span>Nombre de pages</span>
                  <select
                    value={pages}
                    onChange={(event) => setPages(Number(event.target.value))}
                  >
                    {[1, 2, 3].map((n) => (
                      <option key={n} value={n}>
                        {n} page{n > 1 ? "s" : ""}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="pay-field">
                  <span>Code de réduction (facultatif)</span>
                  <input
                    value={promo}
                    onChange={(event) => setPromo(event.target.value)}
                    placeholder="PIERRE10"
                  />
                </label>

                <p className="pay-total">
                  Total : <strong>{eur(BASE_CENTS * pages)}</strong>
                </p>

                {erreur && <p className="pay-error">{erreur}</p>}
                {!BACKEND && (
                  <p className="pay-error">Backend non configuré (VITE_BACKEND_URL).</p>
                )}

                <div className="pay-actions">
                  <button type="button" className="btn" onClick={onBack}>
                    Retour
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={envoi || !BACKEND}
                    onClick={payer}
                  >
                    {envoi ? "Redirection…" : `Payer ${eur(BASE_CENTS * pages)}`}
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
