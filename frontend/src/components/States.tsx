import type { LucideIcon } from "lucide-react";
import { AlertTriangle, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/hooks/queries";
import { ApiError } from "@/lib/api";
import { Button } from "./ui/button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "gap-2 py-8" : "gap-3 px-6 py-16", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-lg border bg-muted/40">
        <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">{title}</p>
        {description && <p className="mx-auto max-w-sm text-sm text-muted-foreground">{description}</p>}
      </div>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className, compact }: { error: unknown; onRetry?: () => void; className?: string; compact?: boolean }) {
  const { t } = useI18n();
  const message = error instanceof ApiError && error.status === 0 ? t("common.networkError") : errorMessage(error, t("common.networkError"));
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center gap-3 text-center", compact ? "py-8" : "px-6 py-16", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5">
        <AlertTriangle className="h-5 w-5 text-destructive" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">{t("common.errorTitle")}</p>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw /> {t("common.retry")}
        </Button>
      )}
    </div>
  );
}
