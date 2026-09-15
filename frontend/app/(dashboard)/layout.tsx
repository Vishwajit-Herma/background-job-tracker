import { Sidebar } from "@/components/bjt/sidebar";
import { Topbar } from "@/components/bjt/topbar";
import { ProjectProvider } from "@/components/bjt/project-provider";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProjectProvider>
      <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
        <div className="hidden border-r bg-muted/40 md:block">
          <Sidebar className="fixed w-[220px] lg:w-[280px]" />
        </div>
        <div className="flex flex-col w-full h-screen overflow-hidden">
          <Topbar />
          <main className="flex-1 overflow-y-auto p-4 lg:p-6 bg-background">
            {children}
          </main>
        </div>
      </div>
    </ProjectProvider>
  );
}
