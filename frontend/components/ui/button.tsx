"use client";

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-hover active:bg-accent-hover disabled:bg-accent/50",
  secondary:
    "border border-line-soft bg-white text-zinc-900 shadow-sm hover:bg-zinc-50 active:bg-zinc-100 disabled:opacity-50",
  ghost: "text-zinc-600 hover:bg-black/[0.05] hover:text-zinc-900 active:bg-black/[0.08] disabled:opacity-50",
  danger:
    "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 active:bg-red-100 disabled:opacity-50",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3.5 text-[13px]",
  md: "h-10 px-5 text-sm",
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
      className={`inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-colors duration-200 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}
