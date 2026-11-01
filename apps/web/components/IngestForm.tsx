"use client";

import { useState } from "react";
import { ingestDocument } from "@/lib/api";

export default function IngestForm({ token }: { token: string }) {
  const [docId, setDocId]   = useState("");
  const [title, setTitle]   = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [result, setResult] = useState<{ chunks_indexed: number } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await ingestDocument(token, {
        document_id: docId || crypto.randomUUID(),
        title,
        content,
      });
      setResult(res);
      setContent("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl bg-gray-900 p-5 shadow space-y-4">
      <h2 className="font-semibold">Ingest Document</h2>
      <p className="text-sm text-gray-400">
        Add a document to the knowledge base so the agent can retrieve it when planning tasks.
      </p>

      {error  && <p className="rounded bg-red-900/50 px-3 py-2 text-sm text-red-300">{error}</p>}
      {result && (
        <p className="rounded bg-green-900/50 px-3 py-2 text-sm text-green-300">
          Indexed {result.chunks_indexed} chunk{result.chunks_indexed !== 1 ? "s" : ""}.
        </p>
      )}

      <div>
        <label className="mb-1 block text-sm text-gray-400">
          Document ID <span className="text-gray-600">(optional — auto-generated if blank)</span>
        </label>
        <input
          placeholder="e.g. company-handbook-v2"
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
          className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm text-gray-400">Title</label>
        <input
          required
          placeholder="Document title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm text-gray-400">Content</label>
        <textarea
          required
          rows={10}
          placeholder="Paste document text here…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
      >
        {loading ? "Indexing…" : "Ingest Document"}
      </button>
    </form>
  );
}
