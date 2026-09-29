import { Database, Lock, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { useSystemStatus } from "@/hooks/queries";
import { SimpleTooltip } from "./ui/tooltip";
import { statusColor } from "./StatusBadge";

function Row({ icon: Icon, label, value, state, collapsed }: { icon: typeof Database; label: string; value: string; state: string; collapsed: boolean }) {
  const content = (
    <div className={cn("flex items-center gap-2 rounded-md px-2 py-1 text-xs", collapsed && "justify-center px-0")}>
      <span className="relative">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
        <span
          className={cn("absolute -bottom-0.5 -end-0.5 h-1.5 w-1.5 rounded-full ring-2 ring-sidebar", state === "running" && "animate-soft-pulse")}
          style={{ backgroundColor: statusColor(state) }}
        />
      </span>
      {!collapsed && (
        <>
          <span className="text-muted-foreground">{label}</span>
          <span className="ms-auto truncate font-medium text-foreground/80">{value}</span>
        </>
      )}
    </div>
  );
  return collapsed ? <SimpleTooltip content={`${label}: ${value}`} side="right">{content}</SimpleTooltip> : content;
}

export function SystemIndicator({ collapsed }: { collapsed: boolean }) {
  const { t, tx } = useI18n();
  const { data, isError } = useSystemStatus();
  const db = isError ? "error" : data?.db ? "success" : data ? "error" : "idle";
  const tg = !data ? "idle" : data.telegram ? "success" : data.telegram_configured ? "locked" : "error";
  const lock = data?.lock.locked ? "running" : "idle";
  const holder = data?.lock.holder;
  return (
    <div className="space-y-0.5" aria-label="System status">
      <Row icon={Database} label={t("system.db")} value={db === "success" ? t("system.connected") : t("system.down")} state={db} collapsed={collapsed} />
      <Row
        icon={Send}
        label={t("system.telegram")}
        value={tg === "success" ? t("system.ok") : data?.telegram_configured ? t("system.sessionMissing") : t("common.notConfigured")}
        state={tg}
        collapsed={collapsed}
      />
      <Row
        icon={Lock}
        label={t("system.lock")}
        value={data?.lock.locked ? (holder?.kind ? tx(`kind.${holder.kind}`) : t("system.busy")) : t("system.idle")}
        state={lock}
        collapsed={collapsed}
      />
    </div>
  );
}
