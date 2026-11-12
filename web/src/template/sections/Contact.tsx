import EditableText from "../../editor/EditableText";
import type { ContactSection, MediaItem } from "../../document/types";
import { useStudio } from "../../studio/studio-context";

interface ContactProps {
  section: ContactSection;
  media: MediaItem[];
}

/**
 * Contact et accès.
 * Les coordonnées sont sensibles : elles viennent de l'extraction et sont
 * éditables, jamais générées.
 */
export default function Contact({ section }: ContactProps) {
  const { mode } = useStudio();
  return (
    <section className="contact">
      <EditableText
        as="h2"
        sectionId={section.id}
        field="title"
        value={section.content.title}
        className="section-title"
      />
      <dl className="contact-list">
        <div>
          <dt>Adresse</dt>
          <dd>
            <EditableText
              sectionId={section.id}
              field="address"
              value={section.content.address}
            />
          </dd>
        </div>
        <div>
          <dt>Téléphone</dt>
          <dd>
            <EditableText
              sectionId={section.id}
              field="phone"
              value={section.content.phone}
            />
          </dd>
        </div>
        <div>
          <dt>E-mail</dt>
          <dd>
            <EditableText
              sectionId={section.id}
              field="email"
              value={section.content.email}
            />
          </dd>
        </div>
      </dl>
      <a
        className="booking"
        href={section.content.booking_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Réserver en ligne
      </a>
      {mode === "edit" && (
        <p className="contact-booking-url">
          Lien de réservation :{" "}
          <EditableText
            sectionId={section.id}
            field="booking_url"
            value={section.content.booking_url}
          />
        </p>
      )}
    </section>
  );
}
