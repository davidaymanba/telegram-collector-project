import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { History } from "lucide-react";
import { useI18n } from "@/i18n";
import type { Run } from "@/lib/types";
import { useRuns } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Pagination } from "@/components/Pagination";
import { EmptyState, ErrorState } from "@/components/States";
import { RunStatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SimpleTooltip } from "@/components/ui/tooltip";

const ANY = "__any__";

export function RunCounters({ run }: { run: Run }) {
  const { tx, fmtNumber } = useI18n();
  const items = [
    ["new", run.new_count, "downloaded"],
    ["duplicate", run.duplicate_count, "duplicate"],
    ["classified", run.classified_count, "classified"],
    ["unclassified", run.unclassified_count, "unclassified"],
    ["failed", run.failed_count, "failed"],
    ["unsupported", run.unsupported_count, "unsupported"],
  ] as const;
  const shown = items.filter(([, n]) => n > 0);
  if (!shown.length) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {shown.map(([key, n, status]) => (
        <SimpleTooltip key={key} content={tx(`counters.${key}`)}>
          <span className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] tabular">
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: `hsl(var(--status-${status}))` }} aria-hidden />
            <span className="sr-only">{tx(`counters.${key}`)}</span>
            {fmtNumber(n)}
          </span>
        </SimpleTooltip>
      ))}
    </div>
  );
}

export default function Runs() {
  const { t, tx, fmtDateTime, fmtRelative, fmtDuration } = useI18n();
  const navigate = useNavigate();
  const [kind, setKind] = useState(ANY);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const { data, isPending, isFetching, isError, error, refetch } = useRuns({ kind: kind === ANY ? undefined : kind, page, page_size: pageSize });

  const columns: ColumnDef<Run, unknown>[] = [
    { id: "id", header: t("runs.run"), meta: { className: "font-mono text-xs tabular" }, cell: ({ row: { original: r } }) => `#${r.id}` },
    { id: "kind", header: t("runs.kind"), cell: ({ row: { original: r } }) => <span className="font-medium">{tx(`kind.${r.kind}`)}</span> },
    { id: "trigger", header: t("runs.trigger"), meta: { className: "text-muted-foreground" }, cell: ({ row: { original: r } }) => tx(`trigger.${r.trigger}`) },
    { id: "status", header: t("runs.status"), cell: ({ row: { original: r } }) => <RunStatusBadge status={r.status} /> },
    {
      id: "started",
      header: t("runs.started"),
      meta: { className: "whitespace-nowrap text-muted-foreground" },
      cell: ({ row: { original: r } }) => (
        <SimpleTooltip content={fmtDateTime(r.started_at)}>
          <span>{fmtRelative(r.started_at)}</span>
        </SimpleTooltip>
      ),
    },
    { id: "duration", header: t("runs.duration"), meta: { className: "text-muted-foreground tabular" }, cell: ({ row: { original: r } }) => fmtDuration(r.duration_seconds) },
    { id: "counters", header: t("runs.counters"), cell: ({ row: { original: r } }) => <RunCounters run={r} /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("runs.title")}
        description={t("runs.subtitle")}
        actions={
          <Select value={kind} onValueChange={(v) => { setKind(v); setPage(1); }}>
            <SelectTrigger className="h-9 w-40" aria-label={t("runs.kind")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>{t("runs.anyKind")}</SelectItem>
              <SelectItem value="collect">{tx("kind.collect")}</SelectItem>
              <SelectItem value="process">{tx("kind.process")}</SelectItem>
            </SelectContent>
          </Select>
        }
      />
      <Card className="overflow-hidden">
        {isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : (
          <>
            <DataTable
              columns={columns}
              data={data?.items ?? []}
              loading={isPending || (isFetching && !data)}
              getRowId={(r) => String(r.id)}
              onRowClick={(r) => navigate(`/runs/${r.id}`)}
              rowLabel={(r) => `${tx(`kind.${r.kind}`)} #${r.id}`}
              empty={<EmptyState icon={History} title={t("runs.empty")} description={t("runs.emptyHint")} />}
              renderCard={(r) => (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">
                      {tx(`kind.${r.kind}`)} <span className="font-mono text-xs text-muted-foreground">#{r.id}</span>
                    </span>
                    <RunStatusBadge status={r.status} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {tx(`trigger.${r.trigger}`)} · {fmtRelative(r.started_at)} · {fmtDuration(r.duration_seconds)}
                  </p>
                  <RunCounters run={r} />
                </div>
              )}
            />
            {data && data.total > 0 && (
              <div className="border-t px-3">
                <Pagination page={page} pages={data.pages} total={data.total} pageSize={pageSize} onPage={setPage} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
