"use client";

import { Eye, EyeOff, Fingerprint, Loader2, Lock, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const FIELD_LABEL = "mb-2 block text-[13px] font-medium text-zinc-300";
const FIELD_CONTROL =
  "h-12 w-full rounded-xl border border-white/10 bg-white/[0.05] pl-11 pr-4 text-[15px] text-zinc-100 placeholder:text-zinc-500 transition-colors duration-200 hover:border-white/20 focus:border-sky-400/60 focus:outline-none focus:ring-4 focus:ring-sky-400/15 disabled:cursor-not-allowed disabled:opacity-50";

export default function Page() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    router.replace("/dashboard");
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(`Demasiados intentos. Reintenta en ${err.retryAfter ?? "?"} s.`);
      } else if (err instanceof ApiError && err.status === 503) {
        setError("Servicio de autenticación no disponible. Inténtalo más tarde.");
      } else {
        setError("Credenciales inválidas. Verifica tu usuario y contraseña.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-[#0a0a0e] px-4 py-10 font-sans">
      {/* Fondo: negro sofisticado con profundidad sutil */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[#0a0a0e]" />
        <div className="absolute left-1/2 top-[-240px] h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-indigo-500/[0.07] blur-[140px]" />
        <div className="absolute bottom-[-280px] left-1/2 h-[460px] w-[720px] -translate-x-1/2 rounded-full bg-sky-500/[0.06] blur-[140px]" />
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage: "radial-gradient(rgba(255,255,255,0.055) 1px, transparent 1px)",
            backgroundSize: "26px 26px",
          }}
        />
      </div>

      <div className="relative w-full max-w-[420px] animate-rise-in">
        {/* Encabezado con branding integrado */}
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400 to-indigo-500 text-white shadow-pop">
            <Fingerprint className="h-7 w-7" aria-hidden />
          </span>
          <p className="mt-5 text-[15px] font-medium tracking-tight text-zinc-300">
            ZKTeco <span className="font-normal text-zinc-500">ADMS</span>
          </p>
          <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-tight text-white">
            Iniciar sesión
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-zinc-400">
            Plataforma de control de asistencia
          </p>
        </div>

        {/* Card del formulario */}
        <section className="rounded-3xl border border-white/10 bg-[#121217] p-8 shadow-pop">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <div>
              <label htmlFor="login-username" className={FIELD_LABEL}>
                Usuario
              </label>
              <span className="relative block">
                <User
                  aria-hidden
                  className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-zinc-500"
                />
                <input
                  id="login-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Tu nombre de usuario"
                  autoComplete="username"
                  required
                  minLength={3}
                  className={FIELD_CONTROL}
                />
              </span>
            </div>
            <div>
              <label htmlFor="login-password" className={FIELD_LABEL}>
                Contraseña
              </label>
              <span className="relative block">
                <Lock
                  aria-hidden
                  className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-zinc-500"
                />
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Tu contraseña"
                  autoComplete="current-password"
                  required
                  minLength={10}
                  className={`${FIELD_CONTROL} pr-12`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-pressed={showPassword}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-zinc-500 transition-colors duration-200 hover:bg-white/[0.06] hover:text-zinc-200"
                >
                  {showPassword ? (
                    <EyeOff className="h-[18px] w-[18px]" aria-hidden />
                  ) : (
                    <Eye className="h-[18px] w-[18px]" aria-hidden />
                  )}
                </button>
              </span>
            </div>
            {error && (
              <p
                role="alert"
                className="rounded-xl border border-red-500/25 bg-red-500/[0.08] px-4 py-3 text-[13px] leading-relaxed text-red-200"
              >
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="mt-2 flex h-12 w-full select-none items-center justify-center gap-2 rounded-xl bg-zinc-100 text-[15px] font-semibold text-zinc-950 transition-colors duration-200 hover:bg-white active:bg-zinc-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
              {busy ? "Iniciando sesión…" : "Iniciar sesión"}
            </button>
          </form>
        </section>
        <p className="mt-6 text-center text-xs leading-relaxed text-zinc-500">
          El acceso está protegido y auditado por el servidor.
        </p>
      </div>
    </main>
  );
}
