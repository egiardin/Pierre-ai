/**
 * Contrat du document de site (site.json).
 *
 * C'est le point central du pilote : le template, l'éditeur manuel et, plus tard,
 * l'agent Pierre liront et modifieront tous cette même structure.
 *
 * Analogie C : c'est une structure sérialisée. `type` joue le rôle d'un tag
 * d'union, et chaque variante possède ses propres champs. Aucune écriture directe
 * n'est autorisée : on passe toujours par `applyPatch`.
 */

export type SectionType = "hero" | "rooms" | "services" | "gallery" | "contact";

export type MediaSource = "demo" | "extraction" | "upload";
export type MediaStatus = "demo" | "extracted" | "validated";

export interface MediaItem {
  /** Identifiant stable, référencé par les sections. */
  id: string;
  /** Emplacement du fichier (chemin local ou URL pour la démonstration). */
  file: string;
  width: number;
  height: number;
  source: MediaSource;
  status: MediaStatus;
  alt?: string;
}

/** Point d'ancrage du cadrage, exprimé en fraction (0 à 1). */
export interface Focal {
  x: number;
  y: number;
}

export interface HeroSection {
  id: string;
  type: "hero";
  content: {
    title: string;
    intro: string;
    cta_label: string;
    cta_url: string;
  };
  media: {
    photo_id: string;
    focal: Focal;
    ratio: string;
  };
}

export interface RoomItem {
  id: string;
  title: string;
  text: string;
  photo_id: string;
}

export interface RoomsSection {
  id: string;
  type: "rooms";
  content: { title: string };
  items: RoomItem[];
}

export interface ServiceItem {
  id: string;
  label: string;
}

export interface ServicesSection {
  id: string;
  type: "services";
  content: { title: string };
  items: ServiceItem[];
}

export interface GalleryItem {
  id: string;
  photo_id: string;
}

export interface GallerySection {
  id: string;
  type: "gallery";
  content: { title: string };
  items: GalleryItem[];
}

export interface ContactSection {
  id: string;
  type: "contact";
  content: {
    title: string;
    address: string;
    phone: string;
    email: string;
    booking_url: string;
  };
}

export type Section =
  | HeroSection
  | RoomsSection
  | ServicesSection
  | GallerySection
  | ContactSection;

export interface SitePage {
  id: string;
  sections: Section[];
}

export interface SiteDocument {
  schema_version: 1;
  slug: string;
  /** Numéro de version du brouillon. Sert plus tard au contrôle de concurrence. */
  version: number;
  status: "draft" | "published";
  pages: SitePage[];
  media: MediaItem[];
}

/** Modification demandée. Toujours validée avant application. */
export type Patch =
  | {
      op: "setText";
      sectionId: string;
      /** Si absent, la cible est le contenu de la section. */
      itemId?: string;
      field: string;
      value: string;
    }
  | {
      op: "setPhoto";
      sectionId: string;
      /** Si absent, la cible est la photo de section (hero). */
      itemId?: string;
      photoId: string;
    };

export type PatchResult =
  | { ok: true; site: SiteDocument }
  | { ok: false; error: string };
