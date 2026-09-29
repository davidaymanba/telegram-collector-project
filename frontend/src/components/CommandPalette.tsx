import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Languages, Moon, Play, Plus, Workflow } from "lucide-react";
import { useI18n } from "@/i18n";
import { NAV } from "@/lib/nav";
import { useTheme } from "@/hooks/use-theme";
import { errorMessage, useStartJob } from "@/hooks/queries";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "./ui/command";

export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("tuc:command-palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("tuc:command-palette", onOpen);
    };
  }, []);
  return { open, setOpen };
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t, lang, setLang } = useI18n();
  const { toggle } = useTheme();
  const navigate = useNavigate();
  const startJob = useStartJob();

  const run = (fn: () => void) => {
    onOpenChange(false);
    fn();
  };

  const start = (kind: "collect" | "process") =>
    run(() => {
      startJob.mutate(
        { kind },
        {
          onSuccess: () => {
            toast.success(t("live.started"));
            navigate("/live");
          },
          onError: (e) => toast.error(errorMessage(e)),
        },
      );
    });

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title={t("palette.placeholder")}>
      <CommandInput placeholder={t("palette.placeholder")} />
      <CommandList>
        <CommandEmpty>{t("palette.empty")}</CommandEmpty>
        <CommandGroup heading={t("palette.navigation")}>
          {NAV.map((item) => (
            <CommandItem key={item.to} value={`nav ${t(item.label)} ${item.to}`} onSelect={() => run(() => navigate(item.to))}>
              <item.icon />
              {t(item.label)}
              {item.shortcut && <kbd className="ms-auto font-mono text-[10px] text-muted-foreground">{item.shortcut}</kbd>}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading={t("palette.actions")}>
          <CommandItem value={`action ${t("palette.startCollect")}`} onSelect={() => start("collect")}>
            <Play /> {t("palette.startCollect")}
          </CommandItem>
          <CommandItem value={`action ${t("palette.startProcess")}`} onSelect={() => start("process")}>
            <Workflow /> {t("palette.startProcess")}
          </CommandItem>
          <CommandItem value={`action ${t("palette.addChannel")}`} onSelect={() => run(() => navigate("/channels?new=1"))}>
            <Plus /> {t("palette.addChannel")}
          </CommandItem>
          <CommandItem value={`action ${t("palette.addSubject")}`} onSelect={() => run(() => navigate("/subjects?new=1"))}>
            <Plus /> {t("palette.addSubject")}
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading={t("palette.preferences")}>
          <CommandItem value="pref theme dark light" onSelect={() => run(toggle)}>
            <Moon /> {t("palette.toggleTheme")}
          </CommandItem>
          <CommandItem value="pref language arabic english" onSelect={() => run(() => setLang(lang === "ar" ? "en" : "ar"))}>
            <Languages /> {t("palette.switchLang")}
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
