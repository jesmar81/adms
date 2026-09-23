"use client";

import {
  Activity,
  Building2,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  Clock,
  FileBarChart,
  Fingerprint,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  ShieldCheck,
  Terminal,
  TimerReset,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Breadcrumb, type Crumb } from "@/components/ui/page-header";
import { Dropdown } from "@/components/ui/dropdown";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useAuth } from "@/lib/auth";

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
  { items: [{ href: "/dashboard", label: "Centro de control", icon: <LayoutDashboard className="h-[17px] w-[17px]" aria-hidden /> }] },
  {
    title: "Terminales",
    items: [
      { href: "/devices", label: "Relojes", icon: <Fingerprint className="h-[17px] w-[17px]" aria-hidden />, perm: "devices.read" },
      { href: "/commands", label: "Comandos", icon: <Terminal className="h-[17px] w-[17px]" aria-hidden />, perm: "commands.read" },
    ],
  },
  {
    title: "Organización",
    items: [
      { href: "/companies", label: "Empresas y sucursales", icon: <Building2 className="h-[17px] w-[17px]" aria-hidden />, perm: "companies.read" },
      { href: "/people", label: "Trabajadores", icon: <Users className="h-[17px] w-[17px]" aria-hidden />, perm: "people.read" },
      { href: "/work-schedules", label: "Horarios", icon: <Clock className="h-[17px] w-[17px]" aria-hidden />, perm: "schedules.read" },
      { href: "/holidays", label: "Feriados", icon: <CalendarDays className="h-[17px] w-[17px]" aria-hidden />, perm: "schedules.read" },
    ],
  },
  {
    title: "Asistencia",
    items: [
      { href: "/attendance", label: "Marcaciones", icon: <Clock className="h-[17px] w-[17px]" aria-hidden />, perm: "attendance.read" },
      { href: "/attendance/pending", label: "Llegadas en vivo", icon: <Activity className="h-[17px] w-[17px]" aria-hidden />, perm: "attendance.read" },
      { href: "/reports", label: "Reportes", icon: <FileBarChart className="h-[17px] w-[17px]" aria-hidden />, perm: "attendance.read" },
      { href: "/reports?view=overtime", label: "Tiempo extra", icon: <TimerReset className="h-[17px] w-[17px]" aria-hidden />, perm: "attendance.read" },
      { href: "/device-users", label: "Personal en reloj", icon: <Users className="h-[17px] w-[17px]" aria-hidden />, perm: "device_users.read" },
      { href: "/enrollments", label: "Enrolamientos", icon: <Fingerprint className="h-[17px] w-[17px]" aria-hidden />, perm: "enrollments.read" },
    ],
  },
  {
    title: "Gobierno",
    items: [
      { href: "/users", label: "Usuarios y accesos", icon: <ShieldCheck className="h-[17px] w-[17px]" aria-hidden />, perm: "users.read" },
      { href: "/audit", label: "Auditoría", icon: <ScrollText className="h-[17px] w-[17px]" aria-hidden />, perm: "audit.read" },
    ],
  },
];

const CRUMB_TITLES: Record<string, string> = {
  dashboard: "Centro de control", devices: "Relojes", commands: "Comandos", attendance: "Marcaciones",
  reports: "Reportes", "device-users": "Personal en reloj", companies: "Empresas y sucursales",
  people: "Trabajadores", "work-schedules": "Horarios", holidays: "Feriados", enrollments: "Enrolamientos",
  users: "Usuarios y accesos", audit: "Auditoría", pending: "Llegadas en vivo",
};

function isActive(pathname: string, href: string): boolean {
  if (href === "/attendance") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function crumbsFor(pathname: string): Crumb[] {
  let href = "";
  return pathname.split("/").filter(Boolean).map((part) => {
    href += `/${part}`;
    return { label: CRUMB_TITLES[part] ?? (part.length > 14 ? `${part.slice(0, 10)}…` : part), href };
  });
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/dashboard" className="flex min-w-0 items-center gap-3 px-5" aria-label="ZKTeco ADMS — Centro de control">
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-blue-300/20 bg-gradient-to-br from-blue-400 to-indigo-600 text-white shadow-glow">
        <Fingerprint className="h-5 w-5" aria-hidden />
      </span>
      {!collapsed && (
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-[14px] font-semibold tracking-tight text-foreground">ZKTeco ADMS</span>
          <span className="block truncate text-[10px] font-medium uppercase tracking-[0.14em] text-muted">Control de asistencia</span>
        </span>
      )}
    </Link>
  );
}

