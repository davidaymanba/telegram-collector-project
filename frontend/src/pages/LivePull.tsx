import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Download, ExternalLink, Loader2, Lock, Play, Trash2, Workflow } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { ApiError } from "@/lib/api";
import type { Job } from "@/lib/types";
import {
  errorMessage,
  qk,
  useChannels,
  useInvalidateData,
  useJobs,
  useLock,
  useStartJob,
  useSystemStatus,
} from "@/hooks/queries";
import { useJobStream } from "@/hooks/use-job-stream";
import { PageHeader } from "@/components/PageHeader";
import { LogTerminal } from "@/components/LogTerminal";
import { JobStateBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ALL = "__all__";
const COUNTER_KEYS = ["new", "duplicate", "classified", "unclassified", "failed", "unsupported"] as const;
const COUNTER_STATUS: Record<(typeof COUNTER_KEYS)[number], string> = {
  new: "downloaded",
  duplicate: "duplicate",
  classified: "classified",
  unclassified: "unclassified",
  failed: "failed",
  unsupported: "unsupported",
};

function ActionCard({
  icon: Icon,
  title,
  hint,
  disabled,
  pending,
  onStart,
  children,
}: {
  icon: typeof Download;
  title: string;
  hint: string;
  disabled: boolean;
  pending: boolean;
  onStart: () => void;
  children?: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <Card className={cn("flex flex-col transition-opacity", disabled && !pending && "opacity-70")}>
      <CardHeader className="flex-row items-start gap-3 space-y-0">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" aria-hidden />
        </div>
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          <p className="text-sm text-muted-foreground">{hint}</p>
        </div>
      </CardHeader>
      <CardContent className="mt-auto space-y-3">
        {children}
        <Button size="lg" className="w-full" onClick={onStart} disabled={disabled}>
          {pending ? <Loader2 className="animate-spin" /> : <Play className="rtl-flip" />}
          {pending ? t("live.starting") : `${t("live.start")} · ${title}`}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function LivePull() {
  const { t, tx, fmtNumber, fmtRelative } = useI18n();
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const invalidate = useInvalidateData();
  const channels = useChannels();
  const lock = useLock();
  const status = useSystemStatus();
  const jobs = useJobs();
  const startJob = useStartJob();

  const [channel, setChannel] = useState(params.get("channel") ?? ALL);
  const [limit, setLimit] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  // Re-attach to a job started from this dashboard (e.g. after navigating away).
  const active = lock.data?.active_job ?? null;
  useEffect(() => {
    if (!jobId && active) setJobId(active.id);
  }, [active, jobId]);
  useEffect(() => {
    if (!jobId && !active && jobs.data?.[0]) setJobId(jobs.data[0].id);
  }, [jobs.data, jobId, active]);

  const stream = useJobStream(jobId, (job: Job) => {
    qc.invalidateQueries({ queryKey: qk.lock });
    qc.invalidateQueries({ queryKey: qk.jobs });
    invalidate();
    if (job.state === "succeeded") toast.success(t("live.finished"));
    else if (job.state === "locked") toast.warning(t("live.locked"));
    else toast.error(t("live.failed"));
  });

  const job = stream.job ?? jobs.data?.find((j) => j.id === jobId) ?? null;
  const running = !!job && (job.state === "running" || job.state === "queued");
  const busy = !!lock.data?.locked || running;
  const holder = lock.data?.holder;
  const telegramReady = !!status.data?.telegram_configured;

  const start = (kind: "collect" | "process") => {
    const n = Number(limit);
    startJob.mutate(
      {
        kind,
        channel: kind === "collect" && channel !== ALL ? channel : undefined,
        limit: Number.isFinite(n) && n > 0 ? n : undefined,
      },
      {
        onSuccess: (j) => {
          setJobId(j.id);
          toast.success(t("live.started"));
          if (params.has("channel")) {
            params.delete("channel");
            setParams(params, { replace: true });
          }
        },
        onError: (e) => {
          if (e instanceof ApiError && e.status === 409) toast.warning(t("live.busyTitle"));
          else toast.error(errorMessage(e));
          qc.invalidateQueries({ queryKey: qk.lock });
        },
      },
    );
  };

  const progress = job?.progress ?? {};
  const pct = progress.total ? Math.round(((progress.current ?? 0) / progress.total) * 100) : null;
  const counters = job?.counters ?? {};

  return (
    <div className="space-y-6">
      <PageHeader title={t("live.title")} description={t("live.subtitle")} />

      {busy && (
        <div role="status" className="flex items-start gap-3 rounded-lg border border-status-processing/30 bg-status-processing/5 p-4">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-status-processing" aria-hidden />
          <div className="space-y-0.5 text-sm">
            <p className="font-medium">{t("live.busyTitle")}</p>
            <p className="text-muted-foreground">
              {holder?.kind
                ? t("live.busyBy", {
                    kind: tx(`kind.${holder.kind}`),
                    trigger: tx(`trigger.${holder.trigger ?? "cli"}`),
                    when: fmtRelative(holder.started_at),
                  })
                : running && job
                  ? t("live.busyBy", { kind: tx(`kind.${job.kind}`), trigger: tx("trigger.web"), when: fmtRelative(job.created_at) })
                  : null}{" "}
              {t("live.busyHint")}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 [&>*]:min-w-0">
        <ActionCard
          icon={Download}
          title={t("live.collect")}
          hint={telegramReady ? t("live.collectHint") : t("live.telegramMissing")}
          disabled={busy || startJob.isPending || !telegramReady}
          pending={startJob.isPending && startJob.variables?.kind === "collect"}
          onStart={() => start("collect")}
        >
          <div className="grid grid-cols-[1fr_8rem] gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="live-channel">{t("live.channel")}</Label>
              <Select value={channel} onValueChange={setChannel} disabled={busy}>
                <SelectTrigger id="live-channel">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>{t("live.allChannels")}</SelectItem>
                  {channels.data
                    ?.filter((c) => c.enabled || String(c.id) === channel)
                    .map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="live-limit">{t("live.limit")}</Label>
              <Input
                id="live-limit"
                inputMode="numeric"
                placeholder={t("live.limitPlaceholder")}
                value={limit}
                onChange={(e) => setLimit(e.target.value.replace(/[^\d]/g, ""))}
                disabled={busy}
                className="tabular"
              />
            </div>
          </div>
        </ActionCard>
        <ActionCard
          icon={Workflow}
          title={t("live.process")}
          hint={t("live.processHint")}
          disabled={busy || startJob.isPending}
          pending={startJob.isPending && startJob.variables?.kind === "process"}
          onStart={() => start("process")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <LogTerminal
          lines={stream.lines}
          live={running && stream.connected}
          className="h-[480px]"
          toolbar={
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50"
              onClick={stream.clear}
              disabled={!stream.lines.length}
            >
              <Trash2 /> <span className="hidden sm:inline">{t("live.clear")}</span>
            </Button>
          }
        />
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle>{t("live.progress")}</CardTitle>
              {job && <JobStateBadge state={job.state} />}
            </CardHeader>
            <CardContent className="space-y-3">
              <Progress
                value={pct ?? (job && !running ? 100 : 0)}
                indeterminate={running && pct === null}
                aria-label={t("live.progress")}
              />
              <div className="flex items-center justify-between text-xs text-muted-foreground tabular">
                <span className="truncate">
                  {job ? `${tx(`kind.${job.kind}`)}${progress.channel ? ` · ${progress.channel}` : ""}` : "—"}
                </span>
                <span>
                  {progress.current !== undefined
                    ? `${fmtNumber(progress.current)}${progress.total ? ` / ${fmtNumber(progress.total)}` : ""}`
                    : pct !== null
                      ? `${pct}%`
                      : ""}
                </span>
              </div>
              {job?.run_id && (
                <Button asChild variant="outline" size="sm" className="w-full">
                  <Link to={`/runs/${job.run_id}`}>
                    <ExternalLink /> {t("live.viewRun", { id: job.run_id })}
                  </Link>
                </Button>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>{t("live.counters")}</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-2">
                {COUNTER_KEYS.map((k) => (
                  <div key={k} className="rounded-md border px-3 py-2">
                    <dt className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: `hsl(var(--status-${COUNTER_STATUS[k]}))` }} aria-hidden />
                      {tx(`counters.${k}`)}
                    </dt>
                    <dd className="text-lg font-semibold tabular transition-all duration-150">{fmtNumber(counters[k] ?? 0)}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
          {jobs.data && jobs.data.length > 1 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">{t("live.recentJobs")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 px-2 sm:px-2">
                {jobs.data.slice(0, 5).map((j) => (
                  <button
                    key={j.id}
                    type="button"
                    onClick={() => setJobId(j.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-start text-xs transition-colors hover:bg-muted",
                      j.id === jobId && "bg-muted",
                    )}
                  >
                    <span className="truncate">
                      {tx(`kind.${j.kind}`)} · {fmtRelative(j.created_at)}
                    </span>
                    <JobStateBadge state={j.state} />
                  </button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
