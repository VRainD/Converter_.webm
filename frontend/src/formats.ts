export const INPUT_EXTENSIONS = [
  ".mp4",
  ".mov",
  ".avi",
  ".mkv",
  ".webm",
  ".wmv",
  ".flv",
  ".mpeg",
  ".mpg",
  ".m4v",
  ".3gp",
  ".ts",
  ".mts",
  ".m2ts",
  ".ogv",
  ".vob",
] as const;

export const VIDEO_OUTPUT_FORMATS = ["mp4", "mkv", "avi", "mov", "mpeg", "gif"] as const;
export const AUDIO_OUTPUT_FORMATS = ["mp3", "wav"] as const;

export function normalizeOutputFormat(value: string): string {
  const v = value.toLowerCase().trim();
  return v === "waw" ? "wav" : v;
}

export function isAudioOnlyOutput(fmt: string): boolean {
  return (AUDIO_OUTPUT_FORMATS as readonly string[]).includes(normalizeOutputFormat(fmt));
}

export function isAllowedInputFilename(name: string): boolean {
  const lower = name.toLowerCase();
  return INPUT_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export const INPUT_ACCEPT = INPUT_EXTENSIONS.join(",");
