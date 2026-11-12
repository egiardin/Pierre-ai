import type { SiteDocument } from "./types";

/**
 * Vérification structurelle minimale du document.
 *
 * Objectif : refuser tôt un document incomplet plutôt que de laisser le rendu
 * échouer plus loin. On ne valide pas encore le contenu de chaque type de
 * section ; ce contrôle s'étoffera avec les lots suivants.
 */
export function validateSite(value: unknown): SiteDocument {
  if (typeof value !== "object" || value === null) {
    throw new Error("site.json : objet attendu.");
  }

  const doc = value as Record<string, unknown>;

  if (doc.schema_version !== 1) {
    throw new Error("site.json : schema_version doit valoir 1.");
  }
  if (typeof doc.slug !== "string" || doc.slug.length === 0) {
    throw new Error("site.json : slug manquant.");
  }
  if (typeof doc.version !== "number") {
    throw new Error("site.json : version manquante.");
  }
  if (doc.status !== "draft" && doc.status !== "paye" && doc.status !== "published") {
    throw new Error("site.json : statut invalide.");
  }
  if (!Array.isArray(doc.pages) || doc.pages.length === 0) {
    throw new Error("site.json : pages manquantes.");
  }
  if (!Array.isArray(doc.media)) {
    throw new Error("site.json : media manquant.");
  }

  for (const page of doc.pages) {
    const candidate = page as Record<string, unknown>;
    if (!Array.isArray(candidate.sections)) {
      throw new Error("site.json : une page n'a pas de sections.");
    }
    for (const section of candidate.sections) {
      const item = section as Record<string, unknown>;
      if (typeof item.id !== "string" || typeof item.type !== "string") {
        throw new Error("site.json : section sans id ou sans type.");
      }
    }
  }

  for (const media of doc.media) {
    const item = media as Record<string, unknown>;
    if (typeof item.id !== "string" || typeof item.file !== "string") {
      throw new Error("site.json : média sans id ou sans fichier.");
    }
  }

  return value as SiteDocument;
}
