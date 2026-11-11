import { useEffect, useReducer, useState } from "react";

import { applyPatch, findSection } from "../document/patch";
import type { Patch, SiteDocument } from "../document/types";
import { validateSite } from "../document/validate";
import SiteRenderer from "../template/SiteRenderer";
import PhotoPicker from "../editor/PhotoPicker";
import SectionOutline from "../editor/SectionOutline";
import demoRaw from "../data/site.demo.json";
import DeviceFrame from "./DeviceFrame";
import PierreBubble from "./PierreBubble";
import {
  StudioContext,
  type StudioApi,
  type StudioDevice,
  type StudioMode,
} from "./studio-context";

/** Document de départ. Validé une fois : le studio ne travaille que sur du valide. */
const INITIAL_SITE: SiteDocument = validateSite(demoRaw);

interface StudioState {
  site: SiteDocument;
  /** États précédents, du plus ancien au plus récent. Sert à l'annulation. */
  history: SiteDocument[];
  lastError: string | null;
}

type StudioAction =
  | { type: "patch"; patch: Patch }
  | { type: "undo" };

/**
 * Un seul point d'entrée pour toutes les modifications.
 * Le réducteur est pur : il ne touche ni au DOM ni au réseau, ce qui rend
 * l'annulation fiable (chaque état reste intact, comme un instantané en C).
 */
function reducer(state: StudioState, action: StudioAction): StudioState {
  if (action.type === "undo") {
    if (state.history.length === 0) {
      return state;
    }
    const previous = state.history[state.history.length - 1];
    return {
      site: previous,
      history: state.history.slice(0, -1),
      lastError: null,
    };
  }

  const result = applyPatch(state.site, action.patch);
  if (!result.ok) {
    return { ...state, lastError: result.error };
  }
  return {
    site: result.site,
    history: [...state.history, state.site],
    lastError: null,
  };
}

function initialState(site: SiteDocument): StudioState {
  return { site, history: [], lastError: null };
}

interface StudioShellProps {
  /** Document de départ. Sans lui, la démonstration locale. */
  initialSite?: SiteDocument;
  /** Retour au choix du template. */
  onBack?: () => void;
  /** Étape suivante du parcours. */
  onNext?: () => void;
}

/**
 * Assemblage du studio : un seul document, un seul chemin d'écriture.
 * Le template ne modifie rien : il demande une action via le contexte.
 */
export default function StudioShell({
  initialSite = INITIAL_SITE,
  onBack,
  onNext,
}: StudioShellProps = {}) {
  const [state, dispatch] = useReducer(reducer, initialSite, initialState);
  const [mode, setMode] = useState<StudioMode>("edit");
  const [device, setDevice] = useState<StudioDevice>("desktop");
  const [selectedId, setSelectedId] = useState<string | null>("hero");
  const [pendingPhoto, setPendingPhoto] = useState<{
    sectionId: string;
    itemId?: string;
  } | null>(null);

  const { site, lastError } = state;

  // Raccourci d'annulation. On l'ignore pendant la saisie d'un texte,
  // pour ne pas casser l'annulation native du champ.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") {
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        dispatch({ type: "undo" });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const commitText = (
    sectionId: string,
    itemId: string | undefined,
    field: string,
    value: string
  ) => {
    dispatch({ type: "patch", patch: { op: "setText", sectionId, itemId, field, value } });
  };

  const requestPhoto = (sectionId: string, itemId: string | undefined) => {
    setPendingPhoto({ sectionId, itemId });
  };

  const api: StudioApi = {
    mode,
    selectedId,
    select: setSelectedId,
    commitText,
    requestPhoto,
    lastError,
  };

  // Photo actuellement posée à l'emplacement ouvert dans le sélecteur.
  let currentPhotoId: string | undefined;
  if (pendingPhoto) {
    const section = findSection(site, pendingPhoto.sectionId);
    if (section?.type === "hero" && pendingPhoto.itemId === undefined) {
      currentPhotoId = section.media.photo_id;
    } else if (section && "items" in section && pendingPhoto.itemId) {
      const item = (
        section.items as unknown as Array<Record<string, unknown>>
      ).find((candidate) => candidate.id === pendingPhoto.itemId);
      const photoId = item?.photo_id;
      currentPhotoId = typeof photoId === "string" ? photoId : undefined;
    }
  }

  const chrome = mode === "edit";
  const host = `https://www.${site.slug}.fr`;

  return (
    <StudioContext.Provider value={api}>
      <div className="shell">
        <header className="topbar">
          <div className="brand">
            <span className="mascot brand-mascot" aria-hidden="true">
              <i />
              <i />
            </span>
            <span className="brand-logo">
              pierre<span className="brand-dot">.</span>
            </span>
            <span className="brand-tag">Studio</span>
            <span className="slug">{site.slug}</span>
          </div>

          <div className="topbar-actions">
            <div className="segmented" role="group" aria-label="Mode">
              <button
                type="button"
                className={mode === "edit" ? "active" : ""}
                onClick={() => setMode("edit")}
              >
                Édition
              </button>
              <button
                type="button"
                className={mode === "preview" ? "active" : ""}
                onClick={() => setMode("preview")}
              >
                Aperçu
              </button>
            </div>

            {!chrome && (
              <div className="segmented" role="group" aria-label="Affichage">
                <button
                  type="button"
                  className={device === "desktop" ? "active" : ""}
                  onClick={() => setDevice("desktop")}
                >
                  Ordinateur
                </button>
                <button
                  type="button"
                  className={device === "mobile" ? "active" : ""}
                  onClick={() => setDevice("mobile")}
                >
                  Mobile
                </button>
              </div>
            )}

          </div>
        </header>

        {lastError && (
          <div className="error-banner" role="alert">
            {lastError}
          </div>
        )}

        <div className={`workspace ${chrome ? "" : "no-chrome"}`}>
          {chrome && (
            <aside className="sidebar">
              <SectionOutline site={site} />
            </aside>
          )}

          <main className={`canvas ${chrome ? "canvas-edit" : ""}`}>
            {chrome ? (
              <div className="canvas-frame">
                <SiteRenderer site={site} />
              </div>
            ) : (
              <DeviceFrame device={device} host={host} mode={mode}>
                <div className="device-page">
                  <SiteRenderer site={site} />
                </div>
              </DeviceFrame>
            )}
          </main>

        </div>

        <footer className="studio-foot">
          <button type="button" className="btn btn-primary" onClick={onBack}>
            Retour
          </button>
          <button type="button" className="btn btn-primary" onClick={onNext}>
            Suivant
          </button>
        </footer>

        <PierreBubble selectedSection={selectedId} />

        {pendingPhoto && (
          <PhotoPicker
            media={site.media}
            currentId={currentPhotoId}
            onChoose={(photoId) => {
              dispatch({
                type: "patch",
                patch: {
                  op: "setPhoto",
                  sectionId: pendingPhoto.sectionId,
                  itemId: pendingPhoto.itemId,
                  photoId,
                },
              });
              setPendingPhoto(null);
            }}
            onClose={() => setPendingPhoto(null)}
          />
        )}
      </div>
    </StudioContext.Provider>
  );
}
