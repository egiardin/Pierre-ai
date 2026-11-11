import type { Patch, PatchResult, Section, SiteDocument } from "./types";

/**
 * Recherche une section par identifiant, toutes pages confondues.
 */
export function findSection(
  site: SiteDocument,
  sectionId: string
): Section | undefined {
  for (const page of site.pages) {
    const found = page.sections.find((section) => section.id === sectionId);
    if (found) {
      return found;
    }
  }
  return undefined;
}

/**
 * Remplace une section sans modifier le document d'origine.
 * On reconstruit les tableaux plutôt que de muter : c'est ce qui rend
 * l'annulation fiable (chaque état reste intact).
 */
function replaceSection(
  site: SiteDocument,
  sectionId: string,
  next: Section
): SiteDocument {
  return {
    ...site,
    pages: site.pages.map((page) => ({
      ...page,
      sections: page.sections.map((section) =>
        section.id === sectionId ? next : section
      ),
    })),
  };
}

/**
 * Applique une valeur à un champ textuel existant.
 * Refuse un champ absent ou non textuel.
 */
function setStringField<T extends object>(
  target: T,
  field: string,
  value: string
): { ok: true; next: T } | { ok: false; error: string } {
  const record = target as Record<string, unknown>;
  if (!(field in record)) {
    return { ok: false, error: `Champ inconnu : ${field}.` };
  }
  if (typeof record[field] !== "string") {
    return { ok: false, error: `Le champ ${field} n'est pas un texte.` };
  }
  return { ok: true, next: { ...target, [field]: value } as T };
}

function applySetText(
  site: SiteDocument,
  patch: Extract<Patch, { op: "setText" }>
): PatchResult {
  const section = findSection(site, patch.sectionId);
  if (!section) {
    return { ok: false, error: `Section inconnue : ${patch.sectionId}.` };
  }
  if (typeof patch.value !== "string") {
    return { ok: false, error: "Valeur textuelle attendue." };
  }

  if (patch.itemId === undefined) {
    const result = setStringField(section.content, patch.field, patch.value);
    if (!result.ok) {
      return result;
    }
    return {
      ok: true,
      site: replaceSection(site, section.id, {
        ...section,
        content: result.next,
      } as Section),
    };
  }

  if (!("items" in section)) {
    return {
      ok: false,
      error: `La section ${patch.sectionId} n'a pas d'éléments.`,
    };
  }

  const items = section.items as unknown as Array<Record<string, unknown>>;
  const index = items.findIndex((item) => item.id === patch.itemId);
  if (index < 0) {
    return { ok: false, error: `Élément inconnu : ${patch.itemId}.` };
  }

  const result = setStringField(items[index], patch.field, patch.value);
  if (!result.ok) {
    return result;
  }

  const nextItems = items.map((item, position) =>
    position === index ? result.next : item
  );

  return {
    ok: true,
    site: replaceSection(site, section.id, {
      ...section,
      items: nextItems,
    } as unknown as Section),
  };
}

function applySetPhoto(
  site: SiteDocument,
  patch: Extract<Patch, { op: "setPhoto" }>
): PatchResult {
  const section = findSection(site, patch.sectionId);
  if (!section) {
    return { ok: false, error: `Section inconnue : ${patch.sectionId}.` };
  }
  if (!site.media.some((media) => media.id === patch.photoId)) {
    return {
      ok: false,
      error: `Média inconnu ou non autorisé pour ce projet : ${patch.photoId}.`,
    };
  }

  if (section.type === "hero" && patch.itemId === undefined) {
    return {
      ok: true,
      site: replaceSection(site, section.id, {
        ...section,
        media: { ...section.media, photo_id: patch.photoId },
      }),
    };
  }

  if (!("items" in section) || patch.itemId === undefined) {
    return {
      ok: false,
      error: "Cette cible n'accepte pas de photo.",
    };
  }

  const items = section.items as unknown as Array<Record<string, unknown>>;
  const index = items.findIndex((item) => item.id === patch.itemId);
  if (index < 0) {
    return { ok: false, error: `Élément inconnu : ${patch.itemId}.` };
  }
  if (typeof items[index].photo_id !== "string") {
    return { ok: false, error: "Cet élément ne porte pas de photo." };
  }

  const nextItems = items.map((item, position) =>
    position === index ? { ...item, photo_id: patch.photoId } : item
  );

  return {
    ok: true,
    site: replaceSection(site, section.id, {
      ...section,
      items: nextItems,
    } as unknown as Section),
  };
}

/**
 * Valide puis applique une modification. Renvoie un nouveau document ou une erreur.
 * Aucune exception : l'appelant décide de l'affichage.
 */
export function applyPatch(site: SiteDocument, patch: Patch): PatchResult {
  if (patch.op === "setText") {
    return applySetText(site, patch);
  }
  return applySetPhoto(site, patch);
}
