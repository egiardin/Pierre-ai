import type { Section, SectionType, SiteDocument, SitePage } from "../document/types";

/**
 * Un template décide de la disposition, pas du contenu.
 *
 * Le contenu et les photos viennent du dossier du client : le template ne fait
 * que les ranger. Chaque template indique donc les sections de la page d'accueil,
 * puis l'ordre des sections suivantes.
 */
export interface Template {
  id: string;
  name: string;
  description: string;
  /** Sections de la page d'accueil, dans l'ordre d'apparition. */
  home: SectionType[];
  /** Sections suivantes, dans l'ordre d'apparition. */
  rest: SectionType[];
}

export const TEMPLATES: Template[] = [
  {
    id: "essentiel",
    name: "Essentiel",
    description:
      "L'accueil présente l'établissement et sa galerie. Les chambres, les services et le contact suivent.",
    home: ["hero", "gallery"],
    rest: ["rooms", "services", "contact"],
  },
  {
    id: "chambres",
    name: "Chambres d'abord",
    description:
      "Les chambres arrivent juste après la présentation, puis la galerie, les services et le contact.",
    home: ["hero", "rooms"],
    rest: ["gallery", "services", "contact"],
  },
  {
    id: "accueil-long",
    name: "Accueil long",
    description:
      "Une grande page d'accueil qui réunit la présentation, la galerie et les chambres. Services et contact suivent.",
    home: ["hero", "gallery", "rooms"],
    rest: ["services", "contact"],
  },
];

export function findTemplate(id: string): Template {
  return TEMPLATES.find((template) => template.id === id) ?? TEMPLATES[0];
}

/** Nombre de pages qu'un template accepte, page d'accueil comprise. */
export function maxPages(template: Template): number {
  return 1 + template.rest.length;
}

/** Choix de pages proposés à l'utilisateur, de 1 au maximum du template. */
export function pageCounts(template: Template): number[] {
  return Array.from({ length: maxPages(template) }, (_value, index) => index + 1);
}

/** Sections conservées et rangées selon l'ordre demandé. Rien n'est inventé. */
function pick(sections: Section[], types: SectionType[]): Section[] {
  return types.flatMap((type) => sections.filter((section) => section.type === type));
}

/** Répartit une liste en parts aussi égales que possible, sans rien perdre. */
function split(items: Section[], parts: number): Section[][] {
  if (parts <= 0) {
    return [items];
  }
  const size = Math.floor(items.length / parts);
  const extra = items.length % parts;
  const groups: Section[][] = [];
  let start = 0;
  for (let index = 0; index < parts; index += 1) {
    const length = size + (index < extra ? 1 : 0);
    groups.push(items.slice(start, start + length));
    start += length;
  }
  return groups;
}

/**
 * Range les sections du dossier selon le template et le nombre de pages voulu.
 * Une seule page accepte tout ; au-delà, l'accueil garde ses sections et le
 * reste est réparti. Aucune section n'est perdue.
 */
export function applyTemplate(
  site: SiteDocument,
  templateId: string,
  pageCount: number
): SiteDocument {
  const template = findTemplate(templateId);
  const sections = site.pages.flatMap((page) => page.sections);
  const wanted = Math.min(Math.max(Math.trunc(pageCount), 1), maxPages(template));

  if (wanted === 1) {
    return {
      ...site,
      pages: [{ id: "home", sections: [...pick(sections, template.home), ...pick(sections, template.rest)] }],
    };
  }

  const pages: SitePage[] = [
    { id: "home", sections: pick(sections, template.home) },
  ];
  split(pick(sections, template.rest), wanted - 1).forEach((group, index) => {
    pages.push({ id: `page-${index + 2}`, sections: group });
  });

  return { ...site, pages };
}
