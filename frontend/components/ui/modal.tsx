"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({ open, onClose, title, description, children, footer }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-2 sm:items-center sm:p-4">
      <button
        aria-label="Cerrar diálogo"
        onClick={onClose}
        className="absolute inset-0 animate-fade-in cursor-default bg-black/70 backdrop-blur-sm"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex max-h-[calc(100dvh-1rem)] w-full max-w-lg flex-col overflow-hidden rounded-[10px] border border-line-soft bg-surface-card p-4 shadow-pop sm:max-h-[calc(100dvh-2rem)] sm:p-5"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[17px] font-semibold tracking-tight text-foreground">{title}</h2>
            {description && <p className="mt-1 text-[13px] text-muted">{description}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Cerrar"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-surface-raised text-muted transition-colors duration-200 hover:bg-surface-hover hover:text-foreground sm:h-8 sm:w-8"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain text-foreground">{children}</div>
        {footer && <div className="mt-4 flex shrink-0 flex-wrap justify-end gap-2 border-t border-line-subtle pt-3 sm:mt-5 sm:border-0 sm:pt-0">{footer}</div>}
      </div>
    </div>
  );
}
