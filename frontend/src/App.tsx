import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  cancelJob,
  createJobs,
  deleteJob,
  downloadUrl,
  listJobs,
  uploadFiles,
  zipUrl,
} from "./api";
import { t, type Lang } from "./i18n";
import type { JobPublic, JobStatus } from "./types";

function readTheme(): "light" | "dark" {
  const v = localStorage.getItem("theme");
  if (v === "dark" || v === "light") return v;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readLang(): Lang {
  const v = localStorage.getItem("lang");
  return v === "ru" ? "ru" : "en";
}

function terminal(s: JobStatus): boolean {
  return s === "completed" || s === "failed" || s === "cancelled";
}

function fmtBytes(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function fmtDur(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec)) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

function statusLabel(lang: Lang, s: JobStatus): string {
  switch (s) {
    case "queued":
    case "uploading":
      return t(lang, "queued");
    case "analyzing":
      return t(lang, "analyzing");
    case "converting":
      return t(lang, "converting");
    case "finalizing":
      return t(lang, "finalizing");
    case "completed":
      return t(lang, "completed");
    case "failed":
      return t(lang, "failed");
    case "cancelled":
      return t(lang, "cancelled");
    default:
      return s;
  }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(readLang);
  const [theme, setTheme] = useState<"light" | "dark">(readTheme);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<{ id: number; text: string }[]>([]);

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [format, setFormat] = useState("mp4");
  const [quality, setQuality] = useState("balanced");
  const [res, setRes] = useState("original");
  const [fps, setFps] = useState("keep");
  const [audio, setAudio] = useState("keep");

  const [jobsById, setJobsById] = useState<Record<string, JobPublic>>({});
  const sourcesRef = useRef<Map<string, EventSource>>(new Map());
  const toastId = useRef(1);
  const langRef = useRef(lang);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("lang", lang);
    langRef.current = lang;
  }, [lang]);

  useEffect(() => {
    listJobs()
      .then((list) => {
        const m: Record<string, JobPublic> = {};
        for (const j of list) m[j.job_id] = j;
        setJobsById(m);
      })
      .catch(() => {});
  }, []);

  const jobs = useMemo(() => Object.values(jobsById).sort((a, b) => (a.created_at < b.created_at ? 1 : -1)), [jobsById]);

  useEffect(() => {
    const active = new Set<string>();
    for (const j of Object.values(jobsById)) {
      if (!terminal(j.status)) active.add(j.job_id);
    }
    for (const [id, es] of sourcesRef.current.entries()) {
      if (!active.has(id)) {
        es.close();
        sourcesRef.current.delete(id);
      }
    }
    for (const id of active) {
      if (sourcesRef.current.has(id)) continue;
      const es = new EventSource(`/api/jobs/${id}/events`);
      es.addEventListener("job", (ev) => {
        const data = JSON.parse((ev as MessageEvent).data) as JobPublic;
        setJobsById((prev) => {
          const prevJ = prev[data.job_id];
          const next = { ...prev, [data.job_id]: data };
          if (prevJ && terminal(prevJ.status) === false && terminal(data.status)) {
            const L = langRef.current;
            if (data.status === "completed") pushToast(t(L, "toastDone") + `: ${data.original_filename}`);
            if (data.status === "failed") pushToast(t(L, "toastFail") + `: ${data.error_message ?? ""}`);
          }
          return next;
        });
      });
      es.addEventListener("error", () => {
        /* browser auto-retries; ignore */
      });
      sourcesRef.current.set(id, es);
    }
    return () => {
      // keep connections while component mounted; cleanup on unmount
    };
  }, [jobsById]);

  useEffect(() => {
    return () => {
      for (const es of sourcesRef.current.values()) es.close();
      sourcesRef.current.clear();
    };
  }, []);

  function pushToast(text: string) {
    const id = toastId.current++;
    setToasts((xs) => [...xs, { id, text }]);
    window.setTimeout(() => {
      setToasts((xs) => xs.filter((t) => t.id !== id));
    }, 4500);
  }

  function onPickFiles(fs: FileList | null) {
    if (!fs || fs.length === 0) return;
    const arr = Array.from(fs).filter((f) => f.name.toLowerCase().endsWith(".webm"));
    setPendingFiles((p) => [...p, ...arr]);
  }

  async function onConvert() {
    setError(null);
    if (pendingFiles.length === 0) {
      setError("Add at least one .webm file.");
      return;
    }
    setBusy(true);
    try {
      const uploads = await uploadFiles(pendingFiles);
      const items = uploads.map((u) => ({
        upload_id: u.upload_id,
        original_filename: u.original_filename,
      }));
      const created = await createJobs({
        items,
        output_format: format,
        quality,
        advanced: {
          resolution: res,
          fps,
          audio,
          overwrite: "rename",
        },
      });
      setPendingFiles([]);
      setJobsById((prev) => {
        const next = { ...prev };
        for (const j of created) next[j.job_id] = j;
        return next;
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(jobId: string) {
    setError(null);
    try {
      await deleteJob(jobId);
      setJobsById((prev) => {
        const n = { ...prev };
        delete n[jobId];
        return n;
      });
    } catch (e) {
      setError(String(e));
    }
  }

  async function onCancel(jobId: string) {
    setError(null);
    try {
      await cancelJob(jobId);
    } catch (e) {
      setError(String(e));
    }
  }

  const completedIds = jobs.filter((j) => j.status === "completed").map((j) => j.job_id);

  const aviWarn = format === "avi";
  const gifWarn = format === "gif";

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>{t(lang, "title")}</h1>
          <p className="muted">{t(lang, "subtitle")}</p>
        </div>
        <div className="toolbar" style={{ justifyContent: "flex-end" }}>
          <button className="btn" type="button" onClick={() => setTheme((x) => (x === "dark" ? "light" : "dark"))}>
            {theme === "dark" ? t(lang, "light") : t(lang, "dark")}
          </button>
          <label className="muted" style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {t(lang, "lang")}
            <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
              <option value="en">English</option>
              <option value="ru">Русский</option>
            </select>
          </label>
          <Link className="link" to="/status-page">
            {t(lang, "statusPage")}
          </Link>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}
      {aviWarn && <div className="banner warn">{t(lang, "aviWarn")}</div>}
      {gifWarn && <div className="banner warn">{t(lang, "gifWarn")}</div>}

      <section className="card" style={{ marginBottom: 14 }}>
        <div
          className="drop"
          onDragOver={(e) => {
            e.preventDefault();
            e.currentTarget.classList.add("drag");
          }}
          onDragLeave={(e) => e.currentTarget.classList.remove("drag")}
          onDrop={(e) => {
            e.preventDefault();
            e.currentTarget.classList.remove("drag");
            onPickFiles(e.dataTransfer.files);
          }}
        >
          <p style={{ margin: 0, fontWeight: 750 }}>{t(lang, "drop")}</p>
          <p className="muted" style={{ marginTop: 8 }}>
            {t(lang, "or")}
          </p>
          <div style={{ marginTop: 10 }}>
            <input type="file" accept=".webm,video/webm" multiple onChange={(e) => onPickFiles(e.target.files)} />
          </div>
        </div>

        {pendingFiles.length > 0 && (
          <div style={{ marginTop: 12 }} className="muted">
            <strong style={{ color: "var(--fg)" }}>{pendingFiles.length}</strong> file(s) selected
          </div>
        )}

        <div className="row" style={{ marginTop: 14 }}>
          <div>
            <label>{t(lang, "format")}</label>
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="mp4">mp4</option>
              <option value="mkv">mkv</option>
              <option value="avi">avi</option>
              <option value="mov">mov</option>
              <option value="mpeg">mpeg</option>
              <option value="gif">gif</option>
            </select>
          </div>
          <div>
            <label>{t(lang, "quality")}</label>
            <select value={quality} onChange={(e) => setQuality(e.target.value)}>
              <option value="source_like">source-like</option>
              <option value="high">high</option>
              <option value="balanced">balanced</option>
              <option value="small">small</option>
            </select>
          </div>
        </div>

        <details className="adv">
          <summary>{t(lang, "advanced")}</summary>
          <div className="row" style={{ marginTop: 12 }}>
            <div>
              <label>{t(lang, "res")}</label>
              <select value={res} onChange={(e) => setRes(e.target.value)}>
                <option value="original">original</option>
                <option value="1080p">1080p</option>
                <option value="720p">720p</option>
                <option value="480p">480p</option>
              </select>
            </div>
            <div>
              <label>{t(lang, "fps")}</label>
              <select value={fps} onChange={(e) => setFps(e.target.value)}>
                <option value="keep">keep</option>
                <option value="30">30</option>
                <option value="25">25</option>
                <option value="24">24</option>
              </select>
            </div>
            <div>
              <label>{t(lang, "audio")}</label>
              <select value={audio} onChange={(e) => setAudio(e.target.value)}>
                <option value="keep">keep</option>
                <option value="remove">remove</option>
              </select>
            </div>
          </div>
        </details>

        <div style={{ marginTop: 14 }}>
          <button className="btn primary" type="button" disabled={busy || pendingFiles.length === 0} onClick={onConvert}>
            {t(lang, "convert")}
          </button>
        </div>
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <h2 style={{ margin: 0 }}>{t(lang, "jobs")}</h2>
          {completedIds.length > 1 && (
            <a className="link" href={zipUrl(completedIds)}>
              {t(lang, "zip")}
            </a>
          )}
        </div>

        {jobs.length === 0 && <p className="muted">{t(lang, "noJobs")}</p>}

        {jobs.map((j) => (
          <div key={j.job_id} className="job">
            <div className="jobTop">
              <p className="jobTitle">{j.original_filename}</p>
              <span className="pill">
                {j.output_format.toUpperCase()} · {statusLabel(lang, j.status)}
              </span>
            </div>
            {j.media_summary && (
              <p className="muted" style={{ margin: "8px 0 0", fontSize: 13 }}>
                {j.media_summary.width}×{j.media_summary.height}
                {j.media_summary.fps ? ` · ${j.media_summary.fps} fps` : ""}
                {j.media_summary.duration_sec ? ` · ${fmtDur(j.media_summary.duration_sec)}` : ""}
                {j.media_summary.has_audio ? "" : " · no audio"}
              </p>
            )}
            {j.progress?.message && <p className="muted" style={{ marginTop: 8 }}>{j.progress.message}</p>}
            <div className="bar" aria-hidden>
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, j.progress?.percent ?? (terminal(j.status) ? 100 : 5)))}%`,
                }}
              />
            </div>
            <div className="meta">
              <div>
                {t(lang, "sourceSize")}: {fmtBytes(j.source_size_bytes)}
              </div>
              <div>
                {t(lang, "resultSize")}: {fmtBytes(j.result_size_bytes)}
              </div>
              <div>
                {t(lang, "eta")}: {j.progress?.eta_sec != null ? fmtDur(j.progress.eta_sec) : "—"}
              </div>
            </div>
            {j.error_message && (
              <div className="banner error" style={{ marginTop: 10 }}>
                <strong>{t(lang, "errorTitle")}:</strong> {j.error_message}
              </div>
            )}
            <div className="actions">
              {j.status === "completed" && (
                <a className="btn primary" href={downloadUrl(j.job_id)}>
                  {t(lang, "download")}
                </a>
              )}
              {!terminal(j.status) && (
                <button className="btn danger" type="button" onClick={() => onCancel(j.job_id)}>
                  {t(lang, "cancel")}
                </button>
              )}
              <button className="btn" type="button" onClick={() => onDelete(j.job_id)}>
                {t(lang, "delete")}
              </button>
            </div>
          </div>
        ))}
      </section>

      <div className="toasts" aria-live="polite">
        {toasts.map((x) => (
          <div key={x.id} className="toast">
            {x.text}
          </div>
        ))}
      </div>
    </div>
  );
}
