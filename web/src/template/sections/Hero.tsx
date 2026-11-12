import EditableText from "../../editor/EditableText";
import PhotoSlot from "../../editor/PhotoSlot";
import type { HeroSection, MediaItem } from "../../document/types";
import { useStudio } from "../../studio/studio-context";

interface HeroProps {
  section: HeroSection;
  media: MediaItem[];
}

/**
 * Bandeau d'accueil : grande photo, titre, introduction et bouton de réservation.
 * En édition, le clic sur le bouton ne déclenche pas la navigation : il sert à
 * modifier le libellé.
 */
export default function Hero({ section, media }: HeroProps) {
  const { mode } = useStudio();

  return (
    <section className="hero">
      <PhotoSlot
        sectionId={section.id}
        photoId={section.media.photo_id}
        media={media}
        ratio={section.media.ratio}
        focal={section.media.focal}
        className="hero-photo"
      />
      <div className="hero-body">
        <EditableText
          as="h1"
          sectionId={section.id}
          field="title"
          value={section.content.title}
          className="hero-title"
        />
        <EditableText
          as="p"
          sectionId={section.id}
          field="intro"
          value={section.content.intro}
          className="hero-intro"
          multiline
          block
        />
        <a
          className="hero-cta"
          href={section.content.cta_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(event) => {
            if (mode === "edit") {
              event.preventDefault();
            }
          }}
        >
          <EditableText
            sectionId={section.id}
            field="cta_label"
            value={section.content.cta_label}
          />
        </a>
        {mode === "edit" && (
          <p className="hero-cta-url">
            Lien du bouton :{" "}
            <EditableText
              sectionId={section.id}
              field="cta_url"
              value={section.content.cta_url}
            />
          </p>
        )}
      </div>
    </section>
  );
}
