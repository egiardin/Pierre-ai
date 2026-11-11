import EditableText from "../../editor/EditableText";
import PhotoSlot from "../../editor/PhotoSlot";
import type { GallerySection, MediaItem } from "../../document/types";

interface GalleryProps {
  section: GallerySection;
  media: MediaItem[];
}

/** Galerie : grille carrée, chaque vignette clique pour changer de photo. */
export default function Gallery({ section, media }: GalleryProps) {
  return (
    <section className="gallery">
      <EditableText
        as="h2"
        sectionId={section.id}
        field="title"
        value={section.content.title}
        className="section-title"
      />
      <div className="gallery-grid">
        {section.items.map((item) => (
          <PhotoSlot
            key={item.id}
            sectionId={section.id}
            itemId={item.id}
            photoId={item.photo_id}
            media={media}
            ratio="1:1"
          />
        ))}
      </div>
    </section>
  );
}
