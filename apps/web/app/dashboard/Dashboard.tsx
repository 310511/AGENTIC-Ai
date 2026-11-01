"use client";

import { useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import TaskList from "@/components/TaskList";
import NewTaskForm from "@/components/NewTaskForm";
import IngestForm from "@/components/IngestForm";

type Tab = "tasks" | "ingest";

export default function Dashboard({ session }: { session: Session }) {
  const [tab, setTab] = useState<Tab>("tasks");

  return (
    <div className="flex h-screen flex-col">
      {/* ── Header ── */}
      <header className="flex items-center justify-between border-b border-gray-800 px-6 py-3">
        <span className="font-semibold tracking-tight">AI Agent Platform</span>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{session.user.email}</span>
          <button
            onClick={() => supabase.auth.signOut()}
            className="rounded bg-gray-800 px-3 py-1 text-xs hover:bg-gray-700"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* ── Tabs ── */}
      <nav className="flex gap-1 border-b border-gray-800 px-6 pt-2">
        {(["tasks", "ingest"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize rounded-t transition-colors ${
              tab === t
                ? "bg-gray-900 text-white border border-b-gray-900 border-gray-800"
                : "text-gray-400 hover:text-white"
            }`}
          >
            {t === "tasks" ? "Tasks" : "Ingest Document"}
          </button>
        ))}
      </nav>

      {/* ── Content ── */}
      <main className="flex-1 overflow-y-auto p-6">
        {tab === "tasks" && (
          <div className="mx-auto max-w-3xl space-y-6">
            <NewTaskForm token={session.access_token} />
            <TaskList token={session.access_token} />
          </div>
        )}
        {tab === "ingest" && (
          <div className="mx-auto max-w-2xl">
            <IngestForm token={session.access_token} />
          </div>
        )}
      </main>
    </div>
  );
}
