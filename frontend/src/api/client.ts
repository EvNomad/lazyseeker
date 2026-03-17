import type { JobPosting, JobPostingWithCompany, UserProfile, Suggestion, CrawlLogEntry } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public body: string) {
    super(`HTTP ${status}: ${body}`);
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.json() as Promise<T>;
}

async function apiFetchText(path: string, options?: RequestInit): Promise<string> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.text();
}

export const getJobs = (params?: { min_score?: number; status?: string; language?: string }): Promise<JobPosting[]> => {
  const searchParams = new URLSearchParams();
  if (params) {
    if (params.min_score !== undefined) searchParams.set("min_score", String(params.min_score));
    if (params.status !== undefined) searchParams.set("status", params.status);
    if (params.language !== undefined) searchParams.set("language", params.language);
  }
  const query = searchParams.toString();
  return apiFetch<JobPosting[]>(`/jobs${query ? `?${query}` : ""}`);
};

export const getJob = (id: string): Promise<JobPostingWithCompany> =>
  apiFetch<JobPostingWithCompany>(`/jobs/${id}`);

export const patchJobStatus = (id: string, application_status: string): Promise<JobPosting> =>
  apiFetch<JobPosting>(`/jobs/${id}/status`, { method: "PATCH", body: JSON.stringify({ application_status }) });

export const retryScore = (id: string): Promise<{ score_status: string }> =>
  apiFetch<{ score_status: string }>(`/jobs/${id}/retry-score`, { method: "POST" });

export const tailorJob = (id: string): Promise<Suggestion[]> =>
  apiFetch<Suggestion[]>(`/jobs/${id}/tailor`, { method: "POST" });

export const getTailoredCv = (id: string): Promise<string> =>
  apiFetchText(`/jobs/${id}/tailored-cv`);

export const getProfile = (): Promise<UserProfile> =>
  apiFetch<UserProfile>("/profile");

export const putProfile = (data: { cv_markdown?: string; preferences?: string }): Promise<UserProfile> =>
  apiFetch<UserProfile>("/profile", { method: "PUT", body: JSON.stringify(data) });

export const getJobSuggestions = (jobId: string): Promise<{ suggestions: Suggestion[]; cv_version_current: string }> =>
  apiFetch<{ suggestions: Suggestion[]; cv_version_current: string }>(`/jobs/${jobId}/suggestions`);

export const patchSuggestion = (id: string, status: "approved" | "rejected"): Promise<Suggestion> =>
  apiFetch<Suggestion>(`/suggestions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });

export const postRadarRun = (): Promise<{ started: boolean }> =>
  apiFetch<{ started: boolean }>("/radar/run", { method: "POST" });

export const getRadarLog = (): Promise<CrawlLogEntry[]> =>
  apiFetch<CrawlLogEntry[]>("/radar/log");
