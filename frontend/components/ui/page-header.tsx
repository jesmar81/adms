"use client";

import Link from "next/link";
import type { ReactNode } from "react";

export interface Crumb {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Migas de pan" className="flex items-center gap-1.5 text-[13px] text-zinc-400">
      {items.map((item, i) => {
        const last = i === items.length - 1;
        return (
          <span key={item.label} className="flex items-center gap-1.5">
            {i > 0 && (
              <span aria-hidden className="text-zinc-300">
                /
              </span>
            )}
            {item.href && !last ? (
              <Link href={item.href} className="transition-colors duration-150 hover:text-zinc-700">
                {item.label}
              </Link>
            ) : (
              <span aria-current={last ? "page" : undefined} className={last ? "text-zinc-700" : ""}>
                {item.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  crumbs?: Crumb[];
}

export function PageHeader({ title, description, actions, crumbs }: PageHeaderProps) {
  return (
    <div className="mb-7">
      {crumbs && (
        <div className="mb-2.5">
          <Breadcrumb items={crumbs} />
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 md:text-[28px]">{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-sm text-zinc-500">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
