"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { btnCls, inputCls } from "@/components/ui";

export default function Page() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    router.replace("/dashboard");
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(`Too many attempts. Retry in ${err.retryAfter ?? "?"}s.`);
      } else if (err instanceof ApiError && err.status === 503) {
        setError("Authentication service unavailable. Try again later.");
      } else {
        setError("Invalid credentials.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto mt-24 max-w-sm p-6">
      <h1 className="mb-4 text-2xl font-bold">ZKTeco ADMS — Login</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          aria-label="username"
          className={inputCls}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          autoComplete="username"
        />
        <input
          aria-label="password"
          className={inputCls}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoComplete="current-password"
        />
        {error && <p className="text-sm text-red-300">{error}</p>}
        <button disabled={busy} className={btnCls} type="submit">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
