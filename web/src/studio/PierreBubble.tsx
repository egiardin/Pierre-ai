import { useEffect, useRef, useState } from "react";

interface PierreBubbleProps {
  selectedSection: string | null;
}

interface Position {
  x: number;
  y: number;
}

const BUTTON_WIDTH = 72;
const BUTTON_HEIGHT = 64;
const PANEL_WIDTH = 320;
const PANEL_HEIGHT = 260;
const EDGE_GAP = 16;

function clampPosition(position: Position): Position {
  return {
    x: Math.min(
      Math.max(EDGE_GAP, position.x),
      window.innerWidth - BUTTON_WIDTH - EDGE_GAP
    ),
    y: Math.min(
      Math.max(EDGE_GAP, position.y),
      window.innerHeight - BUTTON_HEIGHT - EDGE_GAP
    ),
  };
}

/** Bulle de Pierre, déplaçable à la souris ou au toucher. */
export default function PierreBubble({ selectedSection }: PierreBubbleProps) {
  const [position, setPosition] = useState<Position>(() => ({
    x: Math.max(EDGE_GAP, window.innerWidth - BUTTON_WIDTH - 32),
    y: Math.max(EDGE_GAP, window.innerHeight - BUTTON_HEIGHT - 32),
  }));
  const [open, setOpen] = useState(false);
  const moved = useRef(false);
  const drag = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
    startX: number;
    startY: number;
  } | null>(null);

  useEffect(() => {
    const onResize = () => setPosition((current) => clampPosition(current));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const maxPanelLeft = Math.max(
    EDGE_GAP,
    window.innerWidth - PANEL_WIDTH - EDGE_GAP
  );
  const panelLeft = Math.min(
    Math.max(EDGE_GAP, position.x + BUTTON_WIDTH - PANEL_WIDTH),
    maxPanelLeft
  );
  const maxPanelTop = Math.max(
    EDGE_GAP,
    window.innerHeight - PANEL_HEIGHT - EDGE_GAP
  );
  const topbarBottom =
    document.querySelector(".topbar")?.getBoundingClientRect().bottom ?? 0;
  const minPanelTop = Math.min(
    topbarBottom + EDGE_GAP,
    maxPanelTop
  );
  const canOpenAbove =
    position.y - PANEL_HEIGHT - 12 >= minPanelTop;
  const preferredPanelTop =
    canOpenAbove
      ? position.y - PANEL_HEIGHT - 12
      : position.y + BUTTON_HEIGHT + 12;
  const panelTop = Math.min(
    Math.max(minPanelTop, preferredPanelTop),
    maxPanelTop
  );

  return (
    <>
      {open && (
        <section
          className="pierre-popover"
          style={{ left: panelLeft, top: panelTop }}
          aria-label="Assistant Pierre"
        >
          <header className="pierre-popover-head">
            <span className="assistant-logo assistant-logo-small" aria-hidden="true">
              <i />
              <i />
            </span>
            <div>
              <strong>Pierre</strong>
              <span className="pierre-connection">Bientôt disponible</span>
            </div>
            <button
              type="button"
              className="pierre-close"
              onClick={() => setOpen(false)}
              aria-label="Fermer l'assistant"
            >
              ×
            </button>
          </header>
          <p>
            Je pourrai bientôt vous accompagner pour cette section. En
            attendant, vous pouvez modifier les textes directement sur la page.
          </p>
          <div className="pierre-selection">
            Section sélectionnée
            <strong>{selectedSection ?? "Aucune"}</strong>
          </div>
          <div className="pierre-disabled-input">
            <span>La conversation sera bientôt disponible</span>
            <span aria-hidden="true">↗</span>
          </div>
        </section>
      )}

      <button
        type="button"
        className="pierre-fab"
        style={{ left: position.x, top: position.y }}
        aria-label="Ouvrir Pierre. Faire glisser pour déplacer."
        aria-expanded={open}
        title="Pierre"
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          moved.current = false;
          drag.current = {
            pointerId: event.pointerId,
            offsetX: event.clientX - position.x,
            offsetY: event.clientY - position.y,
            startX: event.clientX,
            startY: event.clientY,
          };
        }}
        onPointerMove={(event) => {
          const activeDrag = drag.current;
          if (!activeDrag || activeDrag.pointerId !== event.pointerId) {
            return;
          }
          if (
            Math.abs(event.clientX - activeDrag.startX) > 4 ||
            Math.abs(event.clientY - activeDrag.startY) > 4
          ) {
            moved.current = true;
          }
          setPosition(
            clampPosition({
              x: event.clientX - activeDrag.offsetX,
              y: event.clientY - activeDrag.offsetY,
            })
          );
        }}
        onPointerUp={(event) => {
          if (drag.current?.pointerId === event.pointerId) {
            drag.current = null;
          }
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
        onClick={() => {
          if (moved.current) {
            moved.current = false;
            return;
          }
          setOpen((current) => !current);
        }}
      >
        <span className="mascot pierre-mascot" aria-hidden="true">
          <i />
          <i />
        </span>
      </button>
    </>
  );
}
