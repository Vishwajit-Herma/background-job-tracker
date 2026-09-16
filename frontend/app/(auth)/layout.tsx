import Link from "next/link";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center p-4 sm:p-8 bg-muted/20">
      <Link href="/" className="mb-6 inline-flex items-center gap-2.5 transition-transform hover:scale-105">
        <img
          src="/bjt-logo-clean.png"
          alt="Background Job Tracker Logo"
          className="h-9 w-auto object-contain dark:hidden"
        />
        <img
          src="/bjt-logo-dark.png"
          alt="Background Job Tracker Logo"
          className="h-9 w-auto object-contain hidden dark:block"
        />
        <span className="font-semibold text-lg tracking-tight text-foreground">
          Background Job Tracker
        </span>
      </Link>
      <div className="w-full max-w-md rounded-xl border bg-card p-6 sm:p-8 shadow-sm">
        {children}
      </div>
    </div>
  );
}
