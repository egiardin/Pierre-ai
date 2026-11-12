import demoRaw from "../data/site.demo.json";
import type { SiteDocument } from "../document/types";
import { validateSite } from "../document/validate";

/**
 * Chargement du dossier du client à partir du lien de démonstration.
 *
 * Le lien ne porte qu'un identifiant : c'est lui qui désigne le dossier du
 * compartiment R2, où sont rangées les photos publiées et le document du studio.
 * Tant que le compartiment n'est pas configuré, la page affiche la démonstration
 * locale : mieux vaut un aperçu qu'une page blanche.
 */

/** Adresse publique du compartiment, renseignée au déploiement. */
const STORAGE_BASE = (import.meta.env.VITE_R2_PUBLIC_BASE ?? "").replace(/\/+$/, "");

/** Préfixe des dossiers dans le compartiment, aligné sur le pipeline. */
const PREFIX = "demos";

export interface Dossier {
  id: string;
  site: SiteDocument;
  /** Vrai quand le contenu vient de la démonstration locale, pas du compartiment. */
  demonstration: boolean;
}

/** Identifiant lu dans le lien de démonstration : `/demo/{id}` ou `?id={id}`. */
export function dossierIdFromLocation(location: Location = window.location): string {
  const parameters = new URLSearchParams(location.search);
  const fromQuery = parameters.get("id") ?? parameters.get("demo");
  if (fromQuery) {
    return fromQuery;
  }

  const segments = location.pathname.split("/").filter(Boolean);
  const marker = segments.indexOf("demo");
  if (marker >= 0 && segments[marker + 1]) {
    return segments[marker + 1];
  }
  return segments.length > 0 ? segments[segments.length - 1] : "";
}

/** Adresse du document publié, ou null si le compartiment n'est pas configuré. */
export function siteDocumentUrl(id: string): string | null {
  if (!STORAGE_BASE || !id) {
    return null;
  }
  return `${STORAGE_BASE}/${PREFIX}/${id}/hotel/site.json`;
}

export async function loadDossier(id: string): Promise<Dossier> {
  const url = siteDocumentUrl(id);
  if (url) {
    try {
      // no-cache : le statut « paye » doit être revu après le paiement, même si
      // une ancienne version du document est encore en cache navigateur.
      const response = await fetch(url, { cache: "no-cache" });
      if (response.ok) {
        return { id, site: validateSite(await response.json()), demonstration: false };
      }
    } catch {
      // Compartiment injoignable : on poursuit avec la démonstration locale.
    }
  }
  return { id, site: validateSite(demoRaw), demonstration: true };
}
