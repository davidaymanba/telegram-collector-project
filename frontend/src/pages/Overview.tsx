import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  CircleAlert,
  CircleX,
  Database,
  FileText,
  History,
  Inbox,
  Minus,
  Plus,
  Sparkles,
} from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { cn, sum } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import { errorMessage, useHealth, useInvalidateData, useOverview } from "@/hooks/queries";
import type { HealthCheck, Kpi, Overview as OverviewData } from "@/lib/types";
import { TYPE_COLOR } from "@/lib/content-types";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/States";
import { FileStatusBadge, RunStatusBadge, statusColor } from "@/components/StatusBadge";
import { Sparkline } from "@/components/Sparkline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const KPI_STATUS: Record<Kpi["key"], string> = {
  total: "",
  classified: "classified",
  unclassified: "unclassified",
  duplicate: "duplicate",
  failed: "failed",
};


/* ------------------------------------------------------------------ KPI */
function KpiCard({ kpi }: { kpi: Kpi }) {
  const { t, tx, fmtNumber } = useI18n();
  const status = KPI_STATUS[kpi.key];
  const color = status ? statusColor(status) : "hsl(var(--primary))";
  // For "failed"/"duplicate"/"unclassified" going up is bad news.
  const upIsGood = kpi.key === "total" || kpi.key === "classified";
  const change = kpi.change_pct;
  const good = change === null || change === 0 ? null : change > 0 === upIsGood;
  const TrendIcon = change === null || change === 0 ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <Card className="flex min-w-0 flex-col justify-between p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        {status && <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} aria-hidden />}
        {tx(`overview.kpi.${kpi.key}`)}
      </div>
      <div className="mt-3 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-2xl font-semibold tracking-tight tabular">{fmtNumber(kpi.value)}</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground" title={`${t("overview.last7", { n: fmtNumber(kpi.last_7d) })} · ${t("overview.vsLastWeek")}`}>
            <span
              className={cn(
                "inline-flex items-center gap-0.5 font-medium tabular",
                good === true && "text-status-classified",
                good === false && "text-status-failed",
              )}
            >
              <TrendIcon className="h-3 w-3" aria-hidden />
              {change === null ? "—" : `${change > 0 ? "+" : ""}${fmtNumber(change, { maximumFractionDigits: 1 })}%`}
            </span>
            <span className="whitespace-nowrap">{t("overview.vs7d")}</span>
          </p>
        </div>
        <div dir="ltr" className="shrink-0">
          <Sparkline data={kpi.sparkline} color={color} width={72} label={tx(`overview.kpi.${kpi.key}`)} />
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ charts */
function ChartTooltip({ active, payload, label, render }: { active?: boolean; payload?: { value: number; payload: Record<string, unknown> }[]; label?: string; render: (p: Record<string, unknown>, label?: string) => React.ReactNode }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      {render(payload[0].payload, label)}
    </div>
  );
}

