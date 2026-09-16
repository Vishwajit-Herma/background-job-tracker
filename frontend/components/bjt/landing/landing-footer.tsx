"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export function LandingFooter() {
  return (
    <footer className="border-t border-border/60 bg-card">
      {/* Call to Action Banner */}
      <div className="py-16 bg-gradient-to-br from-primary/10 via-background to-primary/5 border-b border-border/60">
        <div className="container mx-auto max-w-4xl px-4 text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground mb-4">
            Stop wondering what happened to your background jobs.
          </h2>
          <p className="text-base sm:text-lg text-muted-foreground mb-8 max-w-xl mx-auto">
            Get complete real-time visibility into your tasks, latency percentiles, and reliability incidents today.
          </p>
          <Link 
            href="/register" 
            className={buttonVariants({ size: "lg", className: "bg-primary text-primary-foreground shadow-md hover:bg-primary/90 px-8 font-semibold" })}
          >
            <span>Get Started Free</span>
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </div>
      </div>

      {/* Main Footer Content */}
      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 border-b border-border/50 pb-8">
          <div className="flex items-center gap-3">
            <img
              src="/bjt-logo-clean.png"
              alt="BJT Logo"
              className="h-8 w-auto object-contain"
            />
            <div>
              <p className="font-bold text-base text-foreground leading-none">BJT</p>
              <p className="text-xs text-muted-foreground">Background Job Tracker</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-xs text-muted-foreground font-medium">
            <a href="#how-it-works" className="hover:text-foreground transition-colors">How It Works</a>
            <a href="#features" className="hover:text-foreground transition-colors">Features</a>
            <a href="#code-example" className="hover:text-foreground transition-colors">SDK Code</a>
            <a href="https://pypi.org/project/background-job-tracker/" target="_blank" rel="noopener noreferrer" className="text-primary font-semibold hover:underline">PyPI Package ↗</a>
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
