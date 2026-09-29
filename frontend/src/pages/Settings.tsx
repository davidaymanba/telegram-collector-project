import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, CircleDashed, Download, FileUp, KeyRound, Loader2, PlugZap, ShieldCheck, Sparkles } from "lucide-react";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import { errorMessage, useInvalidateData, useSettings } from "@/hooks/queries";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function ToolCard({ icon: Icon, title, hint, children }: { icon: typeof Sparkles; title: string; hint: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-start gap-3 space-y-0">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-muted/40">
          <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
        </div>
        <div className="space-y-1">
          <CardTitle>{title}</CardTitle>
          <CardDescription className="text-sm">{hint}</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="mt-auto flex flex-wrap gap-2">{children}</CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const { t, tx } = useI18n();
  const { data, isPending, isError, error, refetch } = useSettings();
  const invalidate = useInvalidateData();
  const fileRef = useRef<HTMLInputElement>(null);
  const [openaiResult, setOpenaiResult] = useState<{ ok: boolean; message: string } | null>(null);

  const seed = useMutation({
    mutationFn: () => api.post<{ files?: number; skipped?: number }>("/settings/seed-demo"),
    onSuccess: async (r) => {
      toast.success(r.skipped ? t("settings.seedSkipped") : t("settings.seeded", { files: r.files ?? 0 }));
      await invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const importYaml = useMutation({
    mutationFn: (files: FileList | null) => {
      if (!files?.length) return api.post<Record<string, unknown>>("/settings/import-config");
      const form = new FormData();
      for (const f of Array.from(files)) {
        form.append(f.name.toLowerCase().includes("channel") ? "channels" : "subjects", f);
      }
      return api.upload<Record<string, unknown>>("/settings/import-config", form);
    },
    onSuccess: async (r) => {
      const parts = Object.entries(r).map(([k, v]) => `${k}: ${Object.entries(v as Record<string, number>).map(([a, b]) => `${a} ${b}`).join(", ")}`);
      toast.success(t("settings.imported"), { description: parts.join(" · ") });
      await invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const testOpenai = useMutation({
    mutationFn: () => api.post<{ ok: boolean; message: string }>("/settings/test-openai"),
    onSuccess: (r) => {
      setOpenaiResult(r);
      (r.ok ? toast.success : toast.error)(r.message);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">{t("settings.tools")}</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ToolCard icon={Sparkles} title={t("settings.seed")} hint={t("settings.seedHint")}>
            <Button variant="outline" size="sm" onClick={() => seed.mutate()} disabled={seed.isPending}>
              {seed.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} {t("settings.seed")}
            </Button>
          </ToolCard>
          <ToolCard icon={FileUp} title={t("settings.importYaml")} hint={t("settings.importHint")}>
            <input
              ref={fileRef}
              type="file"
              accept=".yaml,.yml"
              multiple
              className="sr-only"
              aria-label={t("settings.importFiles")}
              onChange={(e) => {
                importYaml.mutate(e.target.files);
                e.target.value = "";
              }}
            />
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={importYaml.isPending}>
              <FileUp /> {t("settings.importFiles")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => importYaml.mutate(null)} disabled={importYaml.isPending}>
              {importYaml.isPending && <Loader2 className="animate-spin" />}
              {t("settings.importDefault")}
            </Button>
          </ToolCard>
          <ToolCard icon={Download} title={t("settings.exportYaml")} hint={t("settings.exportHint")}>
            <Button variant="outline" size="sm" asChild>
              <a href="/api/v1/settings/export-config" download>
                <Download /> {t("settings.exportYaml")}
              </a>
            </Button>
          </ToolCard>
          <ToolCard icon={PlugZap} title={t("settings.testOpenai")} hint={t("settings.testOpenaiHint")}>
            <Button variant="outline" size="sm" onClick={() => testOpenai.mutate()} disabled={testOpenai.isPending}>
              {testOpenai.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
              {testOpenai.isPending ? t("settings.testing") : t("settings.testOpenai")}
            </Button>
            {openaiResult && (
              <p role="status" className={openaiResult.ok ? "w-full text-xs text-status-classified" : "w-full text-xs text-status-failed"}>
                {openaiResult.message}
              </p>
            )}
          </ToolCard>
        </div>
      </section>

      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <ShieldCheck className="h-4 w-4 shrink-0 text-primary" aria-hidden />
        {t("settings.secretHidden")}
      </div>

      {isPending ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-56" />)}
        </div>
      ) : isError ? (
        <Card><ErrorState error={error} onRetry={() => refetch()} /></Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 [&>*]:min-w-0">
          {Object.entries(data.sections).map(([section, rows]) => (
            <Card key={section}>
              <CardHeader>
                <CardTitle>{tx(`settings.sections.${section}`)}</CardTitle>
              </CardHeader>
              <CardContent className="px-0 sm:px-0">
                <dl className="divide-y border-t">
                  {rows.map((r) => (
                    <div key={r.key} className="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[minmax(0,15rem)_1fr] sm:gap-3 sm:px-5">
                      <dt className="truncate font-mono text-[11px] text-muted-foreground" dir="ltr" title={r.key}>
                        {r.key.toUpperCase().startsWith("DASHBOARD") ? r.key.toUpperCase() : `TUC_${r.key.toUpperCase()}`}
                      </dt>
                      <dd className="min-w-0 text-sm">
                        {r.secret ? (
                          r.configured ? (
                            <span className="inline-flex items-center gap-1.5 text-status-classified">
                              <KeyRound className="h-3.5 w-3.5" aria-hidden /> {t("common.configured")}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                              <CircleDashed className="h-3.5 w-3.5" aria-hidden /> {t("common.notConfigured")}
                            </span>
                          )
                        ) : r.value === null ? (
                          <span className="text-muted-foreground">—</span>
                        ) : r.value === "True" || r.value === "False" ? (
                          <span className="inline-flex items-center gap-1.5">
                            {r.value === "True" ? <CheckCircle2 className="h-3.5 w-3.5 text-status-classified" aria-hidden /> : <CircleDashed className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
                            {r.value === "True" ? t("common.yes") : t("common.no")}
                          </span>
                        ) : (
                          <span dir="ltr" className="break-all font-mono text-xs">{r.value}</span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
