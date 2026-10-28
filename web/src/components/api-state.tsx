import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { API_URL, ApiError } from "@/lib/api";

export function ApiErrorAlert({ error, title = "Something went wrong" }: { error: unknown; title?: string }) {
  const messages = error instanceof ApiError ? error.messages : [String(error)];
  const unreachable = error instanceof ApiError && error.status === 0;

  return (
    <Alert variant="destructive">
      <AlertTriangle aria-hidden />
      <AlertTitle>{unreachable ? "The prediction API is not running" : title}</AlertTitle>
      <AlertDescription>
        {unreachable ? (
          <p>
            Start it from the project folder with{" "}
            <code className="rounded bg-muted px-1 font-mono text-foreground">uvicorn api.main:app --reload</code>,
            then refresh this page. Expected at <span className="font-mono">{API_URL}</span>.
          </p>
        ) : (
          <ul className="list-disc space-y-1 pl-4">
            {messages.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function PageSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-[480px] rounded-2xl" />
      <Skeleton className="h-[480px] rounded-2xl" />
    </div>
  );
}

export function PageTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-8 max-w-2xl">
      <p className="mb-2 font-mono text-xs tracking-[0.2em] text-primary uppercase">{eyebrow}</p>
      <h1 className="font-heading text-3xl leading-tight font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h1>
      {children && <p className="mt-3 text-pretty text-muted-foreground">{children}</p>}
    </div>
  );
}
