"use client";

import { Eye, EyeOff, Fingerprint, Loader2, Lock, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const FIELD_LABEL = "mb-2 block text-[13px] font-medium text-foreground";
const FIELD_CONTROL =
  "h-12 w-full rounded-xl border border-line-subtle bg-surface-input pl-11 pr-4 text-[15px] text-foreground placeholder:text-muted transition-colors duration-200 hover:border-line-soft focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15 disabled:cursor-not-allowed disabled:opacity-50";

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
    <main className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-surface-canvas px-4 py-10 font-sans">
      {/* Fondo: negro sofisticado con profundidad sutil */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-surface-canvas" />
        <div className="absolute left-1/2 top-[-240px] h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-indigo-500/[0.10] blur-[140px]" />
        <div className="absolute bottom-[-280px] left-1/2 h-[460px] w-[720px] -translate-x-1/2 rounded-full bg-sky-500/[0.08] blur-[140px]" />
        <div
          className="absolute inset-0 opacity-[0.25]"
          style={{
            backgroundImage: "radial-gradient(rgba(255,255,255,0.055) 1px, transparent 1px)",
            backgroundSize: "26px 26px",
          }}
        />
      </div>

      <div className="absolute right-4 top-4 z-10"><ThemeToggle /></div>
      <div className="relative w-full max-w-[420px] animate-rise-in">
        {/* Encabezado con branding integrado */}
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400 to-indigo-500 text-white shadow-pop">
            <Fingerprint className="h-7 w-7" aria-hidden />
          </span>
          <p className="mt-5 text-[15px] font-medium tracking-tight text-foreground">
            ZKTeco <span className="font-normal text-muted">ADMS</span>
          </p>
          <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-tight text-foreground">
            Iniciar sesión
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Plataforma de control de asistencia
          </p>
        </div>

        {/* Card del formulario */}
        <section className="rounded-3xl border border-line-subtle bg-surface-card/90 p-8 shadow-pop backdrop-blur-sm">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <div>
              <label htmlFor="login-username" className={FIELD_LABEL}>
                Usuario
              </label>
              <span className="relative block">
                <User
                  aria-hidden
                  className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-muted"
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
                  className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-muted"
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
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-muted transition-colors duration-200 hover:bg-surface-hover hover:text-foreground"
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
              className="mt-2 flex h-12 w-full select-none items-center justify-center gap-2 rounded-xl border border-blue-300/20 bg-accent text-[15px] font-semibold text-white transition-colors duration-200 hover:bg-accent-hover active:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
              {busy ? "Iniciando sesión…" : "Iniciar sesión"}
            </button>
          </form>
        </section>
        <p className="mt-6 text-center text-xs leading-relaxed text-muted">
          El acceso está protegido y auditado por el servidor.
        </p>
      </div>
    </main>
  );
}
