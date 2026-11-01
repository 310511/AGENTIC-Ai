"use client";

import useSWR from "swr";
import { listTasks, cancelTask, type Task } from "@/lib/api";
import { useState } from "react";

const STATUS_COLORS: Record<string, string> = {
  pending:            "bg-gray-700 text-gray-300",
  queued:             "bg-blue-900 text-blue-300",
  in_progress:        "bg-yellow-900 text-yellow-300",
  awaiting_approval:  "bg-orange-900 text-orange-300",
  completed:          "bg-green-900 text-green-300",
  failed:             "bg-red-900 text-red-300",
  cancelled:          "bg-gray-800 text-gray-500",
};

const ACTIVE = new Set(["pending", "queued", "in_progress", "awaiting_approval"]);

function TaskRow({ task, token, onCancel }: { task: Task; token: string; onCancel: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  async function handleCancel() {
    setCancelling(true);
    try { await cancelTask(token, task.id); onCancel(); }
    finally { setCancelling(false); }
  }

  return (
    <li className="rounded-lg bg-gray-900 p-4 shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{task.title}</p>
          <p className="mt-0.5 truncate text-sm text-gray-400">{task.description}</p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[task.status] ?? STATUS_COLORS.pending}`}>
            {task.status.replace("_", " ")}
          </span>
          {ACTIVE.has(task.status) && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="rounded bg-gray-800 px-2 py-0.5 text-xs hover:bg-red-900 disabled:opacity-50"
            >
              Cancel
            </button>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-500 hover:text-white"
          >
            {expanded ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2 text-sm">
          <p className="text-gray-500">ID: {task.id}</p>
          <p className="text-gray-500">
            Created: {new Date(task.created_at).toLocaleString()}
          </p>
          {task.result?.output && (
            <div className="rounded bg-gray-800 p-3 text-gray-200 whitespace-pre-wrap">
              {task.result.output}
            </div>
          )}
          {task.error_message && (
            <p className="rounded bg-red-900/40 px-3 py-2 text-red-300">
              {task.error_message}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

export default function TaskList({ token }: { token: string }) {
  const [page, setPage] = useState(1);

  // Poll every 5s so active tasks update automatically
  const { data, mutate } = useSWR(
    ["tasks", page, token],
    () => listTasks(token, page),
    { refreshInterval: 5000 }
  );

  const tasks = data?.data?.items ?? [];
  const total = data?.data?.total ?? 0;
  const pages = Math.ceil(total / 20);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Tasks</h2>
        <button
          onClick={() => mutate()}
          className="rounded bg-gray-800 px-3 py-1 text-xs hover:bg-gray-700"
        >
          Refresh
        </button>
      </div>

      {tasks.length === 0 ? (
        <p className="rounded-lg bg-gray-900 p-6 text-center text-sm text-gray-500">
          No tasks yet. Submit one above.
        </p>
      ) : (
        <ul className="space-y-3">
          {tasks.map((t) => (
            <TaskRow key={t.id} task={t} token={token} onCancel={() => mutate()} />
          ))}
        </ul>
      )}

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded bg-gray-800 px-3 py-1 disabled:opacity-40 hover:bg-gray-700"
          >
            ‹ Prev
          </button>
          <span className="text-gray-500">{page} / {pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            className="rounded bg-gray-800 px-3 py-1 disabled:opacity-40 hover:bg-gray-700"
          >
            Next ›
          </button>
        </div>
      )}
    </div>
  );
}
