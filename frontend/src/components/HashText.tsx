import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { cn, shortHash } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

export function CopyButton({ value, className, label }: { value: string; className?: string; label?: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={label ?? t("common.copy")}
      className={cn(
        "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      onClick={async (e) => {
        e.stopPropagation();
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          toast.success(t("common.copied"));
          setTimeout(() => setCopied(false), 1500);
        } catch {
          toast.error(t("common.errorTitle"));
        }
      }}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-primary" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

/** Long ids/hashes: shortened, full value in a tooltip, one-click copy. Always LTR. */
export function HashText({ value, head = 8, tail = 4, className }: { value: string | number | null | undefined; head?: number; tail?: number; className?: string }) {
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">—</span>;
  const full = String(value);
  return (
    <span className={cn("inline-flex items-center gap-1", className)} dir="ltr">
      <Tooltip>
        <TooltipTrigger asChild>
          <code tabIndex={0} className="cursor-default rounded font-mono text-xs text-foreground/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {shortHash(full, head, tail)}
          </code>
        </TooltipTrigger>
        <TooltipContent className="font-mono text-[11px]">{full}</TooltipContent>
      </Tooltip>
      <CopyButton value={full} />
    </span>
  );
}
