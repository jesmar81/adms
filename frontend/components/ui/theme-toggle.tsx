"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "dark" | "light";
const STORAGE_KEY = "adms:theme";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("theme-light", theme === "light");
  document.documentElement.style.colorScheme = theme;
}

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const next: Theme = saved === "light" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    setTheme(next);
  }

  const isLight = theme === "light";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isLight ? "Activar tema oscuro" : "Activar tema claro"}
      title={isLight ? "Tema oscuro" : "Tema claro"}
      className={`inline-flex items-center justify-center rounded-md border border-line-subtle bg-surface-raised text-muted transition-colors hover:border-line-soft hover:bg-surface-hover hover:text-foreground ${compact ? "h-11 w-11 sm:h-8 sm:w-8" : "h-11 gap-1.5 px-3 text-[12px] font-medium sm:h-8 sm:px-2.5"}`}
    >
      {isLight ? <Moon className="h-4 w-4" aria-hidden /> : <Sun className="h-4 w-4" aria-hidden />}
      {!compact && <span>{isLight ? "Oscuro" : "Claro"}</span>}
    </button>
  );
}
