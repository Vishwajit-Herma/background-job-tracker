import { AlertCircle, Inbox } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-md border border-dashed p-8 text-center animate-in fade-in-50">
      <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
          {icon || <Inbox className="h-10 w-10 text-muted-foreground" />}
        </div>
        <h2 className="mt-6 text-xl font-semibold">{title}</h2>
        <p className="mb-8 mt-2 text-center text-sm font-normal leading-6 text-muted-foreground">
          {description}
        </p>
        {action}
      </div>
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  description?: string;
  retry?: () => void;
}

export function ErrorState({ title = "Something went wrong", description, retry }: ErrorStateProps) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-md border p-8 text-center animate-in fade-in-50">
      <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-10 w-10 text-destructive" />
        </div>
        <h2 className="mt-6 text-xl font-semibold">{title}</h2>
        {description && (
          <p className="mb-8 mt-2 text-center text-sm font-normal leading-6 text-muted-foreground">
            {description}
          </p>
        )}
        {retry && (
          <button
            onClick={retry}
            className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}
