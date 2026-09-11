"use client";

import { ChevronDown } from "lucide-react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { useId } from "react";

const CONTROL =
  "w-full rounded-xl border border-line-soft bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm placeholder:text-zinc-400 transition-colors duration-200 hover:border-zinc-400/60 focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15 disabled:cursor-not-allowed disabled:opacity-50";

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
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium text-zinc-700">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-zinc-500">
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
      className={`${CONTROL} h-10 ${invalid ? "border-red-400" : ""} ${className}`}
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
      <select id={id} className={`${CONTROL} h-10 appearance-none pr-9 ${className}`} {...rest}>
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3 h-4 w-4 text-zinc-400"
      />
    </span>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  id?: string;
}

export function Textarea({ id, className = "", ...rest }: TextareaProps) {
  return <textarea id={id} className={`${CONTROL} min-h-[88px] resize-y ${className}`} {...rest} />;
}

export function SearchInput({
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      role="searchbox"
      className={`${CONTROL} h-10 ${className}`}
      {...rest}
    />
  );
}
