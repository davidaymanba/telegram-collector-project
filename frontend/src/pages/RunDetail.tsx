import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, History } from "lucide-react";
import { useI18n } from "@/i18n";
import { ApiError } from "@/lib/api";
import { useRun } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/States";
import { RunStatusBadge, statusColor } from "@/components/StatusBadge";
import { LogTerminal } from "@/components/LogTerminal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const COUNTERS = [
  ["new", "downloaded"],
  ["duplicate", "duplicate"],
  ["classified", "classified"],
  ["unclassified", "unclassified"],
  ["failed", "failed"],
  ["unsupported", "unsupported"],
] as const;

export default function RunDetail() {
  const { id } = useParams();
  const runId = Number(id);
  const { t, tx, fmtNumber, fmtDateTime, fmtDuration } = useI18n();
  const { data, isPending, isError, error, refetch } = useRun(runId);

  const back = (
    <Button asChild variant="outline" size="sm">
      <Link to="/runs">
        <ArrowLeft className="rtl-flip" /> {t("runs.back")}
      </Link>
    </Button>
  );

  if (isPending)
    return (
      <div className="space-y-6" aria-busy>
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  if (isError)
    return error instanceof ApiError && error.status === 404 ? (
      <EmptyState icon={History} title={t("runs.notFound")} action={back} />
    ) : (
      <ErrorState error={error} onRetry={() => refetch()} />
    );

  const errors = data.log_lines.filter((l) => l.level === "error" || l.level === "critical");
  const failedLogs = data.logs.filter((l) => l.status === "failed");
  const meta = Object.entries(data.metadata_json).filter(([, v]) => v !== null && v !== undefined);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${tx(`kind.${data.kind}`)} · ${t("runs.detailTitle", { id: data.id })}`}
        description={`${tx(`trigger.${data.trigger}`)} · ${fmtDateTime(data.started_at)} · ${fmtDuration(data.duration_seconds)}`}
        actions={
          <>
            <RunStatusBadge status={data.status} />
            {back}
          </>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {COUNTERS.map(([key, status]) => (
          <Card key={key} className="p-3">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: statusColor(status) }} aria-hidden />
              {tx(`counters.${key}`)}
            </p>
            <p className="mt-1 text-xl font-semibold tabular">{fmtNumber(data[`${key}_count`])}</p>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="logs">
        <TabsList>
          <TabsTrigger value="logs">{t("runs.logs")}</TabsTrigger>
          <TabsTrigger value="errors">
            {t("runs.errors")}
            {errors.length + failedLogs.length > 0 && (
              <span className="rounded bg-destructive/10 px-1 text-[10px] font-semibold text-destructive tabular">{errors.length + failedLogs.length}</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="events">{t("runs.fileEvents")}</TabsTrigger>
        </TabsList>
        <TabsContent value="logs">
          <LogTerminal lines={data.log_lines} className="h-[520px]" emptyText={t("runs.noLogs")} live={data.status === "running"} />
        </TabsContent>
        <TabsContent value="errors">
          <Card>
            <CardContent className="space-y-3 p-4 sm:p-5">
              {errors.length + failedLogs.length === 0 ? (
                <EmptyState compact icon={CheckCircle2} title={t("runs.noErrors")} />
              ) : (
                <>
                  {failedLogs.map((l) => (
                    <div key={`db-${l.id}`} className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
                      <p className="text-sm font-medium">
                        {l.stage}
                        {l.file_id && (
                          <Link to={`/files?file=${l.file_id}`} className="ms-2 font-mono text-xs text-primary hover:underline">#{l.file_id}</Link>
                        )}
                      </p>
                      <pre dir="ltr" className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-destructive">{l.error_message}</pre>
                    </div>
                  ))}
                  {errors.map((l) => (
                    <div key={`log-${l.seq}`} className="rounded-md border p-3">
                      <p className="font-mono text-xs font-medium text-destructive" dir="ltr">{l.event}</p>
                      <pre dir="ltr" className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-muted-foreground">{JSON.stringify(l.fields, null, 2)}</pre>
                    </div>
                  ))}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="events">
          <Card>
            <CardContent className="p-0">
              {data.logs.length === 0 ? (
                <EmptyState compact icon={History} title={t("files.detail.noLogs")} />
              ) : (
                <ul className="divide-y">
                  {data.logs.map((l) => (
                    <li key={l.id} className="flex items-center gap-3 px-4 py-2 text-sm">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: statusColor(l.status === "success" ? "classified" : l.status === "failed" ? "failed" : "duplicate") }} aria-label={l.status} />
                      <span className="w-20 shrink-0 font-medium">{l.stage}</span>
                      {l.file_id && <Link to={`/files?file=${l.file_id}`} className="font-mono text-xs text-primary hover:underline">#{l.file_id}</Link>}
                      <span className="min-w-0 truncate text-xs text-muted-foreground" dir="auto">{l.message ?? l.error_message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {meta.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t("runs.metadata")}</CardTitle>
          </CardHeader>
          <CardContent>
            <pre dir="ltr" className="overflow-auto rounded-md bg-muted/40 p-3 font-mono text-xs">{JSON.stringify(Object.fromEntries(meta), null, 2)}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
