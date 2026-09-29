import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, setCsrfToken } from "@/lib/api";
import type {
  Channel,
  Facets,
  FileDetail,
  FileItem,
  HealthCheck,
  Job,
  LockInfo,
  Me,
  MessageItem,
  Overview,
  Page,
  Run,
  RunDetail,
  SettingRow,
  Subject,
  SystemStatus,
} from "@/lib/types";

export const qk = {
  me: ["me"] as const,
  overview: ["overview"] as const,
  health: ["system", "health"] as const,
  status: ["system", "status"] as const,
  channels: ["channels"] as const,
  subjects: ["subjects"] as const,
  files: (params: object) => ["files", params] as const,
  file: (id: number) => ["file", id] as const,
  facets: ["files", "facets"] as const,
  messages: (params: object) => ["messages", params] as const,
  runs: (params: object) => ["runs", params] as const,
  run: (id: number) => ["run", id] as const,
  jobs: ["jobs"] as const,
  lock: ["jobs", "lock"] as const,
  settings: ["settings"] as const,
};

export function errorMessage(err: unknown, fallback = "Error"): string {
  if (err instanceof ApiError) return err.status === 0 ? fallback : err.message;
  if (err instanceof Error) return err.message;
  return fallback;
}

// ------------------------------------------------------------------ auth
export function useMe() {
  return useQuery({
    queryKey: qk.me,
    queryFn: async () => {
      const me = await api.get<Me>("/auth/me");
      setCsrfToken(me.csrf_token);
      return me;
    },
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { username: string; password: string }) => api.post<Me>("/auth/login", body),
    onSuccess: (me) => {
      setCsrfToken(me.csrf_token);
      qc.setQueryData(qk.me, me);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSettled: () => {
      setCsrfToken(null);
      qc.clear();
    },
  });
}

// ------------------------------------------------------------------ reads
export const useOverview = () =>
  useQuery({ queryKey: qk.overview, queryFn: () => api.get<Overview>("/overview"), refetchInterval: 30_000 });

export const useHealth = () =>
  useQuery({
    queryKey: qk.health,
    queryFn: () => api.get<{ checks: HealthCheck[]; checked_at: string }>("/system/health"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

export const useSystemStatus = () =>
  useQuery({
    queryKey: qk.status,
    queryFn: () => api.get<SystemStatus>("/system/status"),
    refetchInterval: 10_000,
  });

export const useChannels = () => useQuery({ queryKey: qk.channels, queryFn: () => api.get<Channel[]>("/channels") });
export const useSubjects = () => useQuery({ queryKey: qk.subjects, queryFn: () => api.get<Subject[]>("/subjects") });

export interface FileParams {
  q?: string;
  status?: string;
  subject?: string;
  content_type?: string;
  extension?: string;
  channel_id?: number;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page: number;
  page_size: number;
}

export const useFiles = (params: FileParams) =>
  useQuery({
    queryKey: qk.files(params),
    queryFn: ({ signal }) => api.get<Page<FileItem>>("/files", { ...params }, signal),
    placeholderData: keepPreviousData,
  });

export const useFacets = () => useQuery({ queryKey: qk.facets, queryFn: () => api.get<Facets>("/files/facets") });

export const useFile = (id: number | null) =>
  useQuery({
    queryKey: qk.file(id ?? 0),
    queryFn: () => api.get<FileDetail>(`/files/${id}`),
    enabled: id !== null,
  });

export interface MessageParams {
  q?: string;
  channel_id?: number;
  media_type?: string;
  page: number;
  page_size: number;
}
export const useMessages = (params: MessageParams) =>
  useQuery({
    queryKey: qk.messages(params),
    queryFn: ({ signal }) => api.get<Page<MessageItem>>("/messages", { ...params }, signal),
    placeholderData: keepPreviousData,
  });

export const useRuns = (params: { kind?: string; page: number; page_size: number }) =>
  useQuery({
    queryKey: qk.runs(params),
    queryFn: () => api.get<Page<Run>>("/runs", { ...params }),
    placeholderData: keepPreviousData,
    refetchInterval: 15_000,
  });

export const useRun = (id: number) =>
  useQuery({
    queryKey: qk.run(id),
    queryFn: () => api.get<RunDetail>(`/runs/${id}`),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });

export const useLock = () =>
  useQuery({ queryKey: qk.lock, queryFn: () => api.get<LockInfo>("/jobs/lock"), refetchInterval: 4000 });

export const useJobs = () => useQuery({ queryKey: qk.jobs, queryFn: () => api.get<Job[]>("/jobs"), refetchInterval: 10_000 });

export const useSettings = () =>
  useQuery({
    queryKey: qk.settings,
    queryFn: () => api.get<{ sections: Record<string, SettingRow[]> }>("/settings"),
  });

// ------------------------------------------------------------------ writes
export function useInvalidateData() {
  const qc = useQueryClient();
  return () =>
    Promise.all(
      ["overview", "files", "file", "channels", "subjects", "messages", "runs", "system"].map((k) =>
        qc.invalidateQueries({ queryKey: [k] }),
      ),
    );
}

export function useStartJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { kind: "collect" | "process" | "reclassify"; channel?: string; limit?: number }) =>
      api.post<Job>("/jobs", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.lock });
      qc.invalidateQueries({ queryKey: qk.jobs });
    },
  });
}

export function useSaveChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id?: number; name: string; username?: string | null; telegram_id?: number | null; enabled: boolean; last_message_id?: number }) =>
      id ? api.patch<Channel>(`/channels/${id}`, body) : api.post<Channel>("/channels", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.channels }),
  });
}

export function useToggleChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => api.patch<Channel>(`/channels/${id}`, { enabled }),
    onMutate: async ({ id, enabled }) => {
      await qc.cancelQueries({ queryKey: qk.channels });
      const prev = qc.getQueryData<Channel[]>(qk.channels);
      qc.setQueryData<Channel[]>(qk.channels, (old) => old?.map((c) => (c.id === id ? { ...c, enabled } : c)));
      return { prev };
    },
    onError: (err, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(qk.channels, ctx.prev);
      toast.error(errorMessage(err));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: qk.channels }),
  });
}

export function useDeleteChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/channels/${id}`),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useSaveSubject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, code, ...body }: { id?: number; code: string; name_ar: string; name_en: string; keywords: string[] }) =>
      id ? api.patch<Subject>(`/subjects/${id}`, body) : api.post<Subject>("/subjects", { code, ...body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.subjects });
      qc.invalidateQueries({ queryKey: qk.facets });
    },
  });
}

export function useDeleteSubject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/subjects/${id}`, { force: true }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useFileAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, body }: { id: number; action: "reprocess" | "classify" | "reveal"; body?: unknown }) =>
      api.post<FileItem | undefined>(`/files/${id}/${action}`, body),
    onSuccess: (_d, { id, action }) => {
      if (action === "reveal") return;
      qc.invalidateQueries({ queryKey: qk.file(id) });
      qc.invalidateQueries({ queryKey: ["files"] });
      qc.invalidateQueries({ queryKey: qk.overview });
      qc.invalidateQueries({ queryKey: qk.subjects });
    },
  });
}
