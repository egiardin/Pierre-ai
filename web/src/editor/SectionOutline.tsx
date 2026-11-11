import type { SectionType, SiteDocument, SitePage } from "../document/types";
import { useStudio } from "../studio/studio-context";

const LABELS: Record<SectionType, string> = {
  hero: "Accueil",
  rooms: "Chambres",
  services: "Services",
  gallery: "Galerie",
  contact: "Contact",
};

/** Nom affiché d'une page : l'accueil, puis les pages suivantes numérotées. */
function pageLabel(page: SitePage, index: number): string {
  return page.id === "home" ? "Accueil" : `Page ${index + 1}`;
}

/** Navigation par section, page par page. Sélectionner une section la met en évidence. */
export default function SectionOutline({ site }: { site: SiteDocument }) {
  const { selectedId, select } = useStudio();

  const aller = (sectionId: string) => {
    select(sectionId);
    const target = document.getElementById(`site-section-${sectionId}`);
    // En édition, le canevas défile ; en aperçu, c'est le viewport de
    // l'appareil. On ne fait défiler qu'un seul conteneur pour rester à un
    // unique défilement.
    const viewport =
      document.querySelector<HTMLElement>(".device-viewport") ??
      document.querySelector<HTMLElement>(".canvas");
    if (target && viewport) {
      const top =
        viewport.scrollTop +
        target.getBoundingClientRect().top -
        viewport.getBoundingClientRect().top;
      viewport.scrollTo({ top, behavior: "smooth" });
    }
  };

  return (
    <nav className="outline">
      <h2>Sections</h2>
      {site.pages.map((page, index) => (
        <div className="outline-page" key={page.id}>
          <h3>{pageLabel(page, index)}</h3>
          <ul>
            {page.sections.map((section) => (
              <li key={section.id}>
                <button
                  type="button"
                  className={section.id === selectedId ? "active" : ""}
                  onClick={() => aller(section.id)}
                >
                  <span>{LABELS[section.type]}</span>
                  <span className="outline-id">{section.id}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
