---
name: enterprise-biometric-frontend
description: >-
  Comprehensive blueprint, design system, zero-dependency SVG charts, and UI templates for building enterprise-grade IoT/biometric monitoring dashboards (Linear/Datadog style). Use this skill when asked to build or replicate an enterprise frontend for time & attendance, access control, IoT telemetry, or high-performance executive dashboards with custom KPI cards, interactive SVG charts (Donut, Weekly Trend, Hourly Flow), and mission control live feeds.
---

# Enterprise Biometric & IoT Dashboard Design System

This skill provides an end-to-end framework, design system guidelines, and copy-pasteable component recipes to build world-class, enterprise SaaS dashboards (styled after Linear, Datadog, and Stripe) for time & attendance, biometric devices, access control, or hardware telemetry.

---

## 1. Core Philosophy: Why Zero-Dependency SVG Charts?

Traditional dashboards often rely on heavy external chart libraries (`recharts`, `chart.js`, `victory`). In modern enterprise stacks (such as React 19, Next.js App Router, or Vite), these libraries frequently cause:
- **Peer dependency conflicts**: Broken builds on newer React releases (e.g. `react@19`).
- **Heavy bundle footprint**: 150KB - 400KB of extra JavaScript.
- **Styling constraints**: Clunky CSS-in-JS overrides or canvas rendering that bypasses Tailwind CSS dark mode and theme variables.

### The Bespoke SVG Pattern
Building charts directly in SVG with Tailwind CSS provides:
1. **Zero dependencies**: Zero third-party packages needed. Works on every React version (17, 18, 19+).
2. **Instant render performance**: Under 2KB per chart; native DOM nodes with pure CSS transitions.
3. **Flawless Tailwind Theme Integration**: Supports dark/light mode, CSS gradients, blur effects, and custom font families (`font-mono`, `font-sans`).
4. **Interactive Hover States**: CSS transitions, SVG drop-shadow filters, and responsive viewboxes.

---

## 2. Design Tokens & Visual Standard (Linear / Datadog Aesthetic)

- **Palette**: Dark theme default. Zinc / Slate background (`bg-background: #09090b`), muted surfaces (`bg-card/70 backdrop-blur-sm`), and sharp borders (`border-border/80: #27272a`).
- **Typography Hierarchy**:
  - Headings / Body: `Inter` or system sans-serif (`font-sans`).
  - Numbers, Timestamps, Codes, PINs: `JetBrains Mono` or tabular numbers (`font-mono tracking-tight`).
- **Semantic Colors**:
  - **Primary / Action**: Blue / Sky (`#38bdf8` / `#2563eb`) - system state, general volumes.
  - **Success / On-Time**: Emerald (`#10b981` / `#34d399`) - 100% punctuality, device online, authorized.
  - **Warning / Delays**: Amber (`#f59e0b` / `#fbbf24`) - late punches, overtime alerts, approaching limits.
  - **Danger / Absences**: Rose / Red (`#ef4444` / `#f87171`) - absences, offline terminals, rejected items.
  - **Processes / Special**: Indigo / Violet (`#6366f1` / `#818cf8`) - shifts, payroll calculations, biometric templates.

---

## 3. Executive KPI Cards Pattern

A proper enterprise dashboard opens with 4 primary telemetry cards:

```tsx
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
  {/* Card 1: Activity Volume */}
  <Card className="border-border/80 bg-card/70 backdrop-blur-sm relative overflow-hidden group hover:border-primary/40 transition-all">
    <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none" />
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Total Checadas Hoy
      </CardTitle>
      <div className="rounded-lg bg-primary/10 p-2 text-primary">
        <Clock className="h-4 w-4" />
      </div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold font-mono text-foreground tracking-tight">
        {metrics.totalPunchesToday}
      </div>
      <div className="flex items-center space-x-1.5 text-[11px] text-muted-foreground font-medium mt-1">
        <Activity className="h-3 w-3 text-primary" />
        <span>Marcas registradas hoy</span>
      </div>
    </CardContent>
  </Card>

  {/* Card 2: Compliance / Punctuality Rate with Progress Bar */}
  <Card className="border-border/80 bg-card/70 backdrop-blur-sm relative overflow-hidden group hover:border-emerald-500/40 transition-all">
    <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none" />
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Índice de Puntualidad
      </CardTitle>
      <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-400">
        <CheckCircle2 className="h-4 w-4" />
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex items-baseline space-x-2">
        <span className="text-2xl font-bold font-mono text-emerald-400 tracking-tight">
          {metrics.punctualityRate}%
        </span>
        <span className="text-[10px] text-muted-foreground font-mono">promedio</span>
      </div>
      <div className="w-full bg-muted/40 h-1.5 rounded-full overflow-hidden mt-2 border border-border/40">
        <div
          className="h-full bg-emerald-500 rounded-full transition-all duration-500"
          style={{ width: `${metrics.punctualityRate}%` }}
        />
      </div>
    </CardContent>
  </Card>

  {/* Card 3: Friction / Delays */}
  <Card className="border-border/80 bg-card/70 backdrop-blur-sm relative overflow-hidden group hover:border-amber-500/40 transition-all">
    <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl pointer-events-none" />
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Retardos Acumulados
      </CardTitle>
      <div className="rounded-lg bg-amber-500/10 p-2 text-amber-400">
        <AlertTriangle className="h-4 w-4" />
      </div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold font-mono text-amber-400 tracking-tight">
        {metrics.latePunchesToday}
      </div>
      <div className="text-[11px] text-muted-foreground font-medium mt-1">
        {metrics.totalLateMinutesToday} min de demora total
      </div>
    </CardContent>
  </Card>

  {/* Card 4: Hardware / Edge Fleet Status */}
  <Card className="border-border/80 bg-card/70 backdrop-blur-sm relative overflow-hidden group cursor-pointer hover:border-sky-500/50 transition-all">
    <div className="absolute top-0 right-0 w-24 h-24 bg-sky-500/5 rounded-full blur-2xl pointer-events-none" />
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Terminales Biométricas
      </CardTitle>
      <div className="rounded-lg bg-sky-500/10 p-2 text-sky-400">
        <Cpu className="h-4 w-4" />
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex items-baseline space-x-2">
        <span className="text-2xl font-bold font-mono text-foreground tracking-tight">
          {metrics.activeDevicesCount}
        </span>
        <span className="text-xs text-muted-foreground font-mono">
          / {metrics.totalDevicesCount} activos
        </span>
      </div>
      <div className="flex items-center justify-between text-[11px] text-sky-400 font-medium mt-1">
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-muted-foreground">PUSH online</span>
        </div>
        <div className="flex items-center gap-0.5">
          <span>Ver estado</span>
          <ArrowUpRight className="h-3 w-3" />
        </div>
      </div>
    </CardContent>
  </Card>
</div>
```

