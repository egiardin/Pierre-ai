import type { SiteDocument } from "../document/types";
import type { Dossier } from "./dossier";

interface WelcomePageProps {
  dossier: Dossier;
  onStart(): void;
}

/** Les étapes du parcours, dans l'ordre où elles seront traversées. */
const ETAPES = [
  "Vérifier les informations",
  "Choisir un style et le nombre de pages",
  "Construire votre site",
  "Paiement",
  "Mise en ligne",
  "Accès à votre Dashboard",
];

/** Nom de l'établissement, repris du titre d'accueil relevé sur le site. */
function hotelName(site: SiteDocument): string {
  for (const page of site.pages) {
    for (const section of page.sections) {
      if (section.type === "hero" && section.content.title.trim()) {
        return section.content.title.trim();
      }
    }
  }
  return "votre établissement";
}

export default function WelcomePage({ dossier, onStart }: WelcomePageProps) {
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

          <h1>Bienvenue dans votre studio</h1>
          <p className="demo-lead">
            J'ai relevé le contenu de <strong>{hotelName(dossier.site)}</strong> et
            préparé vos photos. Voici les étapes qui vous attendent.
          </p>

          <ol className="demo-steps">
            {ETAPES.map((etape) => (
              <li key={etape} className="demo-step">
                <span className="demo-step-mark" aria-hidden="true">
                  ✓
                </span>
                <span className="demo-step-label">{etape}</span>
              </li>
            ))}
          </ol>

          <button
            type="button"
            className="btn btn-primary demo-start"
            onClick={onStart}
          >
            Commencer
          </button>
        </section>
      </main>
    </div>
  );
}
