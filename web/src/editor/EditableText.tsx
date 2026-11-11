import { useEffect, useState } from "react";

import { useStudio } from "../studio/studio-context";

interface EditableTextProps {
  sectionId: string;
  itemId?: string;
  field: string;
  value: string;
  /** Balise de rendu (h1, h2, p, span...). */
  as?: keyof JSX.IntrinsicElements;
  className?: string;
  multiline?: boolean;
  block?: boolean;
}

/**
 * Texte modifiable en place.
 *
 * En mode aperçu, il rend simplement le texte.
 * En mode édition, un clic ouvre un champ ; la modification n'est transmise au
 * studio qu'à la validation (Entrée, perte du focus). La touche Échap annule.
 */
export default function EditableText({
  sectionId,
  itemId,
  field,
  value,
  as = "span",
  className = "",
  multiline = false,
  block = false,
}: EditableTextProps) {
  const { mode, commitText } = useStudio();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    if (!editing) {
      setDraft(value);
    }
  }, [value, editing]);

  const Tag = as;

  if (mode === "preview") {
    return <Tag className={className}>{value}</Tag>;
  }

  const base = ["et", block ? "et-block" : "", className, editing ? "" : "et-edit"]
    .filter(Boolean)
    .join(" ");

  const finish = () => {
    setEditing(false);
    if (draft !== value) {
      commitText(sectionId, itemId, field, draft);
    }
  };

  const cancel = () => {
    setDraft(value);
    setEditing(false);
  };

  if (editing) {
    if (multiline) {
      return (
        <textarea
          className={`${base} et-input`}
          value={draft}
          autoFocus
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={finish}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              cancel();
            }
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              finish();
            }
          }}
        />
      );
    }

    return (
      <input
        className={`${base} et-input`}
        value={draft}
        autoFocus
        onClick={(event) => event.stopPropagation()}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={finish}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            cancel();
          }
          if (event.key === "Enter") {
            event.preventDefault();
            finish();
          }
        }}
      />
    );
  }

  return (
    <Tag
      className={base}
      title="Cliquer pour modifier"
      onClick={(event) => {
        event.stopPropagation();
        setDraft(value);
        setEditing(true);
      }}
    >
      {value}
    </Tag>
  );
}
