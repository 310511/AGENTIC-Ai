"use client";

import { useRef, useState } from "react";
import { ingestDocument, uploadDocument } from "@/lib/api";

type Mode = "file" | "text";

interface Result { chunks_indexed: number; document_id: string }

const INPUT_CLS = "w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500";

export default function IngestForm({ token }: { token: string }) {
  const [mode, setMode]       = useState<Mode>("file");
  const [title, setTitle]     = useState("");
  const [docId, setDocId]     = useState("");
  const [content, setContent] = useState("");
  const [file, setFile]       = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [result, setResult]   = useState<Result | null>(null);
  const fileRef               = useRef<HTMLInputElement>(null);

  function pickFile(f: File) {
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) pickFile(f);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      let res: Result;
      if (mode === "file") {
        if (!file) throw new Error("Select a file first");
        res = await uploadDocument(token, file, title, docId || undefined);
      } else {
        res = await ingestDocument(token, {
          document_id: docId || crypto.randomUUID(),
          title,
          content,
        });
      }
      setResult(res);
      setFile(null);
      setContent("");
      setTitle("");
      setDocId("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl bg-gray-900 p-5 shadow space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Ingest Document</h2>
        {/* mode toggle */}
        <div className="flex rounded-lg overflow-hidden border border-gray-700 text-xs">
          {(["file", "text"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(null); setResult(null); }}
              className={`px-3 py-1.5 capitalize transition-colors ${
                mode === m ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {m === "file" ? "📄 File Upload" : "✏️ Paste Text"}
            </button>
          ))}
        </div>
      </div>

      <p className="text-sm text-gray-400">
        {mode === "file"
          ? "Upload a PDF or image — text is extracted automatically (OCR for scanned docs)."
          : "Paste text directly into the knowledge base."}
      </p>

      {error  && <p className="rounded bg-red-900/50 px-3 py-2 text-sm text-red-300">{error}</p>}
      {result && (
        <p className="rounded bg-green-900/50 px-3 py-2 text-sm text-green-300">
          ✓ Indexed <strong>{result.chunks_indexed}</strong> chunk{result.chunks_indexed !== 1 ? "s" : ""}.
          {" "}ID: <code className="text-xs">{result.document_id}</code>
        </p>
      )}

      {/* ── file drop zone ── */}
      {mode === "file" && (
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
            dragging ? "border-indigo-400 bg-indigo-900/20" : "border-gray-700 hover:border-gray-500"
          }`}
        >
          {file ? (
            <div className="space-y-1">
              <p className="text-sm font-medium text-indigo-300">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="text-xs text-red-400 hover:underline mt-1"
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-3xl">📂</p>
              <p className="text-sm text-gray-400">Drop a file here or <span className="text-indigo-400">browse</span></p>
              <p className="text-xs text-gray-600">PDF, PNG, JPG, TIFF, BMP, WEBP · max 50 MB</p>
            </div>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.webp"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); }}
          />
        </div>
      )}

      {/* ── title ── */}
      <div>
        <label className="mb-1 block text-sm text-gray-400">Title {mode === "file" && <span className="text-gray-600">(auto-filled from filename)</span>}</label>
        <input
          required
          placeholder="Document title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={INPUT_CLS}
        />
      </div>

      {/* ── text area (text mode only) ── */}
      {mode === "text" && (
        <div>
          <label className="mb-1 block text-sm text-gray-400">Content</label>
          <textarea
            required
            rows={10}
            placeholder="Paste document text here…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className={INPUT_CLS}
          />
        </div>
      )}

      {/* ── optional doc ID ── */}
      <div>
        <label className="mb-1 block text-sm text-gray-400">
          Document ID <span className="text-gray-600">(optional)</span>
        </label>
        <input
          placeholder="e.g. q4-report-2026 — leave blank to auto-generate"
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
          className={INPUT_CLS}
        />
      </div>

      <button
        type="submit"
        disabled={loading || (mode === "file" && !file)}
        className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-40"
      >
        {loading ? (mode === "file" ? "Extracting & indexing…" : "Indexing…") : "Ingest Document"}
      </button>
    </form>
  );
}
