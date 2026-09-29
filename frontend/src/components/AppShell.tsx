import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BookText,
  ChevronRight,
  Languages,
  LogOut,
  Menu,
  Monitor,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
} from "lucide-react";
import { toast } from "sonner";
import { cn, initials } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { NAV } from "@/lib/nav";
import { useTheme, type Theme } from "@/hooks/use-theme";
import { useLogout, useMe } from "@/hooks/queries";
import { LogoMark } from "./Logo";
import { SystemIndicator } from "./SystemIndicator";
import { CommandPalette, useCommandPalette } from "./CommandPalette";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "./ui/sheet";
import { SimpleTooltip } from "./ui/tooltip";

const COLLAPSE_KEY = "tuc.sidebar.collapsed";
const GROUPS = ["groupWork", "groupData", "groupSystem"] as const;

function NavList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { t } = useI18n();
  return (
    <nav className="flex flex-col gap-4" aria-label="Main">
      {GROUPS.map((group) => (
        <div key={group} className="space-y-0.5">
          {!collapsed && (
            <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/80">{t(`nav.${group}`)}</p>
          )}
          {NAV.filter((n) => n.group === group).map((item) => {
            const link = (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "group flex h-8 items-center gap-2.5 rounded-md px-2 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isActive
                      ? "bg-background text-foreground shadow-[0_0_0_1px_hsl(var(--border))]"
                      : "text-sidebar-foreground hover:bg-accent hover:text-foreground",
                    collapsed && "justify-center px-0",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} aria-hidden />
                    {collapsed ? <span className="sr-only">{t(item.label)}</span> : <span className="truncate">{t(item.label)}</span>}
                  </>
                )}
              </NavLink>
            );
            return collapsed ? (
              <SimpleTooltip key={item.to} content={t(item.label)} side="right">
                {link}
              </SimpleTooltip>
            ) : (
              link
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  const { t } = useI18n();
  return (
    <Link to="/" className={cn("flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", collapsed && "justify-center")}>
      <LogoMark />
      {!collapsed && (
        <span className="min-w-0 leading-tight">
          <span className="block text-sm font-semibold">{t("app.name")}</span>
          <span className="block truncate text-[11px] text-muted-foreground">{t("app.fullName")}</span>
        </span>
      )}
    </Link>
  );
}

function Breadcrumbs() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  const item = NAV.find((n) => n.to === `/${parts[0] ?? ""}`) ?? NAV[0];
  return (
    <ol className="flex min-w-0 items-center gap-1.5 text-sm" aria-label="Breadcrumb">
      <li className="hidden text-muted-foreground sm:block">{t("app.name")}</li>
      <li className="hidden sm:block" aria-hidden>
        <ChevronRight className="rtl-flip h-3.5 w-3.5 text-muted-foreground/60" />
      </li>
      <li className={cn("truncate", parts.length > 1 ? "text-muted-foreground" : "font-medium")}>
        {parts.length > 1 ? <Link to={item.to} className="hover:text-foreground">{t(item.label)}</Link> : t(item.label)}
      </li>
      {parts.length > 1 && (
        <>
          <li aria-hidden>
            <ChevronRight className="rtl-flip h-3.5 w-3.5 text-muted-foreground/60" />
          </li>
          <li className="truncate font-medium tabular" aria-current="page">#{parts[1]}</li>
        </>
      )}
    </ol>
  );
}

function ThemeMenuItems() {
  const { t } = useI18n();
  const { theme, setTheme } = useTheme();
  return (
    <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as Theme)}>
      <DropdownMenuRadioItem value="light"><Sun className="me-2" />{t("topbar.light")}</DropdownMenuRadioItem>
      <DropdownMenuRadioItem value="dark"><Moon className="me-2" />{t("topbar.dark")}</DropdownMenuRadioItem>
      <DropdownMenuRadioItem value="system"><Monitor className="me-2" />{t("topbar.system")}</DropdownMenuRadioItem>
    </DropdownMenuRadioGroup>
  );
}

export function AppShell() {
  const { t, lang, setLang } = useI18n();
  const { resolved } = useTheme();
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const palette = useCommandPalette();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  const onLogout = () =>
    logout.mutate(undefined, {
      onSettled: () => {
        navigate("/login", { replace: true });
        toast.success(t("auth.logout"));
      },
    });

  return (
    <div className="flex min-h-dvh bg-background">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:start-2 focus:top-2 focus:z-[60] focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring">
        Skip to content
      </a>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-e bg-sidebar transition-[width] duration-200 lg:flex",
          collapsed ? "w-[60px]" : "w-60",
        )}
      >
        <div className={cn("flex h-14 items-center border-b px-3", collapsed && "justify-center px-0")}>
          <Brand collapsed={collapsed} />
        </div>
        <div className="flex-1 overflow-y-auto px-2.5 py-4 scrollbar-thin">
          <NavList collapsed={collapsed} />
        </div>
        <div className="space-y-2 border-t p-2.5">
          <SystemIndicator collapsed={collapsed} />
          <Button
            variant="ghost"
            size="sm"
            className={cn("w-full justify-start text-muted-foreground", collapsed && "justify-center px-0")}
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? t("nav.expand") : t("nav.collapse")}
            aria-expanded={!collapsed}
          >
            {collapsed ? <PanelLeftOpen className="rtl-flip" /> : <PanelLeftClose className="rtl-flip" />}
            {!collapsed && t("nav.collapse")}
          </Button>
        </div>
      </aside>

      {/* Mobile drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="start" className="w-72 bg-sidebar p-0">
          <SheetTitle className="sr-only">{t("nav.openMenu")}</SheetTitle>
          <div className="flex h-14 items-center border-b px-4">
            <Brand collapsed={false} />
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-4">
            <NavList collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </div>
          <div className="border-t p-3">
            <SystemIndicator collapsed={false} />
          </div>
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-background/85 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:px-5">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label={t("nav.openMenu")}>
            <Menu />
          </Button>
          <Breadcrumbs />
          <div className="ms-auto flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => palette.setOpen(true)}
              className="hidden h-8 w-64 items-center gap-2 rounded-md border bg-muted/40 px-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:flex"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="truncate">{t("topbar.search")}</span>
              <kbd className="ms-auto rounded border bg-background px-1.5 font-mono text-[10px]" dir="ltr">⌘K</kbd>
            </button>
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => palette.setOpen(true)} aria-label={t("topbar.search")}>
              <Search />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setLang(lang === "ar" ? "en" : "ar")}
              aria-label={t("topbar.language")}
              className="px-2 font-medium"
            >
              <Languages />
              <span className="text-xs">{lang === "ar" ? "EN" : "ع"}</span>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label={t("topbar.theme")}>
                  {resolved === "dark" ? <Moon /> : <Sun />}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{t("topbar.theme")}</DropdownMenuLabel>
                <ThemeMenuItems />
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="ms-1 flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={me?.username ?? "User"}
                >
                  {initials(me?.username ?? "?")}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuLabel className="font-normal">
                  <span className="block text-xs text-muted-foreground">{t("auth.signedInAs")}</span>
                  <span className="block text-sm font-medium text-foreground">{me?.username}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <a href="/api/docs" target="_blank" rel="noreferrer">
                    <BookText /> {t("topbar.apiDocs")}
                  </a>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem destructive onSelect={onLogout}>
                  <LogOut className="rtl-flip" /> {t("auth.logout")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-3 py-5 sm:px-6 sm:py-6">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={palette.open} onOpenChange={palette.setOpen} />
    </div>
  );
}
