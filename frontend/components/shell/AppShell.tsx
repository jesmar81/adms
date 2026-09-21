"use client";

import {
  ChevronsLeft,
  ChevronsRight,
  CalendarDays,
  Clock,
  Building2,
  Fingerprint,
  FileBarChart,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  ShieldCheck,
  Terminal,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { Breadcrumb } from "@/components/ui/page-header";
import type { Crumb } from "@/components/ui/page-header";
import { Dropdown } from "@/components/ui/dropdown";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  perm?: string;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

const NAV: NavSection[] = [
  {
    items: [{ href: "/dashboard", label: "Panel", icon: <LayoutDashboard className="h-[18px] w-[18px]" aria-hidden /> }],
  },
  {
    title: "Dispositivos",
    items: [
      { href: "/devices", label: "Relojes", icon: <Fingerprint className="h-[18px] w-[18px]" aria-hidden />, perm: "devices.read" },
      { href: "/commands", label: "Comandos", icon: <Terminal className="h-[18px] w-[18px]" aria-hidden />, perm: "commands.read" },
    ],
  },
  {
    title: "Organización",
    items: [
      { href: "/companies", label: "Empresas y sucursales", icon: <Building2 className="h-[18px] w-[18px]" aria-hidden />, perm: "companies.read" },
      { href: "/people", label: "Trabajadores", icon: <Users className="h-[18px] w-[18px]" aria-hidden />, perm: "people.read" },
      { href: "/work-schedules", label: "Horarios", icon: <Clock className="h-[18px] w-[18px]" aria-hidden />, perm: "schedules.read" },
      { href: "/holidays", label: "Feriados", icon: <CalendarDays className="h-[18px] w-[18px]" aria-hidden />, perm: "schedules.read" },
    ],
  },
  {
    title: "Asistencia",
    items: [
      { href: "/attendance", label: "Marcaciones", icon: <Clock className="h-[18px] w-[18px]" aria-hidden />, perm: "attendance.read" },
      { href: "/reports", label: "Reportes", icon: <FileBarChart className="h-[18px] w-[18px]" aria-hidden />, perm: "attendance.read" },
      { href: "/device-users", label: "Personal en reloj", icon: <Users className="h-[18px] w-[18px]" aria-hidden />, perm: "device_users.read" },
      { href: "/enrollments", label: "Enrolamientos", icon: <Fingerprint className="h-[18px] w-[18px]" aria-hidden />, perm: "enrollments.read" },
    ],
  },
  {
    title: "Sistema",
    items: [
      { href: "/users", label: "Usuarios", icon: <ShieldCheck className="h-[18px] w-[18px]" aria-hidden />, perm: "users.read" },
      { href: "/audit", label: "Auditoría", icon: <ScrollText className="h-[18px] w-[18px]" aria-hidden />, perm: "audit.read" },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

const CRUMB_TITLES: Record<string, string> = {
  dashboard: "Panel",
  devices: "Relojes",
  commands: "Comandos",
  attendance: "Marcaciones",
  reports: "Reportes",
  "device-users": "Personal en reloj",
  companies: "Empresas y sucursales",
  people: "Trabajadores",
  "work-schedules": "Horarios",
  holidays: "Feriados",
  enrollments: "Enrolamientos",
  users: "Usuarios",
  audit: "Auditoría",
};

function crumbsFor(pathname: string): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [];
  let href = "";
  for (const part of parts) {
    href += `/${part}`;
    const title = CRUMB_TITLES[part] ?? (part.length > 12 ? `${part.slice(0, 8)}…` : part);
    crumbs.push({ label: title, href });
  }
  return crumbs;
}

function NavList({ collapsed, onNavigate, can }: { collapsed: boolean; onNavigate?: () => void; can: (p: string) => boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Principal" className="flex flex-col gap-5 px-3">
      {NAV.map((section, i) => {
        const items = section.items.filter((item) => !item.perm || can(item.perm));
        if (items.length === 0) return null;
        return (
          <div key={section.title ?? `top-${i}`}>
            {section.title && !collapsed && (
              <p className="mb-1.5 px-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-400">
                {section.title}
              </p>
            )}
            <ul className="flex flex-col gap-0.5">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={`group relative flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition-colors duration-200 ${
                        collapsed ? "justify-center" : ""
                      } ${
                        active
                          ? "bg-black/[0.06] font-medium text-zinc-900"
                          : "text-zinc-500 hover:bg-black/[0.04] hover:text-zinc-900"
                      }`}
                    >
                      <span className={active ? "text-accent" : "text-zinc-400 group-hover:text-zinc-600"}>
                        {item.icon}
                      </span>
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 px-5" aria-label="ZKTeco ADMS — Panel">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-zinc-900 text-sm font-bold text-white">
        Z
      </span>
      {!collapsed && (
        <span className="truncate text-[15px] font-semibold tracking-tight text-zinc-900">
          ZKTeco <span className="font-normal text-zinc-400">ADMS</span>
        </span>
      )}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout, can } = useAuth();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem("adms:sidebar") === "collapsed");
    } catch {
      /* sin persistencia */
    }
  }, []);

  function toggleCollapse() {
    setCollapsed((prev) => {
      try {
        window.localStorage.setItem("adms:sidebar", prev ? "expanded" : "collapsed");
      } catch {
        /* sin persistencia */
      }
      return !prev;
    });
  }

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawer(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  const pathname = usePathname();
  const initial = (user?.username ?? "?").slice(0, 1).toUpperCase();

  return (
    <div className="min-h-screen">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:shadow-pop"
      >
        Saltar al contenido
      </a>

      {/* Sidebar escritorio */}
      <aside
        aria-label="Navegación principal"
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line-subtle bg-surface-sidebar/85 backdrop-blur-xl transition-[width] duration-200 lg:flex ${
          collapsed ? "w-[68px]" : "w-60"
        }`}
      >
        <div className="flex h-16 shrink-0 items-center">
          <Brand collapsed={collapsed} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pb-4 pt-2">
          <NavList collapsed={collapsed} can={can} />
        </div>
        <div className="shrink-0 border-t border-line-subtle p-3">
          <button
            onClick={toggleCollapse}
            aria-label={collapsed ? "Expandir menú" : "Colapsar menú"}
            aria-expanded={!collapsed}
            className="flex w-full items-center justify-center gap-2 rounded-xl px-2.5 py-2 text-sm text-zinc-400 transition-colors duration-200 hover:bg-black/[0.04] hover:text-zinc-700"
          >
            {collapsed ? (
              <ChevronsRight className="h-[18px] w-[18px]" aria-hidden />
            ) : (
              <>
                <ChevronsLeft className="h-[18px] w-[18px]" aria-hidden />
                <span>Colapsar</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Drawer móvil */}
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Cerrar menú"
            onClick={() => setDrawer(false)}
            className="absolute inset-0 animate-fade-in cursor-default bg-zinc-900/30 backdrop-blur-[2px]"
          />
          <aside
            aria-label="Navegación principal"
            className="absolute inset-y-0 left-0 flex w-[272px] animate-drawer-in flex-col bg-white shadow-pop"
          >
            <div className="flex h-16 shrink-0 items-center justify-between pr-3">
              <Brand collapsed={false} />
              <button
                onClick={() => setDrawer(false)}
                aria-label="Cerrar menú"
                className="rounded-full bg-black/[0.04] p-2 text-zinc-500 transition-colors duration-200 hover:bg-black/[0.08] hover:text-zinc-900"
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto pb-4 pt-2">
              <NavList collapsed={false} can={can} onNavigate={() => setDrawer(false)} />
            </div>
          </aside>
        </div>
      )}

      {/* Contenido */}
      <div
        className={`flex min-h-screen min-w-0 flex-col transition-[padding] duration-200 ${
          collapsed ? "lg:pl-[68px]" : "lg:pl-60"
        }`}
      >
        <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-line-subtle bg-surface-canvas/80 px-4 backdrop-blur-xl md:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={() => setDrawer(true)}
              aria-label="Abrir menú"
              className="rounded-full p-2 text-zinc-600 transition-colors duration-200 hover:bg-black/[0.05] lg:hidden"
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>
            <div className="min-w-0 truncate">
              <Breadcrumb items={crumbsFor(pathname)} />
            </div>
          </div>
          <Dropdown
            label="Menú de usuario"
            trigger={
              <span className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-2">
                <span
                  aria-hidden
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-[13px] font-semibold text-accent"
                >
                  {initial}
                </span>
                <span className="hidden max-w-32 truncate text-sm font-medium text-zinc-700 sm:block">
                  {user?.username ?? ""}
                </span>
              </span>
            }
            items={[
              {
                label: "Cerrar sesión",
                icon: <LogOut className="h-4 w-4" aria-hidden />,
                danger: true,
                onSelect: () => void signOut(),
              },
            ]}
          />
        </header>
        <main id="contenido" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
