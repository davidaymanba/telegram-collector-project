import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, Loader2, MoreHorizontal, Pencil, Plus, Radio, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n";
import type { Channel } from "@/lib/types";
import { errorMessage, useChannels, useDeleteChannel, useSaveChannel, useToggleChannel } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { EmptyState, ErrorState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { HashText } from "@/components/HashText";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SimpleTooltip } from "@/components/ui/tooltip";

function ChannelForm({ channel, open, onOpenChange }: { channel: Channel | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useI18n();
  const save = useSaveChannel();
  const schema = useMemo(
    () =>
      z
        .object({
          name: z.string().trim().min(1, t("auth.required")).max(255),
          username: z
            .string()
            .trim()
            .transform((v) => v.replace(/^https:\/\/t\.me\//, "").replace(/^@/, "").replace(/\/$/, ""))
            .refine((v) => v === "" || /^[A-Za-z][A-Za-z0-9_]{3,63}$/.test(v), t("channels.invalidUsername")),
          telegram_id: z
            .string()
            .trim()
            .refine((v) => v === "" || /^-?\d+$/.test(v), t("channels.telegramIdHint")),
          enabled: z.boolean(),
          last_message_id: z.string().trim().refine((v) => /^\d*$/.test(v)),
        })
        .refine((v) => v.username !== "" || v.telegram_id !== "", { message: t("channels.needId"), path: ["username"] }),
    [t],
  );
  type Values = z.input<typeof schema>;
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open)
      form.reset({
        name: channel?.name ?? "",
        username: channel?.username ?? "",
        telegram_id: channel?.telegram_id != null ? String(channel.telegram_id) : "",
        enabled: channel?.enabled ?? true,
        last_message_id: channel ? String(channel.last_message_id) : "0",
      });
  }, [open, channel, form]);

  const onSubmit = form.handleSubmit((raw) => {
    const v = schema.parse(raw);
    save.mutate(
      {
        id: channel?.id,
        name: v.name,
        username: v.username || null,
        telegram_id: v.telegram_id ? Number(v.telegram_id) : null,
        enabled: v.enabled,
        ...(channel ? { last_message_id: Number(v.last_message_id || 0) } : {}),
      },
      {
        onSuccess: () => {
          toast.success(channel ? t("channels.updated") : t("channels.created"));
          onOpenChange(false);
        },
        onError: (e) => toast.error(errorMessage(e)),
      },
    );
  });

  const err = form.formState.errors;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <form onSubmit={onSubmit} className="flex h-full flex-col" noValidate>
          <SheetHeader>
            <SheetTitle>{channel ? t("channels.edit") : t("channels.add")}</SheetTitle>
            <SheetDescription>{t("channels.subtitle")}</SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-5 overflow-y-auto p-5">
            <div className="space-y-1.5">
              <Label htmlFor="ch-name">{t("channels.name")}</Label>
              <Input id="ch-name" autoFocus aria-invalid={!!err.name} {...form.register("name")} />
              {err.name && <p className="text-xs text-destructive">{err.name.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ch-username">{t("channels.username")}</Label>
              <div className="relative" dir="ltr">
                <span className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">@</span>
                <Input id="ch-username" className="ps-7 font-mono" aria-invalid={!!err.username} {...form.register("username")} />
              </div>
              <p className={err.username ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
                {err.username?.message ?? t("channels.usernameHint")}
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ch-tgid">
                {t("channels.telegramId")} <span className="font-normal text-muted-foreground">({t("common.optional")})</span>
              </Label>
              <Input id="ch-tgid" dir="ltr" inputMode="numeric" className="font-mono" aria-invalid={!!err.telegram_id} {...form.register("telegram_id")} />
              <p className="text-xs text-muted-foreground">{t("channels.telegramIdHint")}</p>
            </div>
            {channel && (
              <div className="space-y-1.5">
                <Label htmlFor="ch-cursor">{t("channels.resetCursor")}</Label>
                <Input id="ch-cursor" dir="ltr" inputMode="numeric" className="font-mono tabular" {...form.register("last_message_id")} />
                <p className="text-xs text-muted-foreground">{t("channels.resetCursorHint")}</p>
              </div>
            )}
            <div className="flex items-center justify-between rounded-lg border p-3">
              <Label htmlFor="ch-enabled" className="cursor-pointer">{t("channels.enabled")}</Label>
              <Controller
                control={form.control}
                name="enabled"
                render={({ field }) => <Switch id="ch-enabled" checked={field.value} onCheckedChange={field.onChange} />}
              />
            </div>
          </div>
          <SheetFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" />}
              {save.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}

export default function Channels() {
  const { t, tx, fmtNumber, fmtRelative, fmtDateTime } = useI18n();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data, isPending, isError, error, refetch } = useChannels();
  const toggle = useToggleChannel();
  const del = useDeleteChannel();
  const [editing, setEditing] = useState<Channel | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [deleting, setDeleting] = useState<Channel | null>(null);

  useEffect(() => {
    if (params.get("new")) {
      setEditing(null);
      setFormOpen(true);
      params.delete("new");
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  const openForm = (c: Channel | null) => {
    setEditing(c);
    setFormOpen(true);
  };
  const collect = (c: Channel) => navigate(`/live?channel=${c.id}`);

  const actions = (c: Channel) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={t("common.actions")} onClick={(e) => e.stopPropagation()}>
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem onSelect={() => collect(c)} disabled={!c.enabled}>
          <Download /> {t("channels.collectNow")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => openForm(c)}>
          <Pencil /> {t("common.edit")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem destructive onSelect={() => setDeleting(c)}>
          <Trash2 /> {t("common.delete")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const toggleSwitch = (c: Channel) => (
    <Switch
      checked={c.enabled}
      onClick={(e) => e.stopPropagation()}
      onCheckedChange={(enabled) =>
        toggle.mutate({ id: c.id, enabled }, { onSuccess: () => toast.success(t("channels.updated")) })
      }
      aria-label={`${t("channels.enabled")}: ${c.name}`}
    />
  );

  const columns: ColumnDef<Channel, unknown>[] = [
    {
      id: "name",
      header: t("channels.name"),
      cell: ({ row: { original: c } }) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{c.name}</p>
          {c.last_error && (
            <SimpleTooltip content={c.last_error}>
              <p className="max-w-xs truncate text-xs text-status-failed">{c.last_error}</p>
            </SimpleTooltip>
          )}
        </div>
      ),
    },
    {
      id: "username",
      header: t("channels.username"),
      cell: ({ row: { original: c } }) =>
        c.username ? (
          <span dir="ltr" className="font-mono text-xs text-muted-foreground">@{c.username}</span>
        ) : (
          <HashText value={c.telegram_id} head={6} tail={4} />
        ),
    },
    {
      id: "status",
      header: t("channels.status"),
      cell: ({ row: { original: c } }) => <StatusBadge status={c.status} label={tx(`channelStatus.${c.status}`)} />,
    },
    {
      id: "last_message",
      header: t("channels.lastMessage"),
      cell: ({ row: { original: c } }) => <span className="font-mono text-xs tabular">{c.last_message_id || "—"}</span>,
    },
    {
      id: "last_run",
      header: t("channels.lastRun"),
      cell: ({ row: { original: c } }) =>
        c.last_run_at ? (
          <SimpleTooltip content={fmtDateTime(c.last_run_at)}>
            <span className="text-muted-foreground">{fmtRelative(c.last_run_at)}</span>
          </SimpleTooltip>
        ) : (
          <span className="text-muted-foreground">{t("common.never")}</span>
        ),
    },
    {
      id: "files",
      header: t("channels.files"),
      meta: { className: "tabular" },
      cell: ({ row: { original: c } }) => fmtNumber(c.file_count),
    },
    { id: "enabled", header: t("channels.enabled"), cell: ({ row: { original: c } }) => toggleSwitch(c) },
    {
      id: "actions",
      header: () => <span className="sr-only">{t("common.actions")}</span>,
      meta: { className: "w-10 text-end" },
      cell: ({ row: { original: c } }) => (
        <div className="flex items-center justify-end gap-1">
          <SimpleTooltip content={t("channels.collectNow")}>
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={!c.enabled}
              onClick={(e) => {
                e.stopPropagation();
                collect(c);
              }}
              aria-label={t("channels.collectNow")}
            >
              <Download />
            </Button>
          </SimpleTooltip>
          {actions(c)}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("channels.title")}
        description={t("channels.subtitle")}
        actions={
          <Button onClick={() => openForm(null)}>
            <Plus /> {t("channels.add")}
          </Button>
        }
      />
      <Card className="overflow-hidden">
        {isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : (
          <DataTable
            columns={columns}
            data={data ?? []}
            loading={isPending}
            skeletonRows={4}
            getRowId={(c) => String(c.id)}
            onRowClick={openForm}
            rowLabel={(c) => c.name}
            empty={
              <EmptyState
                icon={Radio}
                title={t("channels.empty")}
                description={t("channels.emptyHint")}
                action={
                  <Button onClick={() => openForm(null)}>
                    <Plus /> {t("channels.addFirst")}
                  </Button>
                }
              />
            }
            renderCard={(c) => (
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-medium">{c.name}</p>
                    <StatusBadge status={c.status} label={tx(`channelStatus.${c.status}`)} />
                  </div>
                  <p className="text-xs text-muted-foreground" dir="auto">
                    {c.username ? `@${c.username}` : c.telegram_id} · {fmtNumber(c.file_count)} {t("channels.files")} ·{" "}
                    {fmtRelative(c.last_run_at)}
                  </p>
                </div>
                {toggleSwitch(c)}
              </div>
            )}
          />
        )}
      </Card>

      <ChannelForm channel={editing} open={formOpen} onOpenChange={setFormOpen} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t("channels.deleteTitle", { name: deleting?.name ?? "" })}
        description={t("channels.deleteBody", { count: fmtNumber(deleting?.file_count ?? 0) })}
        onConfirm={() =>
          deleting &&
          del.mutate(deleting.id, {
            onSuccess: () => toast.success(t("channels.deleted")),
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </div>
  );
}
