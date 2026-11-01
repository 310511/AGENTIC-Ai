"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";

export default function LoginPage() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);
  const [mode, setMode]         = useState<"signin" | "signup">("signin");
  const [sent, setSent]         = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setSent(true);
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="rounded-xl bg-gray-900 p-8 text-center shadow-xl">
          <p className="text-lg font-medium">Check your email</p>
          <p className="mt-2 text-sm text-gray-400">
            We sent a confirmation link to <strong>{email}</strong>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl bg-gray-900 p-8 shadow-xl"
      >
        <h1 className="mb-6 text-2xl font-bold">AI Agent Platform</h1>

        {error && (
          <p className="mb-4 rounded bg-red-900/50 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        <label className="mb-1 block text-sm text-gray-400">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
        />

        <label className="mb-1 block text-sm text-gray-400">Password</label>
        <input
          type="password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded-lg bg-gray-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? "…" : mode === "signin" ? "Sign in" : "Sign up"}
        </button>

        <p className="mt-4 text-center text-sm text-gray-500">
          {mode === "signin" ? "No account?" : "Already have one?"}{" "}
          <button
            type="button"
            className="text-indigo-400 hover:underline"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          >
            {mode === "signin" ? "Sign up" : "Sign in"}
          </button>
        </p>
      </form>
    </div>
  );
}
