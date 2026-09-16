"use client";

import { 
  Activity, 
  Sparkles, 
  LineChart, 
  BookOpen, 
  ShieldCheck, 
  Code2,
  FolderGit2,
  BrainCircuit,
  UserCheck,
  CheckCircle2,
  SlidersHorizontal
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollReveal } from "@/components/bjt/landing/scroll-reveal";

export function LandingFeatures() {
  return (
    <section id="features" className="py-20 bg-background border-t border-border/60 relative overflow-hidden">
      {/* Subtle Background Glow Accent */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-primary/5 blur-[140px] rounded-full pointer-events-none" />

      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
        <ScrollReveal>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-primary mb-2">
              Platform Capabilities
            </h2>
            <h3 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              Everything You Need To Monitor Background Jobs
            </h3>
            <p className="mt-4 text-base sm:text-lg text-muted-foreground">
              Built for engineering teams running Celery, Django, FastAPI, and standalone Python task queues.
            </p>
          </div>
        </ScrollReveal>

        {/* 1. Feature Spotlight Blocks (2 Split Cards with Exact Equal Heights & Gradient Accents) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          {/* Spotlight 1: AI Incident Intelligence */}
          <ScrollReveal delayMs={100}>
            <div className="flex flex-col justify-between h-full p-6 sm:p-8 rounded-xl border border-border/90 bg-gradient-to-b from-card via-card to-primary/[0.02] shadow-sm hover:border-primary/40 hover:shadow-xl hover:shadow-primary/5 hover:-translate-y-1 transition-all duration-300 space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <BrainCircuit className="h-6 w-6" />
                  </div>
                  <Badge variant="outline" className="text-xs font-semibold bg-gradient-to-r from-primary/10 to-indigo-500/10 text-primary border-primary/20">
                    AI Powered ✨
                  </Badge>
                </div>
                <div>
                  <h4 className="text-xl font-bold text-foreground">
                    AI Incident Intelligence & Tracebacks
                  </h4>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    Automatically extract tracebacks, categorize error types, and generate AI-assisted root cause summaries for Celery execution failures.
                  </p>
                </div>
              </div>

              {/* Fixed Height Callout Box (Exact h-28) */}
              <div className="h-28 flex flex-col justify-between p-4 rounded-lg border border-border/80 bg-gradient-to-br from-muted/60 via-muted/30 to-background text-xs text-foreground/90 font-sans shadow-xs">
                <div className="flex items-center justify-between text-[11px] font-semibold text-primary">
                  <span>AI Engine Analysis</span>
                  <span className="font-mono text-xs">HTTP 429 Rate Limit</span>
                </div>
                <p className="text-[12px] text-muted-foreground leading-snug line-clamp-2">
                  "Detected 429 Rate Limit cascade across worker pool. Suggested fix: Apply exponential backoff parameters in Celery task retry settings."
                </p>
              </div>
            </div>
          </ScrollReveal>

          {/* Spotlight 2: Multi-Project & Team Collaboration */}
          <ScrollReveal delayMs={200}>
            <div className="flex flex-col justify-between h-full p-6 sm:p-8 rounded-xl border border-border/90 bg-gradient-to-b from-card via-card to-primary/[0.02] shadow-sm hover:border-primary/40 hover:shadow-xl hover:shadow-primary/5 hover:-translate-y-1 transition-all duration-300 space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <UserCheck className="h-6 w-6" />
                  </div>
                  <Badge variant="outline" className="text-xs font-semibold bg-gradient-to-r from-primary/10 to-indigo-500/10 text-primary border-primary/20">
                    Multi-Project & Teams
                  </Badge>
                </div>
                <div>
                  <h4 className="text-xl font-bold text-foreground">
                    Multi-Project Isolation & Incident Assignment
                  </h4>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    Isolate job telemetry into distinct projects, switch project scopes globally, and assign reliability incidents to teammates for resolution.
                  </p>
                </div>
              </div>

              {/* Fixed Height Callout Box (Exact h-28) */}
              <div className="h-28 flex flex-col justify-between p-4 rounded-lg border border-border/80 bg-gradient-to-br from-muted/60 via-muted/30 to-background text-xs text-foreground/90 font-sans shadow-xs">
                <div className="flex items-center justify-between text-[11px] font-semibold">
                  <span className="text-primary font-bold">Active Scope: Payments-Worker</span>
                  <Badge variant="outline" className="text-[10px] bg-background">Assigned: John Doe</Badge>
                </div>
                <p className="text-[12px] text-muted-foreground leading-snug line-clamp-2">
                  Toolbar scope synced across all metrics, execution logs, and incident feeds.
                </p>
              </div>
            </div>
          </ScrollReveal>
        </div>

        {/* 2. Platform Capabilities (4 Horizontal Compact Cards with Hover Animation & Scroll Reveal) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <ScrollReveal delayMs={100}>
            <div className="p-5 rounded-lg border border-border/80 bg-gradient-to-b from-card to-muted/20 hover:border-primary/40 hover:shadow-md hover:-translate-y-1 transition-all duration-300 space-y-2">
              <div className="flex items-center gap-2.5 text-primary">
                <Activity className="h-4 w-4" />
                <h5 className="font-bold text-sm text-foreground">Real-Time Telemetry</h5>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Track execution start, finish, retry, and duration events live across your worker fleet.
              </p>
            </div>
          </ScrollReveal>

          <ScrollReveal delayMs={200}>
            <div className="p-5 rounded-lg border border-border/80 bg-gradient-to-b from-card to-muted/20 hover:border-primary/40 hover:shadow-md hover:-translate-y-1 transition-all duration-300 space-y-2">
              <div className="flex items-center gap-2.5 text-primary">
                <LineChart className="h-4 w-4" />
                <h5 className="font-bold text-sm text-foreground">P95 Latency Metrics</h5>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Monitor P50/P95 latency percentiles, failure rates, and task execution counts.
              </p>
            </div>
          </ScrollReveal>

          <ScrollReveal delayMs={300}>
            <div className="p-5 rounded-lg border border-border/80 bg-gradient-to-b from-card to-muted/20 hover:border-primary/40 hover:shadow-md hover:-translate-y-1 transition-all duration-300 space-y-2">
              <div className="flex items-center gap-2.5 text-primary">
                <BookOpen className="h-4 w-4" />
                <h5 className="font-bold text-sm text-foreground">Runbooks & Postmortems</h5>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Guide team incident response with structured step-by-step runbooks and summaries.
              </p>
            </div>
          </ScrollReveal>

          <ScrollReveal delayMs={400}>
            <div className="p-5 rounded-lg border border-border/80 bg-gradient-to-b from-card to-muted/20 hover:border-primary/40 hover:shadow-md hover:-translate-y-1 transition-all duration-300 space-y-2">
              <div className="flex items-center gap-2.5 text-primary">
                <Code2 className="h-4 w-4" />
                <h5 className="font-bold text-sm text-foreground">PyPI SDK & REST API</h5>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Official `background-job-tracker` Python SDK with async batch sender and REST API.
              </p>
            </div>
          </ScrollReveal>
        </div>

      </div>
    </section>
  );
}
