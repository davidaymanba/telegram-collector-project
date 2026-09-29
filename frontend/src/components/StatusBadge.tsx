import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { FileStatus, JobState, Run } from "@/lib/types";

// One mapping from state → semantic token, reused by badges, filters and charts.
export const STATUS_TOKEN: Record<string, string> = {
  classified: "status-classified",
  unclassified: "status-unclassified",
  duplicate: "status-duplicate",
  failed: "status-failed",
  unsupported: "status-unsupported",
  processing: "status-processing",
  downloaded: "status-downloaded",
  discovered: "status-processing",
  // runs / jobs / channels
  success: "status-classified",
  succeeded: "status-classified",
  active: "status-classified",
  running: "status-processing",
  queued: "status-processing",
  locked: "status-unclassified",
  aborted: "status-duplicate",
  idle: "status-duplicate",
  disabled: "status-unsupported",
  error: "status-failed",
};

export function statusColor(status: string, alpha = 1): string {
  return `hsl(var(--${STATUS_TOKEN[status] ?? "status-duplicate"}) / ${alpha})`;
}

const PULSING = new Set(["processing", "running", "queued", "discovered"]);

export function StatusDot({ status, className }: { status: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block h-1.5 w-1.5 shrink-0 rounded-full", PULSING.has(status) && "animate-soft-pulse", className)}
      style={{ backgroundColor: statusColor(status) }}
    />
  );
}

export function StatusBadge({
  status,
  label,
  className,
}: {
  status: string;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-xs font-medium",
        className,
      )}
      style={{
        color: statusColor(status),
        backgroundColor: statusColor(status, 0.08),
        borderColor: statusColor(status, 0.22),
      }}
    >
      <StatusDot status={status} />
      {label ?? status}
    </span>
  );
}

export function FileStatusBadge({ status }: { status: FileStatus }) {
  const { tx } = useI18n();
  return <StatusBadge status={status} label={tx(`status.${status}`)} />;
}

export function RunStatusBadge({ status }: { status: Run["status"] }) {
  const { tx } = useI18n();
  const key = status === "success" ? "success" : status;
  return <StatusBadge status={key} label={tx(`runStatus.${status}`)} />;
}

export function JobStateBadge({ state }: { state: JobState }) {
  const { tx } = useI18n();
  return <StatusBadge status={state} label={tx(`jobState.${state}`)} />;
}
