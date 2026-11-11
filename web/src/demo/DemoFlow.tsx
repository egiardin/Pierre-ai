import { useEffect, useMemo, useState } from "react";

import type { SiteDocument } from "../document/types";
import StudioShell from "../studio/StudioShell";
import { dossierIdFromLocation, loadDossier, type Dossier } from "./dossier";
import TemplatePage from "./TemplatePage";
import WelcomePage from "./WelcomePage";

/**
 * Parcours de démonstration : bienvenue, choix du template, puis studio.
 *
 * Le lien reçu porte l'identifiant du dossier publié ; tout le reste en découle.
 * Le studio ne se monte qu'une fois le template appliqué, et le document obtenu
 * est son point de départ.
 */
type Etape = "bienvenue" | "templates" | "studio";

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
        onNext={() => {}}
      />
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
