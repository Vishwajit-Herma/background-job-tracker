"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

export function LandingNav() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo & Name */}
        <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-90">
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
          <div className="flex flex-col">
            <span className="font-bold text-base tracking-tight leading-none text-foreground">
              BJT
            </span>
            <span className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
              Background Job Tracker
            </span>
          </div>
        </Link>

        {/* Center Nav Anchors */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
          <a href="#how-it-works" className="transition-colors hover:text-foreground">
            How It Works
          </a>
          <a href="#features" className="transition-colors hover:text-foreground">
            Features
          </a>
          <a href="#code-example" className="transition-colors hover:text-foreground">
            SDK & Code
          </a>
          <a href="#stack" className="transition-colors hover:text-foreground">
            Supported Stack
          </a>
          <a 
            href="https://pypi.org/project/background-job-tracker/" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="transition-colors hover:text-foreground inline-flex items-center gap-1 font-semibold text-primary"
          >
            PyPI Package ↗
          </a>
        </nav>

        {/* Right CTA Actions & Theme Toggle */}
        <div className="flex items-center gap-2.5">
          <ThemeToggle />
          <Link
            href="/login"
            className={buttonVariants({ variant: "ghost", size: "sm" })}
          >
            Login
          </Link>
          <Link
            href="/register"
            className={buttonVariants({
              variant: "default",
              size: "sm",
              className: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
            })}
          >
            <span>Get Started</span>
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </header>
  );
}
