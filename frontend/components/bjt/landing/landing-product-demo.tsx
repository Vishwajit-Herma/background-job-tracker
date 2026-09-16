"use client";

import { 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Sparkles, 
  UserCheck, 
  Terminal, 
  Layers,
  ArrowRight,
  ShieldAlert,
  Cpu
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollReveal } from "@/components/bjt/landing/scroll-reveal";

export function LandingProductDemo() {
  return (
    <section id="product-demo" className="py-20 bg-muted/20 border-t border-border/60">
      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <ScrollReveal>
          <div className="text-center max-w-3xl mx-auto mb-14">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-3">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              <span>Product Spotlight</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              Deep Incident Intelligence & Execution Tracking
            </h2>
            <p className="mt-4 text-base sm:text-lg text-muted-foreground leading-relaxed">
              Inspect real-time execution tracebacks, analyze AI-assisted root causes, and manage team incident assignments in one clean workspace.
            </p>
          </div>
        </ScrollReveal>

        {/* Larger Real-Product Mockup Workspace */}
        <ScrollReveal delayMs={150}>
          <div className="max-w-6xl mx-auto rounded-xl border border-border bg-card shadow-2xl hover:border-primary/40 hover:shadow-primary/10 transition-all duration-300 overflow-hidden">
          {/* Mock App Top Bar */}
          <div className="flex flex-wrap items-center justify-between border-b border-border bg-muted/40 px-4 py-3 gap-2">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-destructive/60" />
                <span className="h-3 w-3 rounded-full bg-amber-400/60" />
                <span className="h-3 w-3 rounded-full bg-emerald-500/60" />
              </div>
              <span className="ml-2 text-xs font-mono text-muted-foreground hidden sm:inline">
                app.backgroundjobtracker.com/projects/payments-worker/incidents/INC-14
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-[10px] bg-background">
                Project: Payments-Worker
              </Badge>
              <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-semibold">
                ● INC-14 (DEGRADED)
              </Badge>
            </div>
          </div>

          {/* Product UI Body Split Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-border bg-background">
            
            {/* Left Column: Incident Overview & AI Root Cause */}
            <div className="lg:col-span-5 p-5 sm:p-6 space-y-6">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Incident Overview
                  </span>
                  <Badge variant="outline" className="border-amber-500/40 text-amber-600 bg-amber-500/10 text-[10px]">
                    HIGH FAILURE RATE
                  </Badge>
                </div>
                <h3 className="text-xl font-bold text-foreground leading-snug">
                  High Failure Rate on <code className="font-mono text-sm bg-muted px-1.5 py-0.5 rounded">sync_user_stripe_events</code>
                </h3>
              </div>

              {/* Status & Team Assignee Badge */}
              <div className="grid grid-cols-2 gap-3 p-3 rounded-lg border bg-muted/30 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[11px]">Investigation Status</span>
                  <div className="flex items-center gap-1.5 mt-1 font-semibold text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>Investigating</span>
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Assigned Engineer</span>
                  <div className="flex items-center gap-1.5 mt-1 font-semibold text-foreground">
                    <UserCheck className="h-3.5 w-3.5 text-primary" />
                    <span>John Doe (Lead)</span>
                  </div>
                </div>
              </div>

              {/* Threshold Failure Rate Meter */}
              <div className="p-4 rounded-lg border bg-card space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">Failure Rate Threshold</span>
                  <span className="font-mono font-bold text-amber-600">15.5% (Limit: 10.0%)</span>
                </div>
                <div className="w-full bg-muted h-2 rounded-full overflow-hidden">
                  <div className="bg-amber-500 h-full rounded-full" style={{ width: "78%" }} />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Triggered 12 minutes ago across 450 total task executions.
                </p>
              </div>

              {/* AI Root Cause Box */}
              <div className="p-4 rounded-lg border border-primary/30 bg-primary/5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-primary">
                    <Sparkles className="h-4 w-4" />
                    <span>AI Root Cause Analysis</span>
                  </div>
                  <Badge variant="outline" className="text-[10px] border-primary/30 bg-primary/10 text-primary">
                    AI Model
                  </Badge>
                </div>
                <p className="text-xs text-foreground/90 leading-relaxed font-sans">
                  "Repeated Stripe API rate limit (<code className="font-mono bg-background px-1 py-0.5 rounded text-[11px]">HTTP 429 Too Many Requests</code>) causing worker retry cascades. Recommended action: Implement exponential backoff in Celery task retry config."
                </p>
              </div>

            </div>

            {/* Right Column: Execution Log & Traceback Inspection */}
            <div className="lg:col-span-7 p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between border-b pb-3">
                <div>
                  <h4 className="font-bold text-sm text-foreground">Recent Task Executions</h4>
                  <p className="text-xs text-muted-foreground">Real-time execution telemetry stream for this task signature</p>
                </div>
                <Badge variant="outline" className="font-mono text-[10px] text-emerald-600 border-emerald-500/30 bg-emerald-500/10">
                  ● Live Streaming
                </Badge>
              </div>

              {/* Execution Items */}
              <div className="space-y-3 text-xs">
                {/* Exec 1 - Failure */}
                <div className="p-3.5 rounded-lg border border-destructive/30 bg-destructive/5 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="destructive" className="text-[10px] px-1.5 py-0">FAILURE</Badge>
                      <span className="font-mono font-semibold text-foreground">exec_8f9a2b1c</span>
                    </div>
                    <div className="flex items-center gap-3 font-mono text-muted-foreground text-[11px]">
                      <span>Duration: 1,840ms</span>
                      <span>2m ago</span>
                    </div>
                  </div>

                  {/* Traceback snippet */}
                  <div className="p-2.5 rounded bg-zinc-950 font-mono text-[11px] text-red-300 overflow-x-auto leading-relaxed border border-zinc-800">
                    <code>
                      stripe.error.RateLimitError: Request rate limit exceeded.<br />
                      File "tasks/stripe_sync.py", line 42, in sync_user_stripe_events
                    </code>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                    <span>Worker: worker-1@prod-aws</span>
                    <span>Queue: payments_default</span>
                  </div>
                </div>

                {/* Exec 2 - Success */}
                <div className="p-3 rounded-lg border bg-card flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="border-green-500/40 text-green-600 bg-green-500/10 text-[10px] px-1.5 py-0">SUCCESS</Badge>
                    <span className="font-mono font-semibold text-foreground">exec_7e6d5c4b</span>
                  </div>
                  <div className="flex items-center gap-3 font-mono text-muted-foreground text-[11px]">
                    <span>Duration: 142ms</span>
                    <span>3m ago</span>
                  </div>
                </div>

                {/* Exec 3 - Success */}
                <div className="p-3 rounded-lg border bg-card flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="border-green-500/40 text-green-600 bg-green-500/10 text-[10px] px-1.5 py-0">SUCCESS</Badge>
                    <span className="font-mono font-semibold text-foreground">exec_6a5b4c3d</span>
                  </div>
                  <div className="flex items-center gap-3 font-mono text-muted-foreground text-[11px]">
                    <span>Duration: 165ms</span>
                    <span>5m ago</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ScrollReveal>
    </div>
  </section>
);
}
