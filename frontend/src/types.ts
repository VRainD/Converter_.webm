export type JobStatus =
  | "queued"
  | "uploading"
  | "analyzing"
  | "converting"
  | "finalizing"
  | "completed"
  | "failed"
  | "cancelled";

export type OutputFormat = "mp4" | "mkv" | "avi" | "mov" | "mpeg" | "gif";
export type QualityProfile = "source_like" | "high" | "balanced" | "small";

export interface JobProgress {
  percent: number | null;
  stage: string;
  message: string;
  eta_sec: number | null;
  out_time_sec: number | null;
  speed: string | null;
}

export interface MediaSummary {
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  has_video: boolean;
  has_audio: boolean;
  video_codec: string | null;
  audio_codec: string | null;
  file_size_bytes: number;
}

export interface JobPublic {
  job_id: string;
  status: JobStatus;
  original_filename: string;
  source_size_bytes: number;
  output_format: OutputFormat;
  quality: QualityProfile;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  media_summary: MediaSummary | null;
  progress: JobProgress;
  result_filename: string | null;
  result_size_bytes: number | null;
  error_message: string | null;
  error_detail: string | null;
}

export interface UploadEntry {
  upload_id: string;
  original_filename: string;
  size_bytes: number;
}

export interface SettingsPublic {
  max_upload_mb: number;
  max_concurrent_jobs: number;
  enable_advanced_options: boolean;
  default_output_format: string;
  default_quality_profile: string;
  gif_max_duration_sec: number;
  supported_formats: string[];
}

export interface HealthResponse {
  status: string;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  version: string;
}

export interface SystemStatusResponse {
  health: HealthResponse;
  settings: SettingsPublic;
  active_jobs: number;
  queued_jobs: number;
}
