import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSystemStatus } from "./api";
import type { SystemStatusResponse } from "./types";
import { t, type Lang } from "./i18n";

function readLang(): Lang {
  const v = localStorage.getItem("lang");
  return v === "ru" ? "ru" : "en";
}

export default function SystemStatus() {
  const [lang] = useState<Lang>(readLang);
  const [data, setData] = useState<SystemStatusResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchSystemStatus()
      .then(setData)
      .catch((e) => setErr(String(e)));
    const id = setInterval(() => {
      fetchSystemStatus().then(setData).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>{t(lang, "statusPage")}</h1>
          <p className="muted">WebM Converter</p>
        </div>
        <Link className="link" to="/">
          ← {t(lang, "home")}
        </Link>
      </header>
      {err && <div className="banner error">{err}</div>}
      {data && (
        <section className="card">
          <h2>FFmpeg</h2>
          <p>
            ffmpeg: {data.health.ffmpeg_available ? "OK" : "missing"} · ffprobe:{" "}
            {data.health.ffprobe_available ? "OK" : "missing"}
          </p>
          <h2>Limits</h2>
          <ul className="list">
            <li>Max upload: {data.settings.max_upload_mb} MB</li>
            <li>Concurrent jobs: {data.settings.max_concurrent_jobs}</li>
            <li>GIF max duration: {data.settings.gif_max_duration_sec}s</li>
          </ul>
          <h2>Queue</h2>
          <p>
            Active: {data.active_jobs} · Queued: {data.queued_jobs}
          </p>
        </section>
      )}
    </div>
  );
}
