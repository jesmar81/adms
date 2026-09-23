"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

export interface DropdownItem {
  label: string;
  icon?: ReactNode;
  danger?: boolean;
  onSelect: () => void;
}

interface DropdownProps {
  trigger: ReactNode;
  label: string;
  items: DropdownItem[];
  align?: "left" | "right";
}

export function Dropdown({ trigger, label, items, align = "right" }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open ]);

  return (
    <div ref={ref} className="relative">
      <button
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 items-center gap-2 rounded-lg transition-colors duration-200 hover:bg-surface-hover sm:min-h-0"
      >
        {trigger}
      </button>
      {open && (
        <div
          role="menu"
          aria-label={label}
          className={`absolute z-40 mt-2 w-52 animate-rise-in rounded-[10px] border border-line-soft bg-surface-card p-1 shadow-pop ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {items.map((item) => (
            <button
              key={item.label}
              role="menuitem"
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={`flex min-h-11 w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors duration-150 hover:bg-surface-hover sm:min-h-0 sm:py-1.5 ${
                item.danger ? "text-rose-300" : "text-foreground"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
