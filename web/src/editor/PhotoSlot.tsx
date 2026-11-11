import type { Focal, MediaItem } from "../document/types";
import { useStudio } from "../studio/studio-context";

interface PhotoSlotProps {
  sectionId: string;
  itemId?: string;
  photoId: string;
  media: MediaItem[];
  ratio?: string;
  focal?: Focal;
  className?: string;
}

function toAspectRatio(ratio: string): string {
  const [width, height] = ratio.split(":").map(Number);
  if (!width || !height) {
    return "4 / 3";
  }
  return `${width} / ${height}`;
}

/**
 * Emplacement photo du template.
 * Le rendu utilise « cover » : jamais d'étirement. Le cadrage vient de `focal`.
 */
export default function PhotoSlot({
  sectionId,
  itemId,
  photoId,
  media,
  ratio = "4:3",
  focal,
  className = "",
}: PhotoSlotProps) {
  const { mode, requestPhoto } = useStudio();
  const photo = media.find((item) => item.id === photoId);
  const objectPosition = focal ? `${focal.x * 100}% ${focal.y * 100}%` : "center";

  return (
    <div
      className={`photo ${className}`.trim()}
      style={{ aspectRatio: toAspectRatio(ratio) }}
      onClick={(event) => event.stopPropagation()}
    >
      {photo ? (
        <img
          src={photo.file}
          alt={photo.alt ?? ""}
          loading="lazy"
          style={{ objectPosition }}
        />
      ) : (
        <div className="photo-missing">Photo introuvable ({photoId})</div>
      )}
      {mode === "edit" && (
        <button
          type="button"
          className="photo-change"
          onClick={(event) => {
            event.stopPropagation();
            requestPhoto(sectionId, itemId);
          }}
        >
          Changer la photo
        </button>
      )}
    </div>
  );
}
