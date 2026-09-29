import { useEffect, useRef, useState } from "react";
import { ArrowDownToLine, Pause, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { LogLine } from "@/lib/types";
import { Button } from "./ui/button";

const LEVEL_CLASS: Record<string, string> = {
  debug: "text-zinc-500",
  info: "text-sky-300",
  warning: "text-amber-300",
  error: "text-red-400",
  critical: "text-red-400",
};

const HIDDEN_FIELDS = new Set(["counters", "run_id"]);

function formatFields(fields: Record<string, unknown>): string {
  return Object.entries(fields)
    .filter(([k, v]) => !HIDDEN_FIELDS.has(k) && v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" ");
}

function time(ts: string | null): string {
  if (!ts) return "        ";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts.slice(11, 19) : d.toLocaleTimeString("en-GB", { hour12: false });
}

/** Terminal-style log panel. Always LTR (logs are code), mono, level colours, pausable auto-scroll. */
export function LogTerminal({
  lines,
  className,
  emptyText,
  live,
  toolbar,
}: {
  lines: LogLine[];
  className?: string;
  emptyText?: string;
  live?: boolean;
  toolbar?: React.ReactNode;
}) {
  const { t, fmtNumber } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);

  useEffect(() => {
    if (follow && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [lines, follow]);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (!atBottom && follow) setFollow(false);
  };

  return (
    <div className={cn("flex min-h-0 flex-col overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-200", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <Terminal className="h-3.5 w-3.5" />
          <span>{t("live.logs")}</span>
          {live && <span className="h-1.5 w-1.5 animate-soft-pulse rounded-full bg-emerald-400" aria-hidden />}
          <span className="tabular text-zinc-500">· {t("live.lines", { n: fmtNumber(lines.length) })}</span>
        </div>
        <div className="flex items-center gap-1">
          {toolbar}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50"
            onClick={() => setFollow((f) => !f)}
            aria-pressed={follow}
          >
            {follow ? <ArrowDownToLine /> : <Pause />}
            <span className="hidden sm:inline">{follow ? t("live.follow") : t("live.paused")}</span>
          </Button>
        </div>
      </div>
      <div
        ref={ref}
        onScroll={onScroll}
        dir="ltr"
        role="log"
        aria-live={live ? "polite" : "off"}
        className="min-h-0 flex-1 overflow-auto p-3 font-mono text-[12px] leading-5 scrollbar-thin"
      >
        {lines.length === 0 ? (
          <p className="text-zinc-500">{emptyText ?? t("live.waiting")}</p>
        ) : (
          lines.map((l) => (
            <div key={l.seq} className="flex gap-3 whitespace-pre-wrap break-all hover:bg-zinc-900/60">
              <span className="shrink-0 select-none text-zinc-600">{time(l.ts)}</span>
              <span className={cn("w-12 shrink-0 select-none uppercase", LEVEL_CLASS[l.level] ?? "text-zinc-400")}>
                {l.level.slice(0, 5)}
              </span>
              <span className="min-w-0">
                <span className={cn("text-zinc-100", l.level === "error" && "text-red-300")}>{l.event}</span>
                {Object.keys(l.fields).length > 0 && <span className="text-zinc-500"> {formatFields(l.fields)}</span>}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
