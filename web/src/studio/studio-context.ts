import { createContext, useContext } from "react";

export type StudioMode = "edit" | "preview";
export type StudioDevice = "desktop" | "mobile";

/**
 * Surface exposée aux composants de template et d'édition.
 * Les composants ne modifient jamais le document : ils demandent une action.
 */
export interface StudioApi {
  mode: StudioMode;
  selectedId: string | null;
  select(sectionId: string | null): void;
  commitText(
    sectionId: string,
    itemId: string | undefined,
    field: string,
    value: string
  ): void;
  requestPhoto(sectionId: string, itemId: string | undefined): void;
  lastError: string | null;
}

export const StudioContext = createContext<StudioApi | null>(null);

export function useStudio(): StudioApi {
  const api = useContext(StudioContext);
  if (!api) {
    throw new Error("useStudio doit être utilisé à l'intérieur de StudioShell.");
  }
  return api;
}
