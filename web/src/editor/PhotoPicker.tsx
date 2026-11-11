import type { MediaItem } from "../document/types";

interface PhotoPickerProps {
  media: MediaItem[];
  currentId?: string;
  onChoose(photoId: string): void;
  onClose(): void;
}

/** Seuil au-dessous duquel on signale une résolution insuffisante. */
const MIN_WIDTH = 1200;

/**
 * Sélection d'une photo parmi les médias du projet.
 * Le choix est transmis au studio, qui valide puis applique la modification.
 */
export default function PhotoPicker({
  media,
  currentId,
  onChoose,
  onClose,
}: PhotoPickerProps) {
  return (
    <div className="picker-backdrop" onClick={onClose}>
      <div className="picker" onClick={(event) => event.stopPropagation()}>
        <div className="picker-head">
          <h2>Choisir une photo</h2>
          <button type="button" className="link-button" onClick={onClose}>
            Fermer
          </button>
        </div>
        <p className="hint">
          Photos disponibles pour ce projet. Les fichiers originaux sont conservés.
        </p>
        <div className="picker-grid">
          {media.map((item) => {
            const lowResolution = item.width < MIN_WIDTH;
            return (
              <button
                key={item.id}
                type="button"
                className={`picker-item ${item.id === currentId ? "selected" : ""}`}
                onClick={() => onChoose(item.id)}
              >
                <img src={item.file} alt={item.alt ?? ""} loading="lazy" />
                <div className={`picker-meta ${lowResolution ? "warn" : ""}`}>
                  {item.width} × {item.height}
                  {lowResolution ? " · résolution limitée" : ""}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
