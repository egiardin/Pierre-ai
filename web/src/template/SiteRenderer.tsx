import { useStudio } from "../studio/studio-context";
import type { Section, SiteDocument, SitePage } from "../document/types";
import Hero from "./sections/Hero";
import Rooms from "./sections/Rooms";
import Services from "./sections/Services";
import Gallery from "./sections/Gallery";
import Contact from "./sections/Contact";

/**
 * Rendu d'une section selon son type.
 * Le `switch` sur `type` force à traiter chaque variante : ajouter un type de
 * section produira une erreur de compilation tant qu'il n'est pas rendu.
 */
function renderSection(section: Section, site: SiteDocument) {
  switch (section.type) {
    case "hero":
      return <Hero section={section} media={site.media} />;
    case "rooms":
      return <Rooms section={section} media={site.media} />;
    case "services":
      return <Services section={section} media={site.media} />;
    case "gallery":
      return <Gallery section={section} media={site.media} />;
    case "contact":
      return <Contact section={section} media={site.media} />;
  }
}

function PageView({ page, site }: { page: SitePage; site: SiteDocument }) {
  const { selectedId, select } = useStudio();

  return (
    <>
      {page.sections.map((section) => (
        <div
          key={section.id}
          id={`site-section-${section.id}`}
          data-section-id={section.id}
          className={`site-section ${section.id === selectedId ? "selected" : ""}`}
          onClick={() => select(section.id)}
        >
          {renderSection(section, site)}
        </div>
      ))}
    </>
  );
}

/**
 * Rendu du site. Le template ne modifie jamais le document : les composants de
 * section utilisent les outils d'édition, qui passent par le studio.
 */
export default function SiteRenderer({ site }: { site: SiteDocument }) {
  return (
    <div className="site">
      {site.pages.map((page) => (
        <PageView key={page.id} page={page} site={site} />
      ))}
    </div>
  );
}
