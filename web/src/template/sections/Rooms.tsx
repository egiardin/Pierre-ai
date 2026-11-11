import EditableText from "../../editor/EditableText";
import PhotoSlot from "../../editor/PhotoSlot";
import type { MediaItem, RoomsSection } from "../../document/types";

interface RoomsProps {
  section: RoomsSection;
  media: MediaItem[];
}

/** Liste des chambres : une carte par chambre, avec sa photo. */
export default function Rooms({ section, media }: RoomsProps) {
  return (
    <section className="rooms">
      <EditableText
        as="h2"
        sectionId={section.id}
        field="title"
        value={section.content.title}
        className="section-title"
      />
      <div className="rooms-grid">
        {section.items.map((item) => (
          <article className="room-card" key={item.id}>
            <PhotoSlot
              sectionId={section.id}
              itemId={item.id}
              photoId={item.photo_id}
              media={media}
              ratio="4:3"
            />
            <EditableText
              as="h3"
              sectionId={section.id}
              itemId={item.id}
              field="title"
              value={item.title}
              className="room-title"
            />
            <EditableText
              as="p"
              sectionId={section.id}
              itemId={item.id}
              field="text"
              value={item.text}
              className="room-text"
              multiline
              block
            />
          </article>
        ))}
      </div>
    </section>
  );
}
