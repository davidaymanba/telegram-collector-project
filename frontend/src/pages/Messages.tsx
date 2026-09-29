import { useState } from "react";
import { Link } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { File, Image, MessagesSquare, Search, Type } from "lucide-react";
import { useI18n } from "@/i18n";
import type { MessageItem } from "@/lib/types";
import { useDebounce } from "@/hooks/use-debounce";
import { useChannels, useMessages } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Pagination } from "@/components/Pagination";
import { EmptyState, ErrorState } from "@/components/States";
import { FileStatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SimpleTooltip } from "@/components/ui/tooltip";

const ANY = "__any__";
const MEDIA_ICON: Record<string, typeof File> = { document: File, photo: Image, none: Type };

export default function Messages() {
  const { t, fmtDateTime, fmtRelative, fmtBytes } = useI18n();
  const channels = useChannels();
  const [search, setSearch] = useState("");
  const q = useDebounce(search, 300);
  const [channelId, setChannelId] = useState<string>(ANY);
  const [media, setMedia] = useState<string>(ANY);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const { data, isPending, isFetching, isError, error, refetch } = useMessages({
    q: q || undefined,
    channel_id: channelId === ANY ? undefined : Number(channelId),
    media_type: media === ANY ? undefined : media,
    page,
    page_size: pageSize,
  });

  const columns: ColumnDef<MessageItem, unknown>[] = [
    {
      id: "date",
      header: t("messages.date"),
      meta: { className: "whitespace-nowrap text-muted-foreground" },
      cell: ({ row: { original: m } }) => (
        <SimpleTooltip content={fmtDateTime(m.message_date)}>
          <span>{fmtRelative(m.message_date)}</span>
        </SimpleTooltip>
      ),
    },
    {
      id: "channel",
      header: t("messages.channel"),
      cell: ({ row: { original: m } }) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{m.channel.name}</p>
          <p className="font-mono text-[11px] text-muted-foreground tabular" dir="ltr">#{m.telegram_message_id}</p>
        </div>
      ),
    },
    {
      id: "caption",
      header: t("messages.caption"),
      cell: ({ row: { original: m } }) => (
        <p className="line-clamp-2 max-w-md text-sm" dir="auto">
          {m.caption || <span className="text-muted-foreground">—</span>}
        </p>
      ),
    },
    {
      id: "media",
      header: t("messages.media"),
      cell: ({ row: { original: m } }) => {
        const Icon = MEDIA_ICON[m.media_type] ?? File;
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Icon className="h-3.5 w-3.5" aria-hidden /> {m.media_type}
            {m.file_size ? ` · ${fmtBytes(m.file_size)}` : ""}
          </span>
        );
      },
    },
    {
      id: "file",
      header: t("messages.file"),
      cell: ({ row: { original: m } }) =>
        m.file_id ? (
          <Link to={`/files?file=${m.file_id}`} className="group inline-flex max-w-[16rem] items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <span className="truncate text-sm text-primary group-hover:underline" dir="auto">{m.file_name ?? `#${m.file_id}`}</span>
            {m.file_status && <FileStatusBadge status={m.file_status} />}
          </Link>
        ) : (
          <span className="text-muted-foreground">{t("messages.noFile")}</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("messages.title")} description={t("messages.subtitle")} />
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-2 border-b p-3 sm:flex-row sm:items-center">
          <div className="relative sm:w-72">
            <Search className="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={t("messages.searchPlaceholder")}
              aria-label={t("common.search")}
              className="h-8 ps-8"
            />
          </div>
          <Select value={channelId} onValueChange={(v) => { setChannelId(v); setPage(1); }}>
            <SelectTrigger className="h-8 text-xs sm:w-48" aria-label={t("messages.channel")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>{t("messages.anyChannel")}</SelectItem>
              {channels.data?.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={media} onValueChange={(v) => { setMedia(v); setPage(1); }}>
            <SelectTrigger className="h-8 text-xs sm:w-40" aria-label={t("messages.media")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>{t("messages.anyMedia")}</SelectItem>
              {["document", "photo", "none"].map((m) => (
                <SelectItem key={m} value={m}>{m}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : (
          <>
            <DataTable
              columns={columns}
              data={data?.items ?? []}
              loading={isPending || isFetching}
              getRowId={(m) => String(m.id)}
              empty={<EmptyState icon={MessagesSquare} title={t("messages.empty")} description={t("messages.emptyHint")} />}
              renderCard={(m) => (
                <div className="space-y-1">
                  <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="truncate font-medium text-foreground">{m.channel.name}</span>
                    <span>{fmtRelative(m.message_date)}</span>
                  </div>
                  <p className="line-clamp-2 text-sm" dir="auto">{m.caption || m.file_name || "—"}</p>
                  {m.file_id && m.file_status && (
                    <Link to={`/files?file=${m.file_id}`} className="inline-flex"><FileStatusBadge status={m.file_status} /></Link>
                  )}
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
