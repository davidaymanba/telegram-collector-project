import { useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";

export function TagInput({
  value,
  onChange,
  placeholder,
  id,
  className,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  id?: string;
  className?: string;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const parts = raw.split(/[,،\n]/).map((s) => s.trim()).filter(Boolean);
    if (!parts.length) return;
    const seen = new Set(value.map((v) => v.toLocaleLowerCase()));
    const next = [...value];
    for (const p of parts) {
      if (!seen.has(p.toLocaleLowerCase())) {
        seen.add(p.toLocaleLowerCase());
        next.push(p);
      }
    }
    onChange(next);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === "," || e.key === "،") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div
      className={cn(
        "flex min-h-9 w-full flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5 text-sm transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background",
        className,
      )}
    >
      {value.map((tag) => (
        <span key={tag} className="inline-flex items-center gap-1 rounded bg-secondary py-0.5 pe-1 ps-2 text-xs font-medium">
          {tag}
          <button
            type="button"
            className="rounded p-0.5 text-muted-foreground hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => onChange(value.filter((v) => v !== tag))}
            aria-label={t("subjects.removeKeyword", { kw: tag })}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => add(draft)}
        onPaste={(e) => {
          const text = e.clipboardData.getData("text");
          if (/[,،\n]/.test(text)) {
            e.preventDefault();
            add(text);
          }
        }}
        placeholder={value.length ? "" : placeholder}
        className="min-w-[8rem] flex-1 bg-transparent py-0.5 outline-none placeholder:text-muted-foreground"
      />
    </div>
  );
}
