import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { FileText, FilterX, Search } from "lucide-react";
import { useI18n } from "@/i18n";
import { CONTENT_TYPES, FILE_STATUSES, type FileItem } from "@/lib/types";
import { useDebounce } from "@/hooks/use-debounce";
import { useFacets, useFiles, type FileParams } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Pagination } from "@/components/Pagination";
import { EmptyState, ErrorState } from "@/components/States";
import { FileStatusBadge, StatusDot } from "@/components/StatusBadge";
import { FileDetailSheet } from "@/components/FileDetailSheet";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SimpleTooltip } from "@/components/ui/tooltip";

const ANY = "__any__";
const FILTER_KEYS = ["q", "status", "subject", "content_type", "extension", "date_from", "date_to"] as const;

function FilterSelect({ value, onChange, placeholder, label, children }: { value: string; onChange: (v: string) => void; placeholder: string; label: string; children: React.ReactNode }) {
  return (
    <Select value={value || ANY} onValueChange={(v) => onChange(v === ANY ? "" : v)}>
      <SelectTrigger className="h-8 w-full text-xs sm:w-auto sm:min-w-[9rem]" aria-label={label}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ANY}>{placeholder}</SelectItem>
        {children}
      </SelectContent>
    </Select>
  );
}

export default function Files() {
  const { t, tx, fmtBytes, fmtRelative, fmtDateTime, fmtNumber } = useI18n();
  const [params, setParams] = useSearchParams();
  const facets = useFacets();

  const get = (k: string) => params.get(k) ?? "";
  const [search, setSearch] = useState(get("q"));
  const debounced = useDebounce(search, 300);

  const update = (patch: Record<string, string | number | null>, resetPage = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, String(v));
    }
    if (resetPage) next.delete("page");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (debounced !== get("q")) update({ q: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const page = Number(get("page") || 1);
  const pageSize = Number(get("page_size") || 25);
  const sort = get("sort") || "created_at";
  const order = (get("order") || "desc") as "asc" | "desc";
  const fileId = params.get("file") ? Number(params.get("file")) : null;

  const query: FileParams = useMemo(
    () => ({
      q: get("q") || undefined,
      status: get("status") || undefined,
      subject: get("subject") || undefined,
      content_type: get("content_type") || undefined,
      extension: get("extension") || undefined,
      date_from: get("date_from") ? `${get("date_from")}T00:00:00Z` : undefined,
      date_to: get("date_to") ? `${get("date_to")}T23:59:59Z` : undefined,
      sort,
      order,
      page,
      page_size: pageSize,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [params],
  );
  const { data, isPending, isFetching, isError, error, refetch } = useFiles(query);
  const hasFilters = FILTER_KEYS.some((k) => params.get(k));
  const sorting: SortingState = [{ id: sort, desc: order === "desc" }];

  const columns: ColumnDef<FileItem, unknown>[] = [
    {
      id: "original_filename",
      header: t("files.name"),
      enableSorting: true,
      cell: ({ row: { original: f } }) => (
        <div className="flex min-w-0 max-w-[26rem] items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-muted/40 font-mono text-[10px] font-medium uppercase text-muted-foreground">
            {f.extension.slice(0, 4) || "?"}
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium" dir="auto" title={f.original_filename}>{f.original_filename}</p>
            <p className="truncate text-xs text-muted-foreground">{f.message.channel.name}</p>
          </div>
        </div>
      ),
    },
    { id: "status", header: t("files.status"), enableSorting: true, cell: ({ row: { original: f } }) => <FileStatusBadge status={f.status} /> },
    {
      id: "subject",
      header: t("files.subject"),
      enableSorting: false,
      cell: ({ row: { original: f } }) =>
        f.classification?.subject_code ? (
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">{f.classification.subject_code}</code>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "type",
      header: t("files.type"),
      enableSorting: false,
      cell: ({ row: { original: f } }) =>
        f.classification?.content_type ? tx(`contentType.${f.classification.content_type}`) : <span className="text-muted-foreground">—</span>,
    },
    {
      id: "size_bytes",
      header: t("files.size"),
      enableSorting: true,
      meta: { className: "whitespace-nowrap text-muted-foreground tabular" },
      cell: ({ row: { original: f } }) => fmtBytes(f.size_bytes),
    },
    {
      id: "created_at",
      header: t("files.collected"),
      enableSorting: true,
      meta: { className: "whitespace-nowrap text-muted-foreground" },
      cell: ({ row: { original: f } }) => (
        <SimpleTooltip content={fmtDateTime(f.created_at)}>
          <span>{fmtRelative(f.created_at)}</span>
        </SimpleTooltip>
      ),
    },
  ];

  const counts = facets.data?.status_counts ?? {};

  return (
    <div className="space-y-6">
      <PageHeader title={t("files.title")} description={t("files.subtitle")} />

      <Card className="overflow-hidden">
        {/* Filters: one row above the table */}
        <div className="flex flex-col gap-2 border-b p-3 lg:flex-row lg:flex-wrap lg:items-center">
          <div className="relative lg:w-72">
            <Search className="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("files.searchPlaceholder")}
              aria-label={t("common.search")}
              className="h-8 ps-8 text-sm"
              type="search"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <FilterSelect value={get("status")} onChange={(v) => update({ status: v })} placeholder={t("files.anyStatus")} label={t("files.status")}>
              {FILE_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  <span className="flex items-center gap-2">
                    <StatusDot status={s} /> {tx(`status.${s}`)}
                    {counts[s] ? <span className="text-muted-foreground tabular">({fmtNumber(counts[s] ?? 0)})</span> : null}
                  </span>
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect value={get("subject")} onChange={(v) => update({ subject: v })} placeholder={t("files.anySubject")} label={t("files.subject")}>
              {facets.data?.subjects.map((s) => (
                <SelectItem key={s} value={s}>
                  <span className="font-mono text-xs">{s}</span>
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect value={get("content_type")} onChange={(v) => update({ content_type: v })} placeholder={t("files.anyType")} label={t("files.type")}>
              {CONTENT_TYPES.map((c) => (
                <SelectItem key={c} value={c}>
                  {tx(`contentType.${c}`)}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect value={get("extension")} onChange={(v) => update({ extension: v })} placeholder={t("files.anyExtension")} label={t("files.extension")}>
              {facets.data?.extensions.map((e) => (
                <SelectItem key={e} value={e}>
                  <span className="font-mono text-xs uppercase">{e}</span>
                </SelectItem>
              ))}
            </FilterSelect>
          </div>
          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="f-from">{t("files.from")}</label>
            <Input id="f-from" type="date" value={get("date_from")} onChange={(e) => update({ date_from: e.target.value })} className="h-8 w-full text-xs sm:w-[9.5rem]" aria-label={t("files.from")} />
            <span className="text-xs text-muted-foreground">–</span>
            <label className="sr-only" htmlFor="f-to">{t("files.to")}</label>
            <Input id="f-to" type="date" value={get("date_to")} onChange={(e) => update({ date_to: e.target.value })} className="h-8 w-full text-xs sm:w-[9.5rem]" aria-label={t("files.to")} />
          </div>
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground lg:ms-auto"
              onClick={() => {
                setSearch("");
                update(Object.fromEntries(FILTER_KEYS.map((k) => [k, null])));
              }}
            >
              <FilterX /> {t("common.clearFilters")}
            </Button>
          )}
        </div>

        {isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : (
          <>
            <DataTable
              columns={columns}
              data={data?.items ?? []}
              loading={isPending || isFetching}
              sorting={sorting}
              onSortingChange={(s) => {
                const first = s[0];
                update({ sort: first?.id ?? null, order: first ? (first.desc ? "desc" : "asc") : null }, false);
              }}
              getRowId={(f) => String(f.id)}
              onRowClick={(f) => update({ file: f.id }, false)}
              rowLabel={(f) => f.original_filename}
              empty={
                hasFilters ? (
                  <EmptyState
                    icon={FilterX}
                    title={t("files.empty")}
                    description={t("files.emptyHint")}
                    action={
                      <Button variant="outline" onClick={() => { setSearch(""); update(Object.fromEntries(FILTER_KEYS.map((k) => [k, null]))); }}>
                        {t("common.clearFilters")}
                      </Button>
                    }
                  />
                ) : (
                  <EmptyState
                    icon={FileText}
                    title={t("files.emptyAll")}
                    description={t("overview.emptyHint")}
                    action={
                      <Button asChild>
                        <Link to="/live">{t("files.goLive")}</Link>
                      </Button>
                    }
                  />
                )
              }
              renderCard={(f) => (
                <div className="space-y-1.5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 truncate text-sm font-medium" dir="auto">{f.original_filename}</p>
                    <FileStatusBadge status={f.status} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {f.message.channel.name}
                    {f.classification?.subject_code && ` · ${f.classification.subject_code}`}
                    {f.classification?.content_type && ` · ${tx(`contentType.${f.classification.content_type}`)}`}
                    {` · ${fmtBytes(f.size_bytes)} · ${fmtRelative(f.created_at)}`}
                  </p>
                </div>
              )}
            />
            {data && data.total > 0 && (
              <div className="border-t px-3">
                <Pagination
                  page={page}
                  pages={data.pages}
                  total={data.total}
                  pageSize={pageSize}
                  onPage={(p) => update({ page: p }, false)}
                  onPageSize={(n) => update({ page_size: n })}
                />
              </div>
            )}
          </>
        )}
      </Card>

      <FileDetailSheet fileId={fileId} onClose={() => update({ file: null }, false)} />
    </div>
  );
}