function NavList({ collapsed, onNavigate, can }: { collapsed: boolean; onNavigate?: () => void; can: (p: string) => boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Principal" className="flex flex-col gap-5 px-3">
      {NAV.map((section, index) => {
        const items = section.items.filter((item) => !item.perm || can(item.perm));
        if (!items.length) return null;
        return (
          <div key={section.title ?? `section-${index}`}>
            {section.title && !collapsed && <p className="mb-2 px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{section.title}</p>}
            <ul className="space-y-1">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={`group flex min-h-11 items-center gap-3 rounded-lg border px-2.5 py-3 text-[13px] transition-all duration-150 lg:min-h-0 lg:py-2 ${collapsed ? "justify-center" : ""} ${active ? "border-blue-400/20 bg-accent-soft font-medium text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,.04)]" : "border-transparent text-muted hover:border-line-subtle hover:bg-surface-hover hover:text-foreground"}`}
                    >
                      <span className={active ? "text-accent" : "text-muted transition-colors group-hover:text-foreground"}>{item.icon}</span>
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

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout, can } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const initial = (user?.username ?? "?").slice(0, 1).toUpperCase();

  useEffect(() => {
    setCollapsed(window.localStorage.getItem("adms:sidebar") === "collapsed");
  }, []);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setDrawer(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  function toggleCollapse() {
    setCollapsed((previous) => {
      const next = !previous;
      window.localStorage.setItem("adms:sidebar", next ? "collapsed" : "expanded");
      return next;
    });
  }

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-surface-canvas text-foreground">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-surface-card focus:px-4 focus:py-2 focus:text-sm focus:text-foreground focus:shadow-pop">Saltar al contenido</a>

      <aside aria-label="Navegación principal" className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line-subtle bg-surface-sidebar/95 backdrop-blur-xl transition-[width] duration-200 lg:flex ${collapsed ? "w-[72px]" : "w-[270px]"}`}>
        <div className="flex h-16 shrink-0 items-center border-b border-line-subtle"><Brand collapsed={collapsed} /></div>
        <div className="min-h-0 flex-1 overflow-y-auto py-4"><NavList collapsed={collapsed} can={can} /></div>
        <div className="m-3 mt-0 rounded-xl border border-line-subtle bg-surface-raised/70 p-2">
          {!collapsed && <div className="mb-2 flex items-center gap-2 px-2 py-1"><span className="relative flex h-2 w-2"><span className="absolute h-full w-full animate-pulse-dot rounded-full bg-emerald-400" /><span className="relative h-2 w-2 rounded-full bg-emerald-400" /></span><span className="truncate text-[11px] text-muted">Sesión protegida</span></div>}
          <button onClick={toggleCollapse} aria-label={collapsed ? "Expandir menú" : "Colapsar menú"} className="flex w-full items-center justify-center gap-2 rounded-lg px-2 py-2 text-xs text-muted transition-colors hover:bg-surface-hover hover:text-foreground">
            {collapsed ? <ChevronsRight className="h-4 w-4" aria-hidden /> : <><ChevronsLeft className="h-4 w-4" aria-hidden /><span>Colapsar menú</span></>}
          </button>
        </div>
      </aside>

      {drawer && <div className="fixed inset-0 z-50 lg:hidden"><button aria-label="Cerrar menú" onClick={() => setDrawer(false)} className="absolute inset-0 animate-fade-in cursor-default bg-black/70 backdrop-blur-sm" /><aside aria-label="Navegación principal" className="absolute inset-y-0 left-0 flex w-[min(286px,calc(100vw-16px))] animate-drawer-in flex-col border-r border-line-subtle bg-surface-sidebar shadow-pop"><div className="flex h-16 items-center justify-between border-b border-line-subtle pr-3"><Brand collapsed={false} /><button onClick={() => setDrawer(false)} aria-label="Cerrar menú" className="flex h-11 w-11 items-center justify-center rounded-lg text-muted hover:bg-surface-hover hover:text-foreground"><X className="h-5 w-5" aria-hidden /></button></div><div className="min-h-0 flex-1 overflow-y-auto py-4"><NavList collapsed={false} can={can} onNavigate={() => setDrawer(false)} /></div></aside></div>}

      <div className={`flex min-h-screen min-w-0 flex-col transition-[padding] duration-200 ${collapsed ? "lg:pl-[72px]" : "lg:pl-[270px]"}`}>
        <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-line-subtle bg-surface-canvas/80 px-4 backdrop-blur-xl md:px-8">
          <div className="flex min-w-0 items-center gap-3"><button onClick={() => setDrawer(true)} aria-label="Abrir menú" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface-hover hover:text-foreground lg:hidden"><Menu className="h-5 w-5" aria-hidden /></button><div className="min-w-0 truncate"><Breadcrumb items={crumbsFor(pathname)} /></div></div>
          <div className="flex items-center gap-2"><ThemeToggle compact /><span className="hidden items-center gap-2 rounded-lg border border-line-subtle bg-surface-raised px-2.5 py-2 text-[11px] text-muted sm:inline-flex"><Activity className="h-3.5 w-3.5 text-emerald-400" aria-hidden />Operación segura</span><Dropdown label="Menú de usuario" trigger={<span className="flex items-center gap-2 rounded-lg border border-transparent py-1 pl-1 pr-2 transition-colors hover:border-line-subtle hover:bg-surface-raised"><span aria-hidden className="flex h-7 w-7 items-center justify-center rounded-md bg-accent-soft text-[12px] font-bold text-accent">{initial}</span><span className="hidden max-w-32 truncate text-[13px] font-medium text-foreground sm:block">{user?.username ?? ""}</span></span>} items={[{ label: "Cerrar sesión", icon: <LogOut className="h-4 w-4" aria-hidden />, danger: true, onSelect: () => void signOut() }]} /></div>
        </header>
        <main id="contenido" className="enterprise-page flex-1 px-4 py-5 md:px-8 md:py-6"><div className="mx-auto w-full max-w-[1600px]">{children}</div></main>
      </div>
    </div>
  );
}
