import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { BookOpen, FileUp, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n";
import { CONTENT_TYPES, type Subject } from "@/lib/types";
import { TYPE_COLOR } from "@/lib/content-types";
import { errorMessage, useDeleteSubject, useSaveSubject, useSubjects } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { EmptyState, ErrorState } from "@/components/States";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TagInput } from "@/components/TagInput";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { SimpleTooltip } from "@/components/ui/tooltip";

function SubjectForm({ subject, open, onOpenChange }: { subject: Subject | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useI18n();
  const save = useSaveSubject();
  const schema = useMemo(
    () =>
      z.object({
        code: z
          .string()
          .trim()
          .transform((v) => v.toUpperCase())
          .refine((v) => /^[A-Z][A-Z0-9_-]{1,31}$/.test(v), t("subjects.invalidCode")),
        name_ar: z.string().trim().min(1, t("auth.required")).max(255),
        name_en: z.string().trim().min(1, t("auth.required")).max(255),
        keywords: z.array(z.string()),
      }),
    [t],
  );
  type Values = z.input<typeof schema>;
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open)
      form.reset({
        code: subject?.code ?? "",
        name_ar: subject?.name_ar ?? "",
        name_en: subject?.name_en ?? "",
        keywords: subject?.keywords ?? [],
      });
  }, [open, subject, form]);

  const onSubmit = form.handleSubmit((raw) => {
    const v = schema.parse(raw);
    save.mutate(
      { id: subject?.id, ...v },
      {
        onSuccess: () => {
          toast.success(subject ? t("subjects.updated") : t("subjects.created"));
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
            <SheetTitle>{subject ? t("subjects.edit") : t("subjects.add")}</SheetTitle>
            <SheetDescription>{t("subjects.subtitle")}</SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-5 overflow-y-auto p-5">
            <div className="space-y-1.5">
              <Label htmlFor="s-code">{t("subjects.code")}</Label>
              <Input
                id="s-code"
                dir="ltr"
                className="font-mono uppercase"
                disabled={!!subject}
                autoFocus={!subject}
                aria-invalid={!!err.code}
                {...form.register("code")}
              />
              <p className={err.code ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
                {err.code?.message ?? t("subjects.codeHint")}
              </p>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="s-ar">{t("subjects.nameAr")}</Label>
                <Input id="s-ar" dir="rtl" lang="ar" aria-invalid={!!err.name_ar} {...form.register("name_ar")} />
                {err.name_ar && <p className="text-xs text-destructive">{err.name_ar.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="s-en">{t("subjects.nameEn")}</Label>
                <Input id="s-en" dir="ltr" lang="en" aria-invalid={!!err.name_en} {...form.register("name_en")} />
                {err.name_en && <p className="text-xs text-destructive">{err.name_en.message}</p>}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-kw">{t("subjects.keywords")}</Label>
              <Controller
                control={form.control}
                name="keywords"
                render={({ field }) => (
                  <TagInput id="s-kw" value={field.value ?? []} onChange={field.onChange} placeholder={t("subjects.keywordsPlaceholder")} />
                )}
              />
              <p className="text-xs text-muted-foreground">{t("subjects.keywordsHint")}</p>
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

function TypeCounts({ s }: { s: Subject }) {
  const { tx, fmtNumber } = useI18n();
  return (
    <div className="flex flex-wrap gap-1">
      {CONTENT_TYPES.map((ct) => {
        const n = s.counts[ct] ?? 0;
        return (
          <SimpleTooltip key={ct} content={tx(`contentType.${ct}`)}>
            <span
              className={
                n
                  ? "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] tabular"
                  : "inline-flex items-center gap-1 rounded border border-dashed px-1.5 py-0.5 text-[11px] text-muted-foreground/70 tabular"
              }
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: TYPE_COLOR[ct] }} aria-hidden />
              <span className="sr-only">{tx(`contentType.${ct}`)}</span>
              {fmtNumber(n)}
            </span>
          </SimpleTooltip>
        );
      })}
    </div>
  );
}

export default function Subjects() {
  const { t, lang, fmtNumber } = useI18n();
  const [params, setParams] = useSearchParams();
  const { data, isPending, isError, error, refetch } = useSubjects();
  const del = useDeleteSubject();
  const [editing, setEditing] = useState<Subject | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [deleting, setDeleting] = useState<Subject | null>(null);

  useEffect(() => {
    if (params.get("new")) {
      setEditing(null);
      setFormOpen(true);
      params.delete("new");
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  const openForm = (s: Subject | null) => {
    setEditing(s);
    setFormOpen(true);
  };

  const columns: ColumnDef<Subject, unknown>[] = [
    {
      id: "code",
      header: t("subjects.code"),
      cell: ({ row: { original: s } }) => <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs font-medium">{s.code}</code>,
    },
    {
      id: "name",
      header: `${t("subjects.nameAr")} / ${t("subjects.nameEn")}`,
      cell: ({ row: { original: s } }) => (
        <div className="min-w-0">
          <p className="truncate font-medium" lang="ar" dir="rtl">{s.name_ar}</p>
          <p className="truncate text-xs text-muted-foreground" lang="en" dir="ltr">{s.name_en}</p>
        </div>
      ),
    },
    {
      id: "keywords",
      header: t("subjects.keywords"),
      cell: ({ row: { original: s } }) => (
        <div className="flex max-w-xs flex-wrap gap-1">
          {s.keywords.slice(0, 5).map((k) => (
            <span key={k} className="rounded bg-secondary px-1.5 py-0.5 text-[11px]">{k}</span>
          ))}
          {s.keywords.length > 5 && (
            <SimpleTooltip content={s.keywords.slice(5).join("، ")}>
              <span className="rounded px-1 py-0.5 text-[11px] text-muted-foreground">+{s.keywords.length - 5}</span>
            </SimpleTooltip>
          )}
        </div>
      ),
    },
    { id: "counts", header: t("subjects.files"), cell: ({ row: { original: s } }) => <TypeCounts s={s} /> },
    {
      id: "total",
      header: t("subjects.total"),
      meta: { className: "font-medium tabular" },
      cell: ({ row: { original: s } }) =>
        s.total ? (
          <Link to={`/files?subject=${s.code}`} className="hover:underline" onClick={(e) => e.stopPropagation()}>
            {fmtNumber(s.total)}
          </Link>
        ) : (
          <span className="text-muted-foreground">0</span>
        ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">{t("common.actions")}</span>,
      meta: { className: "w-20 text-end" },
      cell: ({ row: { original: s } }) => (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="icon-sm" aria-label={`${t("common.edit")} ${s.code}`} onClick={(e) => { e.stopPropagation(); openForm(s); }}>
            <Pencil />
          </Button>
          <Button variant="ghost" size="icon-sm" className="hover:text-destructive" aria-label={`${t("common.delete")} ${s.code}`} onClick={(e) => { e.stopPropagation(); setDeleting(s); }}>
            <Trash2 />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("subjects.title")}
        description={t("subjects.subtitle")}
        actions={
          <Button onClick={() => openForm(null)}>
            <Plus /> {t("subjects.add")}
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
            getRowId={(s) => String(s.id)}
            onRowClick={openForm}
            rowLabel={(s) => s.code}
            empty={
              <EmptyState
                icon={BookOpen}
                title={t("subjects.empty")}
                description={t("subjects.emptyHint")}
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button onClick={() => openForm(null)}>
                      <Plus /> {t("subjects.addFirst")}
                    </Button>
                    <Button asChild variant="outline">
                      <Link to="/settings">
                        <FileUp /> {t("subjects.importYaml")}
                      </Link>
                    </Button>
                  </div>
                }
              />
            }
            renderCard={(s) => (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{s.code}</code>
                  <span className="truncate font-medium">{lang === "ar" ? s.name_ar : s.name_en}</span>
                  <span className="ms-auto text-sm font-medium tabular">{fmtNumber(s.total)}</span>
                </div>
                <TypeCounts s={s} />
              </div>
            )}
          />
        )}
      </Card>
      <SubjectForm subject={editing} open={formOpen} onOpenChange={setFormOpen} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t("subjects.deleteTitle", { code: deleting?.code ?? "" })}
        description={t("subjects.deleteBody")}
        onConfirm={() =>
          deleting &&
          del.mutate(deleting.id, {
            onSuccess: () => toast.success(t("subjects.deleted")),
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </div>
  );
}