---

## 4. Chart Components Specification

### A. Donut Chart (`DonutChart.tsx`)
Reference: [examples/DonutChart.tsx](./examples/DonutChart.tsx)
- **Math**:
  - Radius $r = 70$, Center $(100, 100)$, ViewBox $0\ 0\ 200\ 200$.
  - Circumference $C = 2 \times \pi \times r \approx 439.82$.
  - Stroke Length per segment $= (percentage / 100) \times C$.
  - Cumulative offset $= -(cumulativePercentage / 100) \times C$.
  - SVG transform `-rotate-90` so slices begin at 12 o'clock.
- **Center Tooltip**:
  - When idle: shows Global Metric (e.g. `100% Puntualidad` or `Total Evaluados`).
  - When hovered: dynamically displays the segment's name, count, and percentage in the center circle with matching color.

### B. Weekly Trend Chart (`WeeklyTrendChart.tsx`)
Reference: [examples/WeeklyTrendChart.tsx](./examples/WeeklyTrendChart.tsx)
- **Math & SVG Paths**:
  - Horizontal gridlines at 0%, 50%, 100% with dashed lines.
  - Dual visualization:
    1. Rounded volume bars (`rx="4"`) using CSS/SVG linear gradients (`#3b82f6` to `#1d4ed8`).
    2. Cubic Bezier spline curve (`C cp1x,cp1y cp2x,cp2y x,y`) calculated across points.
    3. Closed area under curve filled with vertical gradient fade (`stop-opacity="0.3"` to `0.0`).
- **Interactive Tooltip**: Floating card on hover showing exact day breakdown (punches, on-time, late, absences, punctuality %).

### C. Hourly Punch Flow Chart (`HourlyPunchChart.tsx`)
Reference: [examples/HourlyPunchChart.tsx](./examples/HourlyPunchChart.tsx)
- Dynamic vertical scaling: `maxCount = Math.max(1, ...data.map(d => d.count))`.
- Segmented columns: Bottom segment (Primary = on-time), top segment (Amber = late).
- **Peak Hour Indicator**: Automatically identifies `peakHour` (e.g. `09:00 hrs`) and decorates the bar with a pulsing flame badge and ring highlight.

---

## 5. Telemetry & Pre-Payroll Widgets

- **`PayrollSummaryCard.tsx`**: Displays Effective Work Hours, Detected Overtime, Accumulated Late Minutes, and provides an instant shortcut button to the Overtime Authorization view.
- **`BiometricHealthCard.tsx`**: Displays biometric template coverage rate progress bar, active SilkID/optical templates in hardware, and counts of enrolled vs pending workers.
- **`LiveAttendanceFeed`**: Real-time websocket stream card showing recently processed punches with avatar, worker PIN, terminal name, and status badge.

---

## 6. Anti-Cache & Single-Page Application (SPA) Deployment

When updating client bundles in production Docker/Nginx setups:
1. **Never Cache `index.html`**:
   ```nginx
   location = /index.html {
       add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0";
       expires off;
   }
   ```
2. **Immutable Long-Term Cache for Hashed Assets**:
   ```nginx
   location /assets/ {
       add_header Cache-Control "public, max-age=31536000, immutable";
   }
   ```
3. **Hot-Swap Alias Symlinks**: When rebuilding a Vite SPA, copy or symlink older cached bundle hashes (e.g., `index-*.js`) inside the container so currently active browser tabs don't fail with a blank screen or React 404 error before page reload.

---

## 7. How to Adapt this Blueprint for Any Device or Hardware

Even if the physical device changes (e.g., from ZKTeco SilkFP to Hikvision, Dahua, Suprema, or custom MQTT/HTTP IoT devices):
1. **Normalize the Logs**: Map incoming punches to `(user_id, timestamp, device_id, verify_mode)`.
2. **Maintain the Summary Pipeline**: Calculate `(on_time, late, absent, overtime)` in backend workers.
3. **Plug into the Frontend Contract**: The frontend components consume normalized JSON:
   - `totalPunchesToday`, `punctualityRate`, `latePunchesToday`, `absencesToday`
   - `hourlyPunches: [{ hour, count, onTime, late }]`
   - `weeklyTrend: [{ date, day, punches, punctualityRate, onTime, late, absences }]`
   - `attendanceBreakdown: [{ name, count, color, percentage }]`
   - `biometricHealth: { totalUsers, usersWithFp, totalFingerprints, coverageRate }`
