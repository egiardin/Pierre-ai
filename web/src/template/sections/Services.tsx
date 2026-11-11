import EditableText from "../../editor/EditableText";
import type { MediaItem, ServicesSection } from "../../document/types";

interface ServicesProps {
  section: ServicesSection;
  media: MediaItem[];
}

/**
 * Services et équipements.
 * Ces libellés proviennent de l'extraction : ils ne doivent jamais être
 * inventés par l'agent, seulement corrigés ou reformulés.
 */
export default function Services({ section }: ServicesProps) {
  return (
    <section className="services">
      <EditableText
        as="h2"
        sectionId={section.id}
        field="title"
        value={section.content.title}
        className="section-title"
      />
      <ul className="services-list">
        {section.items.map((item) => (
          <li key={item.id}>
            <EditableText
              sectionId={section.id}
              itemId={item.id}
              field="label"
              value={item.label}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
