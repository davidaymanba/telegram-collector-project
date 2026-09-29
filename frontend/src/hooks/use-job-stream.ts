import { useEffect, useRef, useState } from "react";
import type { Job, LogLine } from "@/lib/types";

const MAX_LINES = 3000;

export interface JobStream {
  lines: LogLine[];
  job: Job | null;
  connected: boolean;
  done: boolean;
  clear: () => void;
}

/** Subscribe to `/api/v1/jobs/{id}/stream` (Server-Sent Events). EventSource reconnects on its own. */
export function useJobStream(jobId: string | null, onEnd?: (job: Job) => void): JobStream {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const onEndRef = useRef(onEnd);
  onEndRef.current = onEnd;

  useEffect(() => {
    if (!jobId) return;
    setLines([]);
    setJob(null);
    setDone(false);
    const es = new EventSource(`/api/v1/jobs/${jobId}/stream`, { withCredentials: true });
    let buffer: LogLine[] = [];
    let frame = 0;
    const flush = () => {
      frame = 0;
      const batch = buffer;
      buffer = [];
      setLines((prev) => {
        const next = prev.concat(batch);
        return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
      });
    };
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.addEventListener("log", (e) => {
      buffer.push(JSON.parse((e as MessageEvent<string>).data) as LogLine);
      if (!frame) frame = requestAnimationFrame(flush);
    });
    es.addEventListener("status", (e) => setJob(JSON.parse((e as MessageEvent<string>).data) as Job));
    es.addEventListener("end", (e) => {
      const final = JSON.parse((e as MessageEvent<string>).data) as Job;
      setJob(final);
      setDone(true);
      setConnected(false);
      es.close();
      if (buffer.length) flush();
      onEndRef.current?.(final);
    });
    return () => {
      if (frame) cancelAnimationFrame(frame);
      es.close();
    };
  }, [jobId]);

  return { lines, job, connected, done, clear: () => setLines([]) };
}
