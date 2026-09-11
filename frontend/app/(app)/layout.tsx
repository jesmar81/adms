import { RequireAuth } from "@/lib/auth";
import { AppShell } from "@/components/shell/AppShell";
import { ToastProvider } from "@/components/ui/toast";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <ToastProvider>
        <AppShell>{children}</AppShell>
      </ToastProvider>
    </RequireAuth>
  );
}
