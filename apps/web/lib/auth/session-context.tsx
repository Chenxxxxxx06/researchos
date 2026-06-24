'use client';

import { useQuery } from '@tanstack/react-query';

import { getMe, type MeResponse } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';

/**
 * Session hook backed by GET /auth/me. The backend is authoritative; the
 * middleware cookie check is only a UX guard.
 */
export function useSession() {
  return useQuery<MeResponse, ApiError>({
    queryKey: ['me'],
    queryFn: getMe,
    retry: (failureCount, error) => {
      // Do not retry on auth failures.
      if (error instanceof ApiError && error.status === 401) return false;
      return failureCount < 1;
    },
  });
}
