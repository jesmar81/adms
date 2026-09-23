"use client";

import Link from "next/link";
import type { ReactNode } from "react";

export interface Crumb {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Migas de pan" className="flex items-center gap-1.5 text-[12px] text-muted">
      {items.map((item, i) => {
        const last = i === items.length - 1;
        return (
          <span key={item.label} className="flex items-center gap-1.5">
            {i > 0 && (
              <span aria-hidden className="text-muted/60">
                /
              </span>
            )}
            {item.href && !last ? (
              <Link href={item.href} className="transition-colors duration-150 hover:text-foreground">
                {item.label}
              </Link>
            ) : (
              <span aria-current={last ? "page" : undefined} className={last ? "text-foreground" : ""}>
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
    <div className="mb-6 border-b border-line-subtle pb-5">
      {crumbs && (
        <div className="mb-2.5">
          <Breadcrumb items={crumbs} />
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[24px] font-semibold tracking-tight text-foreground md:text-[27px]">{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
