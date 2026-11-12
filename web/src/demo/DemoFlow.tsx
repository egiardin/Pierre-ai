import { useEffect, useMemo, useState } from "react";

import type { SiteDocument } from "../document/types";
import StudioShell from "../studio/StudioShell";
import { dossierIdFromLocation, loadDossier, type Dossier } from "./dossier";
import PaymentPage from "./PaymentPage";
import TemplatePage from "./TemplatePage";
import WelcomePage from "./WelcomePage";

/**
 * Parcours de démonstration : bienvenue, choix du template, studio, paiement.
 *
 * Le lien reçu porte l'identifiant du dossier publié ; tout le reste en découle.
 * Le studio ne se monte qu'une fois le template appliqué, et le document obtenu
 * est son point de départ. Après le studio, « Suivant » mène au paiement ;
 * au retour de Stripe (?paid=1), un dossier payé ouvre directement la confirmation.
 */
type Etape = "bienvenue" | "templates" | "studio" | "paiement" | "termine";

export default function DemoFlow() {
  const id = useMemo(() => dossierIdFromLocation(), []);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [etape, setEtape] = useState<Etape>("bienvenue");
  const [site, setSite] = useState<SiteDocument | null>(null);

  useEffect(() => {
    let actif = true;
    loadDossier(id).then((value) => {
      if (actif) {
        setDossier(value);
        // Retour de Stripe : ?paid=1 → si le dossier est marqué payé, on montre la confirmation.
        const params = new URLSearchParams(window.location.search);
        if (params.get("paid") === "1" && value.site.status === "paye") {
          setEtape("paiement");
        }
      }
    });
    return () => {
      actif = false;
    };
  }, [id]);

  if (!dossier) {
    return <p className="demo-loading">Chargement de votre dossier…</p>;
  }

  if (etape === "studio" && site) {
    return (
      <StudioShell
        initialSite={site}
        onBack={() => setEtape("templates")}
        onNext={() => setEtape("paiement")}
      />
    );
  }

  if (etape === "paiement") {
    return (
      <PaymentPage
        dossier={dossier}
        onBack={() => setEtape("studio")}
        onDone={() => setEtape("termine")}
      />
    );
  }

  if (etape === "termine") {
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
          <section className="demo-welcome">
            <span className="mascot demo-mascot" aria-hidden="true">
              <i />
              <i />
            </span>
            <h1>Merci !</h1>
            <p className="demo-lead">
              Votre site est payé. La mise en ligne sur votre domaine arrive à l'étape
              suivante — vous recevrez le lien final par e-mail.
            </p>
            <button
              type="button"
              className="btn btn-primary demo-start"
              onClick={() => setEtape("studio")}
            >
              Retourner dans le studio
            </button>
          </section>
        </main>
      </div>
    );
  }

  if (etape === "templates") {
    return (
      <TemplatePage
        site={dossier.site}
        onBack={() => setEtape("bienvenue")}
        onNext={(construit) => {
          setSite(construit);
          setEtape("studio");
        }}
      />
    );
  }

  return <WelcomePage dossier={dossier} onStart={() => setEtape("templates")} />;
}
