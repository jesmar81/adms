import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata = { title: "ZKTeco ADMS", description: "Attendance platform" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="bg-surface-canvas font-sans text-zinc-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
