"use client";

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "border border-blue-300/20 bg-accent text-white shadow-[0_8px_22px_-12px_rgba(59,130,246,.9)] hover:bg-accent-hover active:brightness-95 disabled:bg-accent/50",
  secondary:
    "border border-line-subtle bg-surface-raised text-foreground shadow-sm hover:border-line-soft hover:bg-surface-hover active:bg-surface-hover disabled:opacity-50",
  ghost: "text-muted hover:bg-surface-hover hover:text-foreground active:bg-surface-hover disabled:opacity-50",
  danger:
    "border border-rose-500/25 bg-rose-500/10 text-rose-300 hover:bg-rose-500/15 active:bg-rose-500/20 disabled:opacity-50",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-2.5 text-[12px]",
  md: "h-9 px-3.5 text-[13px]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  children,
  disabled,
  className = "",
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={Boolean(disabled || loading)}
      className={`inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-all duration-150 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}
