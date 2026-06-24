import { apiRequest } from './client';

export type OrgRole = 'member' | 'admin' | 'owner';

export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  role: OrgRole;
}

export interface MeResponse {
  user: User;
  organizations: OrganizationSummary[];
}

export interface RegisterResponse {
  user: User;
  organization: OrganizationSummary;
}

export function getMe(): Promise<MeResponse> {
  return apiRequest<MeResponse>('/auth/me');
}

export function login(email: string, password: string): Promise<User> {
  return apiRequest<User>('/auth/login', { method: 'POST', body: { email, password } });
}

export function register(
  email: string,
  password: string,
  display_name: string,
): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: { email, password, display_name },
  });
}

export function logout(): Promise<void> {
  return apiRequest<void>('/auth/logout', { method: 'POST' });
}
