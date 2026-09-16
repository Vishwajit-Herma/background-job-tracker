"use client";

import { 
  ListChecks, 
  Activity, 
  LineChart, 
  AlertTriangle, 
  BellRing, 
  CheckCircle2,
  ChevronRight
} from "lucide-react";

import { ScrollReveal } from "@/components/bjt/landing/scroll-reveal";

const steps = [
  {
    num: "01",
    title: "Job Discovery",
    desc: "SDK automatically registers background task signatures from your Celery, Django, or FastAPI code.",
    icon: ListChecks,
  },
  {
    num: "02",
    title: "Telemetry Stream",
    desc: "Lightweight async sender batches execution start, finish, retry, and duration events.",
    icon: Activity,
  },
  {
    num: "03",
    title: "Health Monitoring",
    desc: "Aggregates P50/P95 latency percentiles, failure rates, and execution counts per project.",
    icon: LineChart,
  },
  {
    num: "04",
    title: "Failure Analysis",
    desc: "Extracts tracebacks, categorizes error types, and deduplicates repeated error signatures with AI.",
    icon: AlertTriangle,
  },
  {
    num: "05",
    title: "Alert Evaluation",
    desc: "Evaluates thresholds for high failure rates, retries, or execution volume anomalies for Webhooks.",
    icon: BellRing,
  },
  {
    num: "06",
    title: "Incident Resolution",
    desc: "Generates actionable incidents with automated runbooks and team assignment workflows.",
    icon: CheckCircle2,
  },
];

export function LandingPipeline() {
  return (
    <section id="how-it-works" className="py-20 bg-background border-t border-border/60">
      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <ScrollReveal>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-primary mb-2">
              Architecture Workflow
            </h2>
            <h3 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              How Background Job Tracker Works
            </h3>
            <p className="mt-4 text-base sm:text-lg text-muted-foreground">
              From execution telemetry to automated incident resolution, BJT gives you end-to-end visibility.
            </p>
          </div>
        </ScrollReveal>

        {/* Connected 6-Stage Timeline Flow with Staggered Scroll Reveal */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 relative">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <ScrollReveal key={step.num} delayMs={idx * 100}>
                <div
                  className="relative flex flex-col justify-between p-6 rounded-xl border border-border/80 bg-card/70 hover:border-primary/40 hover:bg-card hover:-translate-y-1 hover:shadow-lg transition-all duration-300 h-full"
                >
                  {/* Step Connector Indicator */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold">
                        <Icon className="h-5 w-5" />
                      </div>
                      <span className="text-xs font-mono font-bold text-primary px-2 py-0.5 rounded bg-primary/5 border border-primary/20">
                        STAGE {step.num}
                      </span>
                    </div>
                    <span className="text-xs font-mono font-medium text-muted-foreground">
                      Step {idx + 1} of 6
                    </span>
                  </div>

                  <div className="space-y-2">
                    <h4 className="text-lg font-bold text-foreground">
                      {step.title}
                    </h4>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {step.desc}
                    </p>
                  </div>
                </div>
              </ScrollReveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
