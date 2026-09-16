"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { ScrollReveal } from "@/components/bjt/landing/scroll-reveal";
import { ArrowRight, Sparkles, CheckCircle2 } from "lucide-react";

export function LandingFooter() {
  return (
    <footer className="border-t border-border/60 bg-background">
      {/* Modern Card Call to Action Section */}
      <div className="py-16 md:py-20 px-4 sm:px-6 lg:px-8">
        <ScrollReveal>
          <div className="max-w-5xl mx-auto rounded-2xl border border-border/80 bg-card p-8 sm:p-12 md:py-16 text-center relative overflow-hidden shadow-2xl shadow-primary/10 hover:border-primary/40 transition-all duration-500 group">
            {/* Background Ambient Glow Orbs */}
            <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-primary/10 dark:bg-primary/20 blur-[120px] rounded-full pointer-events-none animate-pulse duration-10000" />
            <div className="absolute -bottom-24 right-10 w-72 h-72 bg-blue-500/10 blur-[90px] rounded-full pointer-events-none" />

            {/* Inner Content */}
            <div className="relative z-10 max-w-3xl mx-auto">
              {/* Badge */}
              <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/5 px-3.5 py-1 text-xs font-medium text-primary mb-5 shadow-xs">
                <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                <span>Start Monitoring In Minutes</span>
              </div>

              {/* Headline */}
              <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-foreground leading-[1.2] mb-4">
                Stop wondering what happened to your <span className="bg-gradient-to-r from-primary via-blue-600 to-indigo-600 bg-clip-text text-transparent">background jobs.</span>
              </h2>

              {/* Subtext */}
              <p className="text-base sm:text-lg text-muted-foreground mb-8 max-w-xl mx-auto leading-relaxed">
                Get complete real-time visibility into your tasks, latency percentiles, and reliability incidents today.
              </p>

              {/* Action Buttons */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link 
                  href="/register" 
                  className={buttonVariants({ size: "lg", className: "group w-full sm:w-auto bg-primary text-primary-foreground shadow-lg shadow-primary/15 hover:shadow-xl hover:shadow-primary/25 hover:bg-primary/95 hover:-translate-y-0.5 transition-all duration-300 px-8 font-semibold" })}
                >
                  <span>Get Started Free</span>
                  <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1.5 transition-transform duration-300" />
                </Link>
                <a 
                  href="https://pypi.org/project/background-job-tracker/" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className={buttonVariants({ variant: "outline", size: "lg", className: "w-full sm:w-auto px-6 font-medium border-border/80 hover:bg-muted/70 transition-all duration-300" })}
                >
                  <span>Install PyPI SDK ↗</span>
                </a>
              </div>

              {/* Trust Features */}
              <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-xs text-muted-foreground font-medium">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <span>3-line SDK setup</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <span>Zero worker performance impact</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <span>Celery & RQ support</span>
                </div>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>

      {/* Main Footer Content */}
      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 border-b border-border/50 pb-8">
          <div className="flex items-center gap-3">
            <img
              src="/bjt-logo-clean.png"
              alt="BJT Logo"
              className="h-8 w-auto object-contain dark:hidden"
            />
            <img
              src="/bjt-logo-dark.png"
              alt="BJT Logo"
              className="h-8 w-auto object-contain hidden dark:block"
            />
            <div>
              <p className="font-bold text-base text-foreground leading-none">BJT</p>
              <p className="text-xs text-muted-foreground">Background Job Tracker</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-xs text-muted-foreground font-medium">
            <a href="#how-it-works" className="hover:text-foreground transition-colors">How It Works</a>
            <a href="#features" className="hover:text-foreground transition-colors">Features</a>
            <a href="https://background-job-tracker.readthedocs.io/en/latest/" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">Documentation ↗</a>
            <a href="https://pypi.org/project/background-job-tracker/" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">PyPI Package ↗</a>
            <Link href="/login" className="hover:text-foreground transition-colors">Login</Link>
            <Link href="/register" className="hover:text-foreground transition-colors">Register</Link>
          </div>
        </div>

        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-muted-foreground gap-4">
          <p>© {new Date().getFullYear()} Background Job Tracker. All rights reserved.</p>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span>Platform Operational</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
