import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertCircle, Languages, Loader2, Lock, Moon, Sun } from "lucide-react";
import { useI18n } from "@/i18n";
import { useTheme } from "@/hooks/use-theme";
import { useLogin, useMe } from "@/hooks/queries";
import { ApiError } from "@/lib/api";
import { LogoMark } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const { t, lang, setLang } = useI18n();
  const { resolved, toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const me = useMe();
  const login = useLogin();

  const schema = z.object({
    username: z.string().trim().min(1, t("auth.required")),
    password: z.string().min(1, t("auth.required")),
  });
  type Values = z.infer<typeof schema>;
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { username: "", password: "" } });

  useEffect(() => {
    if (me.data) navigate(from, { replace: true });
  }, [me.data, from, navigate]);

  const onSubmit = form.handleSubmit((values) =>
    login.mutate(values, { onSuccess: () => navigate(from, { replace: true }) }),
  );

  const err = login.error;
  const errorText =
    err instanceof ApiError
      ? err.status === 401
        ? t("auth.invalid")
        : err.status === 429
          ? t("auth.tooMany")
          : err.status === 503
            ? t("auth.notConfigured")
            : err.status === 0
              ? t("common.networkError")
              : err.message
      : err
        ? t("common.errorTitle")
        : null;

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center bg-muted/30 px-4">
      <div className="absolute end-4 top-4 flex gap-1">
        <Button variant="ghost" size="sm" onClick={() => setLang(lang === "ar" ? "en" : "ar")} aria-label={t("topbar.language")}>
          <Languages /> {lang === "ar" ? "English" : "العربية"}
        </Button>
        <Button variant="ghost" size="icon" onClick={toggle} aria-label={t("topbar.theme")}>
          {resolved === "dark" ? <Sun /> : <Moon />}
        </Button>
      </div>

      <main className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <LogoMark className="h-11 w-11" />
          <div className="space-y-1">
            <h1 className="text-lg font-semibold tracking-tight">{t("app.fullName")}</h1>
            <p className="text-sm text-muted-foreground">{t("app.tagline")}</p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="mb-5 space-y-1">
            <h2 className="text-base font-semibold">{t("auth.title")}</h2>
            <p className="text-sm text-muted-foreground">{t("auth.subtitle")}</p>
          </div>

          {errorText && (
            <div role="alert" className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{errorText}</span>
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="username">{t("auth.username")}</Label>
              <Input
                id="username"
                autoComplete="username"
                autoFocus
                dir="ltr"
                aria-invalid={!!form.formState.errors.username}
                aria-describedby={form.formState.errors.username ? "username-error" : undefined}
                {...form.register("username")}
              />
              {form.formState.errors.username && (
                <p id="username-error" className="text-xs text-destructive">{form.formState.errors.username.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">{t("auth.password")}</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                dir="ltr"
                aria-invalid={!!form.formState.errors.password}
                aria-describedby={form.formState.errors.password ? "password-error" : undefined}
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <p id="password-error" className="text-xs text-destructive">{form.formState.errors.password.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? <Loader2 className="animate-spin" /> : null}
              {login.isPending ? t("auth.submitting") : t("auth.submit")}
            </Button>
          </form>
        </div>
        <p className="mt-6 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="h-3 w-3" /> {t("auth.localOnly")}
        </p>
      </main>
    </div>
  );
}
