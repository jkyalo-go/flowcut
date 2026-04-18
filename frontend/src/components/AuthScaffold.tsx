import Link from "next/link";
import type { ReactNode } from "react";

interface AuthScaffoldProps {
  eyebrow: string;
  title: string;
  description: string;
  footer?: ReactNode;
  children: ReactNode;
}

export function AuthScaffold({
  eyebrow,
  title,
  description,
  footer,
  children,
}: AuthScaffoldProps) {
  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6 lg:px-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative overflow-hidden rounded-[32px] border border-border/70 bg-[linear-gradient(160deg,rgba(255,255,255,0.55),rgba(255,245,236,0.82))] p-8 shadow-[0_30px_100px_rgba(37,33,23,0.12)] md:p-10">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,107,53,0.14),transparent_32%),radial-gradient(circle_at_75%_20%,rgba(31,169,150,0.18),transparent_24%)]" />
          <div className="relative flex h-full flex-col justify-between gap-12">
            <div>
              <Link href="/" className="font-display text-2xl tracking-tight text-foreground">
                FlowCut
              </Link>
              <p className="mt-12 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                {eyebrow}
              </p>
              <h1 className="mt-4 max-w-xl font-display text-4xl leading-tight tracking-tight text-foreground md:text-5xl">
                {title}
              </h1>
              <p className="mt-5 max-w-lg text-base leading-7 text-muted-foreground">
                {description}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="app-panel-muted p-4">
                <p className="eyebrow">Projects</p>
                <p className="mt-3 font-display text-2xl tracking-tight text-foreground">Faster intake</p>
                <p className="mt-2 text-sm text-muted-foreground">Move from upload to publish without changing tools.</p>
              </div>
              <div className="app-panel-muted p-4">
                <p className="eyebrow">Queue</p>
                <p className="mt-3 font-display text-2xl tracking-tight text-foreground">Clear review</p>
                <p className="mt-2 text-sm text-muted-foreground">Approve, reject, and schedule from one operating surface.</p>
              </div>
              <div className="app-panel-muted p-4">
                <p className="eyebrow">Schedule</p>
                <p className="mt-3 font-display text-2xl tracking-tight text-foreground">Reliable delivery</p>
                <p className="mt-2 text-sm text-muted-foreground">Track platform readiness, failures, and upcoming slots in context.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="app-panel flex items-center p-4 sm:p-6 lg:p-8">
          <div className="mx-auto w-full max-w-md space-y-6">
            {children}
            {footer}
          </div>
        </section>
      </div>
    </div>
  );
}
