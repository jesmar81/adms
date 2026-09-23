"use client";

import { ChevronDown } from "lucide-react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { useId } from "react";

const CONTROL =
  "w-full rounded-md border border-line-subtle bg-surface-input px-2.5 py-1.5 text-[13px] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,.025)] placeholder:text-muted transition-colors duration-150 hover:border-line-soft focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/15 disabled:cursor-not-allowed disabled:opacity-50";

interface FieldProps {
  label: string;
  hint?: string;
  error?: string | null;
  children: (id: string) => ReactNode;
}

export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] font-medium tracking-[0.01em] text-foreground">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-rose-400">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  id?: string;
  invalid?: boolean;
}

export function Input({ id, invalid, className = "", ...rest }: InputProps) {
  return (
    <input
      id={id}
      aria-invalid={invalid || undefined}
      className={`${CONTROL} h-11 sm:h-9 ${invalid ? "border-red-400" : ""} ${className}`}
      {...rest}
    />
  );
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  id?: string;
}

export function Select({ id, children, className = "", ...rest }: SelectProps) {
  return (
    <span className="relative inline-flex w-full items-center">
      <select id={id} className={`${CONTROL} h-11 appearance-none pr-8 sm:h-9 ${className}`} {...rest}>
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-2.5 h-3.5 w-3.5 text-muted"
      />
    </span>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  id?: string;
}

export function Textarea({ id, className = "", ...rest }: TextareaProps) {
  return <textarea id={id} className={`${CONTROL} min-h-24 resize-y ${className}`} {...rest} />;
}

export function SearchInput({
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      role="searchbox"
      className={`${CONTROL} h-11 sm:h-9 ${className}`}
      {...rest}
    />
  );
}
