import React, { useState, useRef } from "react";
import { motion } from "framer-motion";

export default function Home() {
  const [instaUrl, setInstaUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [method, setMethod] = useState("GET");
  const [cookiesFile, setCookiesFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

  function resetState() {
    setProgress(0);
    setStatus("idle");
    setDownloadUrl("");
    setError("");
    if (abortRef.current) {
      abortRef.current = null;
    }
  }

  function handleFileChange(e) {
    const f = e.target.files && e.target.files[0];
    setCookiesFile(f || null);
  }

  async function handleDownload(e) {
    e.preventDefault();
    setError("");
    setDownloadUrl("");

    if (!instaUrl) {
      setError("Masukkan URL Instagram Reels atau post publik dulu.");
      return;
    }

    resetState();
    setStatus("starting");

    try {
      const headers = {};
      if (username) headers["X-Username"] = username;
      if (password) headers["X-Password"] = password;

      let response;

      if (method === "POST" || cookiesFile) {
        const form = new FormData();
        if (cookiesFile) form.append("cookies", cookiesFile);
        // Insta URL is passed as query param as backend expects it there
        const controller = new AbortController();
        abortRef.current = controller;

        response = await fetch(`${API_BASE}/download?insta_url=${encodeURIComponent(instaUrl)}`, {
          method: "POST",
          headers,
          body: form,
          signal: controller.signal,
        });
      } else {
        const controller = new AbortController();
        abortRef.current = controller;

        const url = `${API_BASE}/download?insta_url=${encodeURIComponent(instaUrl)}`;
        response = await fetch(url, {
          method: "GET",
          headers,
          signal: controller.signal,
        });
      }

      if (!response.ok) {
        const txt = await response.text();
        throw new Error(`Server responded: ${response.status} - ${txt}`);
      }

      const contentLength = response.headers.get("Content-Length");
      const contentType = response.headers.get("Content-Type") || "application/octet-stream";
      const cd = response.headers.get("Content-Disposition") || "";

      let filename = "reel.mp4";
      if (cd && cd.includes("filename=")) {
        try {
          filename = cd.split("filename=")[1].replace(/\"|\'/g, "");
        } catch (err) {}
      }

      const reader = response.body && response.body.getReader ? response.body.getReader() : null;

      if (!reader) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);
        triggerDownload(url, filename);
        setStatus("done");
        return;
      }

      setStatus("downloading");

      const contentLengthNum = contentLength ? parseInt(contentLength, 10) : null;
      let received = 0;
      const chunks = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        if (contentLengthNum) {
          setProgress(Math.round((received / contentLengthNum) * 100));
        } else {
          setProgress((p) => Math.min(95, p + 2));
        }
      }

      const blob = new Blob(chunks, { type: contentType });
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      triggerDownload(url, filename);
      setProgress(100);
      setStatus("done");
    } catch (err) {
      if (err.name === "AbortError") {
        setError("Download dibatalkan.");
        setStatus("aborted");
      } else {
        setError(err.message || "Terjadi kesalahan saat mengunduh.");
        setStatus("error");
      }
    }
  }

  function triggerDownload(url, filename) {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "reel.mp4";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function handleCancel() {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch (e) {}
    }
    setStatus("aborting");
    setProgress(0);
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white flex items-center justify-center p-6">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-3xl w-full bg-white shadow-lg rounded-2xl p-8 grid gap-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Instagram Reels Downloader</h1>
            <p className="text-sm text-slate-500">Masukkan URL Reels/public post, opsional cookies atau login.</p>
          </div>
          <div className="text-xs text-slate-400">Frontend Demo</div>
        </header>

        <form onSubmit={handleDownload} className="grid gap-4">
          <div className="grid gap-1">
            <label className="text-sm font-medium">URL Instagram</label>
            <input value={instaUrl} onChange={(e) => setInstaUrl(e.target.value)} placeholder="https://www.instagram.com/reel/XXXXXXXX/" className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-slate-200" />
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Username (opsional)</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username untuk login" className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-slate-200" />
            </div>
            <div>
              <label className="text-sm font-medium">Password (opsional)</label>
              <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" type="password" className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-slate-200" />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="text-sm font-medium">Method:</label>
            <div className="flex gap-2">
              <button type="button" onClick={() => setMethod("GET")} className={`px-3 py-1 rounded-md border ${method === "GET" ? "bg-slate-100" : "bg-white"}`}>GET</button>
              <button type="button" onClick={() => setMethod("POST")} className={`px-3 py-1 rounded-md border ${method === "POST" ? "bg-slate-100" : "bg-white"}`}>POST</button>
            </div>
            <div className="ml-auto text-sm text-slate-400">Note: Use POST if uploading cookies file.</div>
          </div>

          <div>
            <label className="text-sm font-medium">Cookies file (cookies.txt, Netscape format, optional)</label>
            <input type="file" accept=".txt" onChange={handleFileChange} className="mt-2" />
            {cookiesFile && <div className="text-xs text-slate-500 mt-1">Loaded: {cookiesFile.name}</div>}
          </div>

          <div className="flex items-center gap-3">
            <button className="px-4 py-2 rounded-xl bg-slate-900 text-white font-medium shadow-sm hover:opacity-95" type="submit">{status === "downloading" ? "Downloading..." : "Download"}</button>

            <button type="button" onClick={handleCancel} className="px-3 py-2 rounded-xl border text-slate-700">Cancel</button>

            <div className="ml-auto text-sm text-slate-500">Status: <span className="font-medium">{status}</span></div>
          </div>

          {status !== "idle" && (
            <div className="w-full bg-slate-100 rounded-md h-3 overflow-hidden">
              <div className="h-full bg-slate-800" style={{ width: `${progress}%`, transition: "width 300ms ease" }} />
            </div>
          )}

          {downloadUrl && (
            <div className="flex items-center gap-3">
              <a href={downloadUrl} target="_blank" rel="noreferrer" className="text-sm underline">Buka file hasil download</a>
              <button className="px-3 py-1 rounded-md border" onClick={() => { triggerDownload(downloadUrl, "reel.mp4"); }}>Download ulang</button>
            </div>
          )}

          {error && <div className="text-red-600 text-sm">Error: {error}</div>}

          <div className="text-xs text-slate-400 mt-2">Tips: jika konten membutuhkan login, upload cookies.txt atau isi username/password. Pastikan backend mengizinkan CORS jika frontend dihost di domain berbeda.</div>
        </form>

        <footer className="text-xs text-slate-400 text-right">Built with FastAPI backend in mind — adjust <code>API_BASE</code> as needed.</footer>
      </motion.div>
    </div>
  );
}