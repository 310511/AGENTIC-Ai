"use client";

import { useState } from "react";
import { createTask } from "@/lib/api";

export default function NewTaskForm({ token }: { token: string }) {
  const [title, setTitle]       = useState("");
  const [desc, setDesc]         = useState("");
  const [priority, setPriority] = useState("normal");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);
  const [success, setSuccess]   = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const res = await createTask(token, { title, description: desc, priority });
      if (!res.success) throw new Error(res.error?.message ?? "Failed");
      setSuccess(`Task submitted — ID: ${res.data!.id}`);
      setTitle("");
      setDesc("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl bg-gray-900 p-5 shadow"
    >
      <h2 className="mb-4 font-semibold">New Task</h2>

      {error   && <p className="mb-3 rounded bg-red-900/50 px-3 py-2 text-sm text-red-300">{error}</p>}
      {success && <p className="mb-3 rounded bg-green-900/50 px-3 py-2 text-sm text-green-300">{success}</p>}

      <input
        required
        placeholder="Title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="mb-3 w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <textarea
        required
        placeholder="Describe the task…"
        rows={3}
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        className="mb-3 w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <div className="flex items-center gap-3">
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none"
        >
          <option value="low">Low</option>
          <option value="normal">Normal</option>
          <option value="high">High</option>
        </select>
        <button
          type="submit"
          disabled={loading}
          className="ml-auto rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? "Submitting…" : "Submit"}
        </button>
      </div>
    </form>
  );
}
