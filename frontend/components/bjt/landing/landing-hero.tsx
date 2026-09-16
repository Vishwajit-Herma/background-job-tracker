"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollReveal } from "@/components/bjt/landing/scroll-reveal";
import {
  ArrowRight,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ListChecks,
  FolderGit2,
  RotateCw,
  Sparkles,
  ChevronRight,
  User,
  ShieldCheck,
  Zap,
  ArrowUpRight,
  BookOpen
} from "lucide-react";

export function LandingHero() {
  // Animated phrase switcher for hero text headline
  const phrases = [
    "Under control.",
    "Monitored in real time.",
    "AI-protected.",
    "100% reliable."
  ];

  const [currentPhraseIndex, setCurrentPhraseIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentPhraseIndex((prev) => (prev + 1) % phrases.length);
        setIsTransitioning(false);
      }, 300); // 300ms fade out before swapping phrase
    }, 3200);

    return () => clearInterval(interval);
  }, [phrases.length]);

  return (
    <section className="relative overflow-hidden py-16 md:py-24 bg-gradient-to-b from-background via-muted/20 to-background">
      {/* Background Decorative Radial Glows & Grid */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[400px] bg-primary/10 blur-[130px] rounded-full pointer-events-none animate-pulse duration-7000" />
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[400px] h-[200px] bg-blue-500/10 blur-[90px] rounded-full pointer-events-none" />

      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center relative z-10">
        
        {/* Animated Sub-badge with Shimmer Sheen */}
        <ScrollReveal>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary mb-6 shadow-sm hover:scale-105 hover:border-primary/40 hover:bg-primary/10 transition-all duration-300 cursor-pointer group relative overflow-hidden">
            {/* Shimmer Sheen Effect */}
            <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-1000 bg-gradient-to-r from-transparent via-primary/15 to-transparent pointer-events-none" />
            
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
            <span className="flex items-center gap-1.5">
              AI-Powered Background Job Reliability & Team Observability
              <Sparkles className="h-3.5 w-3.5 text-amber-500 group-hover:rotate-12 transition-transform duration-300" />
            </span>
          </div>
        </ScrollReveal>

        {/* Main Headline with Dynamic Text Rotation & Gradient Shimmer */}
        <ScrollReveal delayMs={100}>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-foreground leading-[1.15] max-w-4xl mx-auto">
            Your background jobs. <br />
            <span className="relative inline-block h-[1.3em] min-w-[280px] text-center">
              <span 
                className={`inline-block bg-gradient-to-r from-primary via-blue-600 to-indigo-600 dark:from-blue-400 dark:via-indigo-300 dark:to-primary bg-clip-text text-transparent transition-all duration-300 transform ${
                  isTransitioning ? "opacity-0 translate-y-2 scale-95" : "opacity-100 translate-y-0 scale-100"
                }`}
              >
                {phrases[currentPhraseIndex]}
              </span>
              <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-3/4 h-1 bg-gradient-to-r from-transparent via-primary/30 to-transparent rounded-full blur-[1px]" />
            </span>
          </h1>
        </ScrollReveal>

        {/* Subtext with Interactive Section Redirect Links */}
        <ScrollReveal delayMs={200}>
          <p className="mt-6 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Track{" "}
            <a
              href="#features"
              className="font-semibold text-foreground underline decoration-primary/40 underline-offset-4 hover:decoration-primary hover:text-primary transition-all inline-flex items-center gap-0.5 group/link"
            >
              multi-project executions
              <ArrowUpRight className="h-3.5 w-3.5 opacity-60 group-hover/link:opacity-100 group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5 transition-transform" />
            </a>
            , leverage{" "}
            <a
              href="#product-demo"
              className="font-semibold text-foreground underline decoration-indigo-500/40 underline-offset-4 hover:decoration-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all inline-flex items-center gap-0.5 group/link"
            >
              AI-powered incident intelligence
              <ArrowUpRight className="h-3.5 w-3.5 opacity-60 group-hover/link:opacity-100 group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5 transition-transform" />
            </a>
            , and assign background-job incidents to your team in{" "}
            <a
              href="#product-demo"
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-mono text-xs font-semibold tracking-tight shadow-xs hover:shadow-[0_0_16px_rgba(16,185,129,0.3)] hover:border-emerald-500/60 hover:bg-emerald-500/20 hover:scale-105 transition-all duration-300 cursor-pointer group/link align-middle ml-0.5"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-80" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
              </span>
              <span className="uppercase tracking-wider text-[11px] font-bold">real-time</span>
              <ArrowUpRight className="h-3 w-3 text-emerald-600 dark:text-emerald-400 opacity-80 group-hover/link:opacity-100 group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5 transition-all" />
            </a>
            .
          </p>
        </ScrollReveal>

        {/* Action Buttons with Hover Micro-Animations */}
        <ScrollReveal delayMs={300}>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/register"
              className={buttonVariants({ size: "lg", className: "group w-full sm:w-auto bg-primary text-primary-foreground shadow-lg shadow-primary/15 hover:shadow-xl hover:shadow-primary/25 hover:bg-primary/95 hover:-translate-y-0.5 transition-all duration-300 px-7 font-semibold" })}
            >
              <span>Get Started Free</span>
              <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1.5 transition-transform duration-300" />
            </Link>
            <a
              href="https://background-job-tracker.readthedocs.io/en/latest/getting-started/sdk-quickstart/"
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "lg", className: "w-full sm:w-auto px-6 font-medium border-border/80 hover:bg-muted/70 hover:scale-[1.02] hover:border-border transition-all duration-300 gap-2" })}
            >
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <span>View Docs ↗</span>
            </a>
          </div>
        </ScrollReveal>

        {/* Real BJT Dashboard Style & Data Preview */}
        <div className="mt-14 max-w-5xl mx-auto text-left rounded-xl border border-border/90 bg-card shadow-2xl shadow-primary/10 overflow-hidden transition-all hover:border-primary/40">
          {/* Top Mock Window Bar */}
          <div className="flex items-center justify-between border-b border-border/60 bg-muted/40 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-destructive/60" />
              <span className="h-3 w-3 rounded-full bg-amber-400/60" />
              <span className="h-3 w-3 rounded-full bg-emerald-500/60" />
              <span className="ml-2 text-xs font-mono text-muted-foreground">app.backgroundjobtracker.com/projects</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium">
                ● Live Telemetry
              </Badge>
            </div>
          </div>

          {/* Real BJT App Content Preview */}
          <div className="p-4 sm:p-6 space-y-5 bg-background">
            {/* Top Stat Summary Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              <div className="p-3.5 rounded-lg border bg-card/60">
                <p className="text-xs font-medium text-muted-foreground">Active Jobs</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <p className="text-2xl font-bold text-foreground">14</p>
                  <span className="text-[11px] font-medium text-emerald-600">● 100% Active</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg border bg-card/60">
                <p className="text-xs font-medium text-muted-foreground">Executions / 24h</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <p className="text-2xl font-bold text-foreground">12,840</p>
                  <span className="text-[11px] text-muted-foreground">99.8% Success</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg border bg-card/60">
                <p className="text-xs font-medium text-muted-foreground">P95 Latency</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <p className="text-2xl font-bold text-foreground">240ms</p>
                  <span className="text-[11px] text-emerald-600">↓ -14ms</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg border bg-card/60 border-amber-500/30 bg-amber-500/5">
                <p className="text-xs font-medium text-amber-600 dark:text-amber-400">Active Incidents</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">1</p>
                  <span className="text-[11px] text-amber-600 font-medium">INC-14 DEGRADED</span>
                </div>
              </div>
            </div>

            {/* Active Incident Alert Banner */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300 text-xs">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                <span>
                  <strong className="font-semibold">INC-14 (DEGRADED):</strong> High Failure Rate detected on <code className="font-mono bg-amber-500/20 px-1 py-0.5 rounded">sync_user_stripe_events</code> (Current: 15.5% vs Threshold: 10%)
                </span>
              </div>
              <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-300 hidden sm:inline-flex">
                Investigating
              </Badge>
            </div>

            {/* Table Mockup */}
            <div className="rounded-lg border bg-card overflow-hidden">
              <div className="px-4 py-3 border-b bg-muted/30 grid grid-cols-12 gap-2 items-center text-xs font-semibold text-muted-foreground">
                <span className="col-span-4 sm:col-span-4">Task Identifier</span>
                <span className="col-span-2 text-center">Framework</span>
                <span className="col-span-3 sm:col-span-2 text-center">Status</span>
                <span className="hidden sm:block sm:col-span-2 text-right">P95 Latency</span>
                <span className="col-span-3 sm:col-span-2 text-right">Last Event</span>
              </div>

              <div className="divide-y divide-border/60 text-xs">
                {/* Row 1 */}
                <div className="px-4 py-3.5 grid grid-cols-12 gap-2 items-center hover:bg-muted/30 transition-colors">
                  <div className="col-span-4 sm:col-span-4 flex flex-col min-w-0">
                    <span className="font-semibold text-foreground truncate">send_welcome_email</span>
                    <span className="text-[11px] text-muted-foreground truncate">Project: Core-Backend</span>
                  </div>
                  <div className="col-span-2 flex justify-center">
                    <Badge variant="outline" className="font-mono text-[10px] uppercase">Celery</Badge>
                  </div>
                  <div className="col-span-3 sm:col-span-2 flex justify-center">
                    <Badge variant="outline" className="border-green-500/40 text-green-600 bg-green-500/10">HEALTHY</Badge>
                  </div>
                  <div className="hidden sm:block sm:col-span-2 text-right font-mono text-muted-foreground">
                    145ms
                  </div>
                  <div className="col-span-3 sm:col-span-2 text-right text-muted-foreground">
                    10s ago
                  </div>
                </div>

                {/* Row 2 */}
                <div className="px-4 py-3.5 grid grid-cols-12 gap-2 items-center hover:bg-muted/30 transition-colors bg-amber-500/5">
                  <div className="col-span-4 sm:col-span-4 flex flex-col min-w-0">
                    <span className="font-semibold text-foreground truncate">sync_user_stripe_events</span>
                    <span className="text-[11px] text-muted-foreground truncate">Project: Payments-Worker</span>
                  </div>
                  <div className="col-span-2 flex justify-center">
                    <Badge variant="outline" className="font-mono text-[10px] uppercase">Celery</Badge>
                  </div>
                  <div className="col-span-3 sm:col-span-2 flex justify-center">
                    <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 border-amber-500/20">DEGRADED</Badge>
                  </div>
                  <div className="hidden sm:block sm:col-span-2 text-right font-mono text-muted-foreground">
                    1,820ms
                  </div>
                  <div className="col-span-3 sm:col-span-2 text-right text-muted-foreground">
                    2s ago
                  </div>
                </div>

                {/* Row 3 */}
                <div className="px-4 py-3.5 grid grid-cols-12 gap-2 items-center hover:bg-muted/30 transition-colors">
                  <div className="col-span-4 sm:col-span-4 flex flex-col min-w-0">
                    <span className="font-semibold text-foreground truncate">generate_monthly_invoice</span>
                    <span className="text-[11px] text-muted-foreground truncate">Project: Billing-Engine</span>
                  </div>
                  <div className="col-span-2 flex justify-center">
                    <Badge variant="outline" className="font-mono text-[10px] uppercase">Celery</Badge>
                  </div>
                  <div className="col-span-3 sm:col-span-2 flex justify-center">
                    <Badge variant="outline" className="border-green-500/40 text-green-600 bg-green-500/10">HEALTHY</Badge>
                  </div>
                  <div className="hidden sm:block sm:col-span-2 text-right font-mono text-muted-foreground">
                    480ms
                  </div>
                  <div className="col-span-3 sm:col-span-2 text-right text-muted-foreground">
                    1m ago
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
