import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { Skeleton } from "@/components/ui/skeleton";
import { LogoMark } from "@/components/Logo";
import { useMe } from "@/hooks/queries";
import { useI18n } from "@/i18n";
import LoginPage from "@/pages/Login";

const Overview = lazy(() => import("@/pages/Overview"));
const LivePull = lazy(() => import("@/pages/LivePull"));
const Channels = lazy(() => import("@/pages/Channels"));
const Subjects = lazy(() => import("@/pages/Subjects"));
const Files = lazy(() => import("@/pages/Files"));
const Messages = lazy(() => import("@/pages/Messages"));
const Runs = lazy(() => import("@/pages/Runs"));
const RunDetail = lazy(() => import("@/pages/RunDetail"));
const SettingsPage = lazy(() => import("@/pages/Settings"));
const NotFound = lazy(() => import("@/pages/NotFound"));

function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy>
      <div className="space-y-2">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

function BootScreen() {
  return (
    <div className="flex min-h-dvh items-center justify-center" aria-busy>
      <LogoMark className="h-9 w-9 animate-soft-pulse" />
    </div>
  );
}

function RequireAuth() {
  const me = useMe();
  const location = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();

  useEffect(() => {
    const onUnauthorized = () => {
      qc.removeQueries({ queryKey: ["me"] });
      navigate("/login", { replace: true, state: { from: location.pathname + location.search } });
    };
    window.addEventListener("tuc:unauthorized", onUnauthorized);
    return () => window.removeEventListener("tuc:unauthorized", onUnauthorized);
  }, [navigate, location, qc]);

  if (me.isPending) return <BootScreen />;
  if (me.isError) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <AppShell />;
}

export default function App() {
  const { t, lang } = useI18n();
  const { pathname } = useLocation();
  useEffect(() => {
    const segment = pathname.split("/")[1] || "overview";
    const key = segment === "live" ? "nav.live" : `nav.${segment}`;
    const title = t(key as never);
    document.title = `${title.startsWith("nav.") ? t("app.name") : title} · TUC`;
  }, [pathname, t, lang]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route
          path="*"
          element={
            <Suspense fallback={<PageSkeleton />}>
              <Routes>
                <Route index element={<Overview />} />
                <Route path="live" element={<LivePull />} />
                <Route path="channels" element={<Channels />} />
                <Route path="subjects" element={<Subjects />} />
                <Route path="files" element={<Files />} />
                <Route path="messages" element={<Messages />} />
                <Route path="runs" element={<Runs />} />
                <Route path="runs/:id" element={<RunDetail />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
