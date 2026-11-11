import { useLayoutEffect, useRef, useState } from "react";

import type { SiteDocument } from "../document/types";
import { StudioContext, type StudioApi } from "../studio/studio-context";
import SiteRenderer from "../template/SiteRenderer";
import { TEMPLATES, applyTemplate, findTemplate, maxPages } from "./templates";

/** Largeur de référence de l'aperçu : celle d'un écran d'ordinateur. */
const PREVIEW_WIDTH = 1100;

/**
 * Aperçu inerte : c'est le rendu réel du template, sans édition ni sélection.
 * Le contexte du studio est fourni en mode aperçu pour que le template se
 * contente d'afficher, exactement comme dans la fenêtre d'aperçu du studio.
 */
const PREVIEW_API: StudioApi = {
  mode: "preview",
  selectedId: null,
  select: () => {},
  commitText: () => {},
  requestPhoto: () => {},
  lastError: null,
};

function SitePreview({ site }: { site: SiteDocument }) {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);

  useLayoutEffect(() => {
    const element = box.current;
    if (!element) {
      return;
    }
    const update = () => setScale(element.clientWidth / PREVIEW_WIDTH);
    update();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", update);
      return () => window.removeEventListener("resize", update);
    }
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="demo-preview" ref={box} aria-hidden="true">
      <StudioContext.Provider value={PREVIEW_API}>
        <div className="demo-preview-page" style={{ transform: `scale(${scale})` }}>
          <SiteRenderer site={site} />
        </div>
      </StudioContext.Provider>
    </div>
  );
}

/** Chevron d'une flèche de défilement. */
function Chevron({ direction }: { direction: "left" | "right" }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d={direction === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"}
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface TemplatePageProps {
  site: SiteDocument;
  onBack(): void;
  onNext(site: SiteDocument): void;
}

export default function TemplatePage({ site, onBack, onNext }: TemplatePageProps) {
  const [templateId, setTemplateId] = useState(TEMPLATES[0].id);
  const track = useRef<HTMLDivElement>(null);

  const template = findTemplate(templateId);

  /** Fait défiler la liste d'une carte, dans un sens ou dans l'autre. */
  const defiler = (direction: 1 | -1) => {
    const element = track.current;
    if (!element) {
      return;
    }
    const carte = element.firstElementChild as HTMLElement | null;
    const pas = carte ? carte.offsetWidth + 20 : element.clientWidth;
    element.scrollBy({ left: direction * pas, behavior: "smooth" });
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

      <main className="demo-main demo-main-wide">
        <div className="demo-heading">
          <h1>Choisissez votre template</h1>
          <p className="demo-lead">
            Vos photos et votre contenu sont déjà en place. Le template décide de leur
            disposition : cliquez sur celui qui vous plaît.
          </p>
        </div>

        <div className="demo-carousel">
          <button
            type="button"
            className="demo-arrow demo-arrow-prev"
            aria-label="Template précédent"
            onClick={() => defiler(-1)}
          >
            <Chevron direction="left" />
          </button>

          <div className="demo-templates" ref={track}>
            {TEMPLATES.map((item) => {
              const active = item.id === templateId;
              return (
                <article
                  key={item.id}
                  className={`demo-template ${active ? "active" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={active}
                  onClick={() => setTemplateId(item.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setTemplateId(item.id);
                    }
                  }}
                >
                  <SitePreview site={applyTemplate(site, item.id, maxPages(item))} />
                  <div className="demo-template-body">
                    <strong>{item.name}</strong>
                    <p>{item.description}</p>
                  </div>
                </article>
              );
            })}
          </div>

          <button
            type="button"
            className="demo-arrow demo-arrow-next"
            aria-label="Template suivant"
            onClick={() => defiler(1)}
          >
            <Chevron direction="right" />
          </button>
        </div>
      </main>

      <footer className="demo-foot">
        <button type="button" className="btn btn-primary" onClick={onBack}>
          Retour
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => onNext(applyTemplate(site, templateId, maxPages(template)))}
        >
          Suivant
        </button>
      </footer>
    </div>
  );
}
