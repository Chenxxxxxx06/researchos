import { apiRequest } from './client';

export function createCodingRun(
  projectId: string,
  message: string,
): Promise<{ agent_run_id: string; status: string; stream: string }> {
  return apiRequest(`/projects/${projectId}/coding-agent/runs`, {
    method: 'POST',
    body: { message },
  });
}