function DailyChart({ data }: { data: OverviewData["daily"] }) {
  const { t, fmtDate, fmtNumber } = useI18n();
  const total = sum(data.map((d) => d.total));
  return (
    <Card className="lg:col-span-2">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle>{t("overview.daily")}</CardTitle>
          <CardDescription>{t("overview.dailyHint")}</CardDescription>
        </div>
        <p className="text-lg font-semibold tabular">{fmtNumber(total)}</p>
      </CardHeader>
      <CardContent>
        <div dir="ltr" className="h-64" role="img" aria-label={t("overview.daily")}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 4, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="dailyFill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="0" />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                minTickGap={28}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickFormatter={(d: string) => fmtDate(d, { month: "short", day: "numeric" })}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={40}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              />
              <Tooltip
                cursor={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 1, strokeDasharray: "3 3" }}
                content={
                  <ChartTooltip
                    render={(p) => (
                      <div className="space-y-1">
                        <p className="font-medium">{fmtDate(String(p.date), { weekday: "short", month: "short", day: "numeric" })}</p>
                        <p className="tabular">
                          <span className="text-muted-foreground">{t("overview.kpi.total")}: </span>
                          <span className="font-semibold">{fmtNumber(Number(p.total))}</span>
                        </p>
                        <p className="tabular text-muted-foreground">
                          {t("status.classified")}: {fmtNumber(Number(p.classified))} · {t("status.duplicate")}: {fmtNumber(Number(p.duplicate))}
                        </p>
                      </div>
                    )}
                  />
                }
              />
              <Area
                type="monotone"
                dataKey="total"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                fill="url(#dailyFill)"
                activeDot={{ r: 4, strokeWidth: 2, stroke: "hsl(var(--card))" }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function TypeDonut({ data }: { data: OverviewData["by_content_type"] }) {
  const { t, tx, fmtNumber, fmtPercent } = useI18n();
  const total = sum(data.map((d) => d.count));
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("overview.byType")}</CardTitle>
      </CardHeader>
      <CardContent>
        {total === 0 ? (
          <EmptyState compact icon={Sparkles} title={t("overview.noData")} />
        ) : (
          <div className="flex flex-col items-center gap-5 sm:flex-row lg:flex-col">
            <div dir="ltr" className="relative h-40 w-40 shrink-0" role="img" aria-label={t("overview.byType")}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data}
                    dataKey="count"
                    nameKey="content_type"
                    innerRadius="64%"
                    outerRadius="100%"
                    stroke="hsl(var(--card))"
                    strokeWidth={2}
                    isAnimationActive={false}
                  >
                    {data.map((d) => (
                      <Cell key={d.content_type} fill={TYPE_COLOR[d.content_type]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={
                      <ChartTooltip
                        render={(p) => (
                          <span className="tabular">
                            {tx(`contentType.${String(p.content_type)}`)}: <b>{fmtNumber(Number(p.count))}</b>
                          </span>
                        )}
                      />
                    }
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-semibold tabular">{fmtNumber(total)}</span>
                <span className="text-[11px] text-muted-foreground">{t("status.classified")}</span>
              </div>
            </div>
            {/* Legend doubles as the table view: every slice labelled with count and share. */}
            <ul className="w-full space-y-1.5 text-sm">
              {data.map((d) => (
                <li key={d.content_type} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: TYPE_COLOR[d.content_type] }} aria-hidden />
                  <span className="truncate">{tx(`contentType.${d.content_type}`)}</span>
                  <span className="ms-auto font-medium tabular">{fmtNumber(d.count)}</span>
                  <span className="w-10 text-end text-xs text-muted-foreground tabular">{fmtPercent(total ? d.count / total : 0)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SubjectBars({ data }: { data: OverviewData["by_subject"] }) {
  const { t, lang, fmtNumber } = useI18n();
  const rows = data.filter((d) => d.count > 0).slice(0, 8);
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>{t("overview.bySubject")}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState compact icon={BookOpen} title={t("overview.noData")} />
        ) : (
          <div dir="ltr" style={{ height: Math.max(120, rows.length * 36) }} role="img" aria-label={t("overview.bySubject")}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 36, left: 0, bottom: 0 }} barCategoryGap={8}>
                <XAxis type="number" hide allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="code"
                  width={78}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))", fontFamily: "var(--font-mono)" }}
                />
                <Tooltip
                  cursor={{ fill: "hsl(var(--muted))" }}
                  content={
                    <ChartTooltip
                      render={(p) => (
                        <div>
                          <p className="font-medium">{String(lang === "ar" ? p.name_ar : p.name_en)}</p>
                          <p className="tabular text-muted-foreground">
                            <b className="text-foreground">{fmtNumber(Number(p.count))}</b> · {String(p.code)}
                          </p>
                        </div>
                      )}
                    />
                  }
                />
                <Bar
                  dataKey="count"
                  fill="hsl(var(--primary))"
                  radius={[0, 4, 4, 0]}
                  maxBarSize={18}
                  isAnimationActive={false}
                  label={{ position: "right", fontSize: 11, fill: "hsl(var(--muted-foreground))", formatter: (v: number) => fmtNumber(v) }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ side cards */
function EmptySubjects({ items }: { items: OverviewData["empty_subjects"] }) {
  const { t, lang } = useI18n();
  return (
    <Card className={cn(items.length > 0 && "border-status-unclassified/40")}>
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        {items.length > 0 ? (
          <AlertTriangle className="h-4 w-4 text-status-unclassified" aria-hidden />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-status-classified" aria-hidden />
        )}
        <CardTitle>{t("overview.emptySubjects")}</CardTitle>
        <span className="ms-auto rounded bg-muted px-1.5 text-xs font-medium tabular">{items.length}</span>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("overview.allCovered")}</p>
        ) : (
          <>
            <p className="mb-3 text-xs text-muted-foreground">{t("overview.emptySubjectsHint")}</p>
            <ul className="space-y-1.5">
              {items.map((s) => (
                <li key={s.code} className="flex items-center gap-2 text-sm">
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">{s.code}</code>
                  <span className="truncate">{lang === "ar" ? s.name_ar : s.name_en}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function RecentFiles({ files }: { files: OverviewData["recent_files"] }) {
  const { t, tx, fmtRelative } = useI18n();
  const navigate = useNavigate();
  return (
    <Card className="lg:col-span-2">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>{t("overview.recentFiles")}</CardTitle>
        <Button asChild variant="ghost" size="sm" className="-me-2 text-muted-foreground">
          <Link to="/files">
            {t("overview.viewAll")} <ArrowRight className="rtl-flip" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="px-0 sm:px-0">
        {files.length === 0 ? (
          <EmptyState compact icon={Inbox} title={t("overview.noData")} />
        ) : (
          <ul className="divide-y">
            {files.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/files?file=${f.id}`)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-start transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none sm:px-5"
                >
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{f.original_filename}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {f.message.channel.name}
                      {f.classification?.subject_code && ` · ${f.classification.subject_code}`}
                      {f.classification?.content_type && ` · ${tx(`contentType.${f.classification.content_type}`)}`}
                    </span>
                  </span>
                  <span className="hidden text-xs text-muted-foreground sm:block">{fmtRelative(f.created_at)}</span>
                  <FileStatusBadge status={f.status} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function LastRun({ run, pending }: { run: OverviewData["last_run"]; pending: number }) {
  const { t, tx, fmtNumber, fmtRelative, fmtDuration } = useI18n();
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>{t("overview.lastRun")}</CardTitle>
        {run && <RunStatusBadge status={run.status} />}
      </CardHeader>
      <CardContent>
        {!run ? (
          <EmptyState compact icon={History} title={t("overview.noRuns")} />
        ) : (
          <div className="space-y-3">
            <Link to={`/runs/${run.id}`} className="block rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <p className="text-sm font-medium">
                {tx(`kind.${run.kind}`)} <span className="text-muted-foreground tabular">#{run.id}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                {tx(`trigger.${run.trigger}`)} · {fmtRelative(run.started_at)} · {fmtDuration(run.duration_seconds)}
              </p>
            </Link>
            <dl className="grid grid-cols-3 gap-2 text-center">
              {(["new", "classified", "failed"] as const).map((k) => (
                <div key={k} className="rounded-md bg-muted/50 py-2">
                  <dt className="text-[11px] text-muted-foreground">{tx(`counters.${k}`)}</dt>
                  <dd className="text-sm font-semibold tabular">{fmtNumber(run[`${k}_count`])}</dd>
                </div>
              ))}
            </dl>
            {pending > 0 && (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-1.5 w-1.5 animate-soft-pulse rounded-full bg-status-processing" aria-hidden />
                {t("overview.pending", { n: fmtNumber(pending) })}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const CHECK_ICON = { ok: CheckCircle2, warn: CircleAlert, fail: CircleX } as const;
const CHECK_STATUS = { ok: "classified", warn: "unclassified", fail: "failed" } as const;

function HealthCard() {
  const { t, tx, fmtBytes } = useI18n();
  const { data, isPending, isError, error, refetch } = useHealth();
  const detail = (c: HealthCheck) => {
    if (c.key === "storage" && typeof c.data.free === "number") return `${fmtBytes(c.data.free)} free`;
    return c.detail;
  };
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <Database className="h-4 w-4 text-muted-foreground" aria-hidden />
        <CardTitle>{t("overview.health")}</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="space-y-2.5">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-5" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState compact error={error} onRetry={() => refetch()} />
        ) : (
          <ul className="space-y-2">
            {data.checks.map((c) => {
              const Icon = CHECK_ICON[c.status];
              return (
                <li key={c.key} className="flex items-start gap-2 text-sm">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: statusColor(CHECK_STATUS[c.status]) }} aria-label={c.status} />
                  <div className="min-w-0">
                    <p className="font-medium leading-5">{tx(`overview.checks.${c.key}`)}</p>
                    <p className="truncate text-xs text-muted-foreground" title={c.detail} dir="auto">
                      {detail(c)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ page */
function OverviewSkeleton() {
  return (
    <div className="space-y-4" aria-busy>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-[108px]" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Skeleton className="h-80 lg:col-span-2" />
        <Skeleton className="h-80" />
      </div>
    </div>
  );
}

export default function Overview() {
  const { t } = useI18n();
  const { data, isPending, isError, error, refetch } = useOverview();
  const invalidate = useInvalidateData();
  const seed = useMutation({
    mutationFn: () => api.post<{ files?: number; skipped?: number }>("/settings/seed-demo"),
    onSuccess: async (r) => {
      toast.success(r.skipped ? t("settings.seedSkipped") : t("settings.seeded", { files: r.files ?? 0 }));
      await invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t("overview.title")} description={t("overview.subtitle")} />
      {isPending ? (
        <OverviewSkeleton />
      ) : isError ? (
        <Card>
          <ErrorState error={error} onRetry={() => refetch()} />
        </Card>
      ) : (
        <>
          {data.kpis[0]?.value === 0 && (
            <Card className="border-dashed">
              <EmptyState
                icon={Inbox}
                title={t("overview.empty")}
                description={t("overview.emptyHint")}
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button asChild>
                      <Link to="/channels?new=1">
                        <Plus /> {t("overview.goChannels")}
                      </Link>
                    </Button>
                    <Button variant="outline" onClick={() => seed.mutate()} disabled={seed.isPending}>
                      <Sparkles /> {t("overview.seedDemo")}
                    </Button>
                  </div>
                }
              />
            </Card>
          )}
          <section aria-label={t("overview.title")} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {data.kpis.map((k) => (
              <KpiCard key={k.key} kpi={k} />
            ))}
          </section>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 [&>*]:min-w-0">
            <DailyChart data={data.daily} />
            <TypeDonut data={data.by_content_type} />
            <SubjectBars data={data.by_subject} />
            <EmptySubjects items={data.empty_subjects} />
            <RecentFiles files={data.recent_files} />
            <div className="space-y-4">
              <LastRun run={data.last_run} pending={data.pending} />
              <HealthCard />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
