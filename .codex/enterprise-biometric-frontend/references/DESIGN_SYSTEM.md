# Design System Tokens & Typography (Linear / Datadog Style)

## 1. Color Palette (Tailwind CSS Dark Mode)

```css
:root {
  --background: 240 10% 3.9%;          /* #09090b - Zinc 950 */
  --foreground: 0 0% 98%;              /* #fafafa - White text */
  --card: 240 10% 5.5%;                /* #121215 - Surface card */
  --card-foreground: 0 0% 98%;
  --popover: 240 10% 5.5%;
  --popover-foreground: 0 0% 98%;
  --primary: 217 91% 60%;              /* #3b82f6 - Electric Blue */
  --primary-foreground: 0 0% 100%;
  --secondary: 240 3.7% 15.9%;         /* #27272a - Zinc 800 */
  --secondary-foreground: 0 0% 98%;
  --muted: 240 3.7% 15.9%;
  --muted-foreground: 240 5% 64.9%;     /* #a1a1aa - Zinc 400 */
  --accent: 240 3.7% 15.9%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 84.2% 60.2%;        /* #ef4444 - Rose 500 */
  --destructive-foreground: 0 0% 98%;
  --border: 240 3.7% 15.9%;            /* #27272a - Zinc 800 border */
  --input: 240 3.7% 15.9%;
  --ring: 217 91% 60%;
}
```

## 2. Visual Glassmorphism Recipe
Apply to dashboard cards:
```tsx
className="border-border/80 bg-card/70 backdrop-blur-sm relative overflow-hidden group hover:border-primary/40 transition-all"
```
Optional subtle background radial glow:
```tsx
<div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none" />
```

## 3. Typography Rules
- **Inter**: All titles, descriptions, and user names (`font-sans`).
- **JetBrains Mono**: All numeric values, time values, PIN numbers, percentages, and serial numbers:
  ```tsx
  <span className="text-2xl font-bold font-mono text-foreground tracking-tight">
    {value}
  </span>
  ```

## 4. Semantic Color Mapping
| Metric / Concept | Color Name | Hex Code | Tailwind Token |
| :--- | :--- | :--- | :--- |
| On-Time / Success / Online | Emerald | `#10b981` | `text-emerald-400 bg-emerald-500/10 border-emerald-500/20` |
| Late / Warning / Overtime | Amber | `#f59e0b` | `text-amber-400 bg-amber-500/10 border-amber-500/20` |
| Absence / Critical / Offline | Rose / Red | `#ef4444` | `text-rose-400 bg-rose-500/10 border-rose-500/20` |
| Incidents / Shifts / Info | Indigo | `#6366f1` | `text-indigo-400 bg-indigo-500/10 border-indigo-500/20` |
| Hardware / Telemetry / PUSH | Sky | `#38bdf8` | `text-sky-400 bg-sky-500/10 border-sky-500/20` |
