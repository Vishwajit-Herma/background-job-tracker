"use client";

import { Layers, Server, Database, Cpu, Globe, Terminal, Shield, ExternalLink, Package } from "lucide-react";

const stackItems = [
  { name: "Python 3.8 - 3.14+", type: "Runtime", icon: Terminal },
  { name: "Celery", type: "Task Queue", icon: Cpu },
  { name: "Django 5.x", type: "Framework", icon: Layers },
  { name: "FastAPI", type: "Framework", icon: Layers },
  { name: "Flask / Standalone", type: "Framework / Script", icon: Layers },
  { name: "Redis", type: "Broker / Cache", icon: Server },
  { name: "PostgreSQL", type: "Database", icon: Database },
  { name: "REST API", type: "OpenAPI 3.0", icon: Globe },
  { name: "Webhooks", type: "Alert Delivery", icon: Shield },
];

export function LandingStack() {
  return (
    <section id="stack" className="py-16 bg-muted/30 border-t border-border/60">
      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-primary mb-2">
          Supported Technology Stack
        </h2>
        <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mb-3">
          Works Seamlessly With Your Stack
        </h3>
        <p className="text-sm text-muted-foreground max-w-2xl mx-auto mb-8">
          BJT supports Celery and Python background tasks across <strong>Django</strong>, <strong>FastAPI</strong>, <strong>Flask</strong>, and <strong>standalone Python scripts</strong>, as well as any REST client.
        </p>

        {/* PyPI SDK Link Banner */}
        <div className="inline-flex items-center gap-2 px-4 py-2 mb-8 rounded-full border border-primary/30 bg-primary/10 text-xs text-primary font-medium">
          <Package className="h-4 w-4 text-primary" />
          <span>Official Python SDK on PyPI:</span>
          <a
            href="https://pypi.org/project/background-job-tracker/"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold underline hover:text-primary/80 inline-flex items-center gap-1"
          >
            background-job-tracker
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3.5 max-w-5xl mx-auto">
          {stackItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.name}
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg border border-border/70 bg-card shadow-xs hover:border-primary/40 transition-all"
              >
                <Icon className="h-4 w-4 text-primary shrink-0" />
                <div className="flex flex-col text-left">
                  <span className="font-semibold text-sm text-foreground leading-tight">
                    {item.name}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {item.type}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
