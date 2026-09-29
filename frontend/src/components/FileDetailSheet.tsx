import { useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2,
  CircleX,
  Download,
  ExternalLink,
  FolderSearch,
  Loader2,
  MinusCircle,
  RefreshCw,
  Tags,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { CONTENT_TYPES, type FileDetail, type LogEntry } from "@/lib/types";
import { errorMessage, useFile, useFileAction, useSubjects } from "@/hooks/queries";
import { FileStatusBadge, statusColor } from "./StatusBadge";
import { HashText } from "./HashText";
import { ErrorState } from "./States";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { Skeleton } from "./ui/skeleton";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-3 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("space-y-2", className)}>
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

const LOG_ICON = { success: CheckCircle2, failed: CircleX, skipped: MinusCircle } as const;
const LOG_STATUS = { success: "classified", failed: "failed", skipped: "duplicate" } as const;

function Timeline({ logs }: { logs: LogEntry[] }) {
  const { t, fmtDateTime } = useI18n();
  if (!logs.length) return <p className="text-sm text-muted-foreground">{t("files.detail.noLogs")}</p>;
  return (
    <ol className="relative space-y-4 border-s ps-5">
      {logs.map((l) => {
        const Icon = LOG_ICON[l.status];
        return (
          <li key={l.id} className="relative">
            <span className="absolute -start-[27px] top-0.5 bg-background">
              <Icon className="h-4 w-4" style={{ color: statusColor(LOG_STATUS[l.status]) }} aria-label={l.status} />
            </span>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-sm font-medium">{l.stage}</span>
              <time className="text-xs text-muted-foreground" dateTime={l.created_at}>{fmtDateTime(l.created_at)}</time>
              {l.run_id && <span className="text-xs text-muted-foreground tabular">· run #{l.run_id}</span>}
            </div>
            {l.message && <p className="text-xs text-muted-foreground" dir="auto">{l.message}</p>}
            {l.error_message && (
              <pre dir="ltr" className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-destructive/5 p-2 font-mono text-[11px] text-destructive scrollbar-thin">
                {l.error_message}
              </pre>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function ManualClassifyDialog({ file, open, onOpenChange }: { file: FileDetail; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t, tx, lang } = useI18n();
  const subjects = useSubjects();
  const action = useFileAction();
  const [subject, setSubject] = useState(file.classification?.subject_code ?? "");
  const [ctype, setCtype] = useState<string>(file.classification?.content_type ?? "");
  const submit = () =>
    action.mutate(
      { id: file.id, action: "classify", body: { subject_code: subject, content_type: ctype } },
      {
        onSuccess: () => {
          toast.success(t("files.detail.applied"));
          onOpenChange(false);
        },
        onError: (e) => toast.error(errorMessage(e)),
      },
    );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("files.detail.manualTitle")}</DialogTitle>
          <DialogDescription>{t("files.detail.manualHint")}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="mc-subject">{t("files.subject")}</Label>
            <Select value={subject} onValueChange={setSubject}>
              <SelectTrigger id="mc-subject">
                <SelectValue placeholder={t("files.detail.pickSubject")} />
              </SelectTrigger>
              <SelectContent>
                {subjects.data?.map((s) => (
                  <SelectItem key={s.code} value={s.code}>
                    <span className="font-mono text-xs">{s.code}</span> · {lang === "ar" ? s.name_ar : s.name_en}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="mc-type">{t("files.type")}</Label>
            <Select value={ctype} onValueChange={setCtype}>
              <SelectTrigger id="mc-type">
                <SelectValue placeholder={t("files.detail.pickType")} />
              </SelectTrigger>
              <SelectContent>
                {CONTENT_TYPES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {tx(`contentType.${c}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button onClick={submit} disabled={!subject || !ctype || action.isPending}>
            {action.isPending && <Loader2 className="animate-spin" />}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DetailBody({ file }: { file: FileDetail }) {
  const { t, tx, fmtBytes, fmtDateTime, fmtNumber, fmtPercent } = useI18n();
  const action = useFileAction();
  const [manualOpen, setManualOpen] = useState(false);
  const c = file.classification;
  const canProcess = file.exists_on_disk && !["duplicate", "unsupported"].includes(file.status);

  const run = (kind: "reprocess" | "reveal") =>
    action.mutate(
      { id: file.id, action: kind },
      {
        onSuccess: () => toast.success(kind === "reveal" ? t("files.detail.revealed") : t("files.detail.reprocessed")),
        onError: (e) => toast.error(errorMessage(e)),
      },
    );

  return (
    <>
      <div className="flex flex-wrap gap-2 border-b px-5 py-3">
        <Button size="sm" variant="outline" asChild disabled={!file.exists_on_disk}>
          <a href={file.exists_on_disk ? `/api/v1/files/${file.id}/download` : undefined} aria-disabled={!file.exists_on_disk} download>
            <Download /> {t("files.detail.download")}
          </a>
        </Button>
        <Button size="sm" variant="outline" onClick={() => run("reveal")} disabled={!file.exists_on_disk}>
          <FolderSearch /> {t("files.detail.reveal")}
        </Button>
        <Button size="sm" variant="outline" onClick={() => run("reprocess")} disabled={!canProcess || action.isPending}>
          {action.isPending && action.variables?.action === "reprocess" ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          {action.isPending && action.variables?.action === "reprocess" ? t("files.detail.reprocessing") : t("files.detail.reprocess")}
        </Button>
        <Button size="sm" onClick={() => setManualOpen(true)} disabled={["duplicate", "unsupported"].includes(file.status)}>
          <Tags /> {t("files.detail.manual")}
        </Button>
      </div>
      <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
        <TabsList className="mx-5 mt-3 w-fit">
          <TabsTrigger value="overview">{t("common.details")}</TabsTrigger>
          <TabsTrigger value="text">{t("files.detail.text")}</TabsTrigger>
          <TabsTrigger value="timeline">{t("files.detail.timeline")}</TabsTrigger>
        </TabsList>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-6 scrollbar-thin">
          <TabsContent value="overview" className="space-y-6">
            <Section title={t("files.detail.classification")}>
              {!c ? (
                <p className="text-sm text-muted-foreground">{t("files.detail.noClassification")}</p>
              ) : (
                <div className="space-y-3 rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {c.subject_code && <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs font-medium">{c.subject_code}</code>}
                    {c.content_type && <span className="text-sm font-medium">{tx(`contentType.${c.content_type}`)}</span>}
                    <span className="ms-auto rounded border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{c.classifier_version}</span>
                  </div>
                  {c.confidence !== null && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">{t("files.detail.confidence")}</span>
                        <span className="font-medium tabular">{fmtPercent(c.confidence)}</span>
                      </div>
                      <Progress value={c.confidence * 100} aria-label={t("files.detail.confidence")} />
                    </div>
                  )}
                  {c.reason && (
                    <p className="text-sm">
                      <span className="text-muted-foreground">{t("files.detail.reason")}: </span>
                      <span dir="auto">{c.reason}</span>
                    </p>
                  )}
                  {c.evidence.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("files.detail.evidence")}</p>
                      <ul className="space-y-1">
                        {c.evidence.map((e, i) => (
                          <li key={i} className="rounded bg-muted/60 px-2 py-1 text-xs" dir="auto">{e}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Section>

            <Section title={t("files.detail.message")}>
              <div className="space-y-2 rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{file.message.channel.name}</span>
                  <span>· #{file.message.telegram_message_id}</span>
                  <span>· {fmtDateTime(file.message.message_date)}</span>
                  {file.telegram_link && (
                    <a href={file.telegram_link} target="_blank" rel="noreferrer" className="ms-auto inline-flex items-center gap-1 text-primary hover:underline">
                      {t("files.detail.openTelegram")} <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
                <p className="whitespace-pre-wrap text-sm" dir="auto">
                  {file.message.caption || <span className="text-muted-foreground">{t("files.detail.noCaption")}</span>}
                </p>
              </div>
            </Section>

            <Section title={t("files.detail.metadata")}>
              <dl className="divide-y">
                <Meta label={t("files.size")}>{fmtBytes(file.size_bytes)}</Meta>
                <Meta label={t("files.extension")}><span className="font-mono text-xs uppercase">{file.extension || "—"}</span></Meta>
                <Meta label={t("files.detail.mime")}><span className="font-mono text-xs">{file.mime_type ?? "—"}</span></Meta>
                <Meta label={t("files.detail.sha256")}><HashText value={file.sha256} head={12} tail={6} /></Meta>
                <Meta label={t("files.detail.documentId")}><HashText value={file.telegram_document_id} /></Meta>
                <Meta label={t("files.collected")}>{fmtDateTime(file.created_at)}</Meta>
                {file.relative_path && (
                  <Meta label={t("files.detail.path")}>
                    <span dir="ltr" className="font-mono text-xs">{file.relative_path}</span>
                  </Meta>
                )}
                {file.duplicate_of_file_id && (
                  <Meta label={t("files.detail.duplicateOf")}>
                    <a href={`?file=${file.duplicate_of_file_id}`} className="font-mono text-xs text-primary hover:underline">#{file.duplicate_of_file_id}</a>
                  </Meta>
                )}
                {file.error_message && (
                  <Meta label={t("files.detail.error")}>
                    <span dir="ltr" className="text-xs text-destructive">{file.error_message}</span>
                  </Meta>
                )}
              </dl>
            </Section>
          </TabsContent>

          <TabsContent value="text">
            {file.text_preview ? (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground tabular">
                  {t("files.detail.textLength", { n: fmtNumber(file.text_length) })}
                  {file.text_length > file.text_preview.length && ` · ${t("files.detail.textTruncated", { n: fmtNumber(file.text_preview.length) })}`}
                </p>
                <pre dir="auto" className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 font-sans text-sm leading-6 scrollbar-thin">
                  {file.text_preview}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{t("files.detail.noText")}</p>
            )}
          </TabsContent>

          <TabsContent value="timeline">
            <Timeline logs={file.logs} />
          </TabsContent>
        </div>
      </Tabs>
      {manualOpen && <ManualClassifyDialog file={file} open={manualOpen} onOpenChange={setManualOpen} />}
    </>
  );
}

export function FileDetailSheet({ fileId, onClose }: { fileId: number | null; onClose: () => void }) {
  const { t } = useI18n();
  const { data, isPending, isError, error, refetch } = useFile(fileId);
  return (
    <Sheet open={fileId !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {data ? (
              <>
                <span className="truncate" dir="auto" title={data.original_filename}>{data.original_filename}</span>
                <FileStatusBadge status={data.status} />
              </>
            ) : (
              t("files.detail.title")
            )}
          </SheetTitle>
          <SheetDescription className="tabular">#{fileId}</SheetDescription>
        </SheetHeader>
        {isPending ? (
          <div className="space-y-4 p-5">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-32" />
            <Skeleton className="h-24" />
            <Skeleton className="h-40" />
          </div>
        ) : isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : (
          <DetailBody key={data.id} file={data} />
        )}
      </SheetContent>
    </Sheet>
  );
}
