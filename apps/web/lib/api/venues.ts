import { apiRequest } from './client';

export interface VenueDeadline {
  uid: string;
  title: string;
  description: string | null;
  location: string | null;
  starts_at: string;
  ends_at: string | null;
  url: string | null;
}

export interface VenueDeadlineFeed {
  source_name: string;
  source_url: string;
  fetched_at: string;
  items: VenueDeadline[];
}

export function listVenueDeadlines(projectId: string): Promise<VenueDeadlineFeed> {
  return apiRequest(`/projects/${projectId}/venues/deadlines`);
}
