import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold">ZKTeco ADMS Platform</h1>
      <p className="mt-2 text-slate-400">
        Attendance management for ZKTeco SpeedFace-V5LP devices.
      </p>
      <nav className="mt-6 flex flex-col gap-2">
        <Link className="text-sky-400 underline" href="/login">Login</Link>
        <Link className="text-sky-400 underline" href="/dashboard">Dashboard</Link>
      </nav>
    </main>
  );
}
