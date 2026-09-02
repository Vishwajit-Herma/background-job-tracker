export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full items-center justify-center p-4 sm:p-8 bg-muted/20">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 sm:p-8 shadow-sm">
        {children}
      </div>
    </div>
  );
}
