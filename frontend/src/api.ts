import type { JobPublic, SettingsPublic, SystemStatusResponse, UploadEntry } from "./types";

const API = "";

export async function fetchSettings(): Promise<SettingsPublic> {
  const r = await fetch(`${API}/api/settings`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchSystemStatus(): Promise<SystemStatusResponse> {
  const r = await fetch(`${API}/api/status`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function uploadFiles(files: File[]): Promise<UploadEntry[]> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  const r = await fetch(`${API}/api/upload`, { method: "POST", body: fd });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  const data = await r.json();
  return data.uploads as UploadEntry[];
}

export async function createJobs(payload: {
  items: { upload_id: string; original_filename: string }[];
  output_format: string;
  quality: string;
  advanced?: Record<string, string>;
}): Promise<JobPublic[]> {
  const r = await fetch(`${API}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  const data = await r.json();
  return data.jobs as JobPublic[];
}

export async function listJobs(): Promise<JobPublic[]> {
  const r = await fetch(`${API}/api/jobs`);
  if (!r.ok) throw new Error(await r.text());
  const data = await r.json();
  return data.jobs as JobPublic[];
}

export async function deleteJob(jobId: string): Promise<void> {
  const r = await fetch(`${API}/api/jobs/${jobId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
}

export async function cancelJob(jobId: string): Promise<void> {
  const r = await fetch(`${API}/api/jobs/${jobId}/cancel`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
}

export function downloadUrl(jobId: string): string {
  return `${API}/api/jobs/${jobId}/download`;
}

export function zipUrl(ids: string[]): string {
  const q = ids.join(",");
  return `${API}/api/jobs/download-zip?ids=${encodeURIComponent(q)}`;
}
