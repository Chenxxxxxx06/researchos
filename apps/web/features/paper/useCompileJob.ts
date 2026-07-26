'use client';

/**
 * Compile driver (partition: frontend-paper, Design E.1).
 *
 * The mock engine returns a terminal job synchronously; a future async engine
 * publishes `latex.compile.*` (subscribed in PaperWorkspace) and this hook polls
 * `GET /compile-jobs/{id}` every 2 s (≤60 s) as the WS-outage fallback.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { compile as compileApi, getCompileJob, type CompileJob } from '@/lib/api/documents';

const POLL_MS = 2000;
const MAX_POLLS = 30;

function isTerminal(job: CompileJob): boolean {
  return job.status === 'succeeded' || job.status === 'failed';
}

export function useCompileJob(projectId: string, latexProjectId: string | undefined) {
  const [job, setJob] = useState<CompileJob | null>(null);
  const [isCompiling, setIsCompiling] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const poll = useCallback(
    (jobId: string) => {
      if (!latexProjectId) return;
      let count = 0;
      stopPolling();
      pollRef.current = setInterval(async () => {
        count += 1;
        try {
          const next = await getCompileJob(projectId, latexProjectId, jobId);
          setJob(next);
          if (isTerminal(next) || count >= MAX_POLLS) {
            stopPolling();
            setIsCompiling(false);
          }
        } catch {
          if (count >= MAX_POLLS) {
            stopPolling();
            setIsCompiling(false);
          }
        }
      }, POLL_MS);
    },
    [projectId, latexProjectId, stopPolling],
  );

  const compile = useCallback(async () => {
    if (!latexProjectId) return;
    setIsCompiling(true);
    try {
      const started = await compileApi(projectId, latexProjectId);
      setJob(started);
      if (isTerminal(started)) {
        setIsCompiling(false);
      } else {
        poll(started.id);
      }
    } catch {
      setIsCompiling(false);
    }
  }, [projectId, latexProjectId, poll]);

  /** Refetch the current job (used when a `latex.compile.*` event arrives). */
  const refetch = useCallback(async () => {
    if (!latexProjectId || !job) return;
    try {
      const next = await getCompileJob(projectId, latexProjectId, job.id);
      setJob(next);
      if (isTerminal(next)) setIsCompiling(false);
    } catch {
      // ignore — polling covers it
    }
  }, [projectId, latexProjectId, job]);

  return { job, isCompiling, compile, refetch };
}
