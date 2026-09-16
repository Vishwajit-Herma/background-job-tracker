import { Metadata } from "next";
import { LandingNav } from "@/components/bjt/landing/landing-nav";
import { LandingHero } from "@/components/bjt/landing/landing-hero";
import { LandingPipeline } from "@/components/bjt/landing/landing-pipeline";
import { LandingProductDemo } from "@/components/bjt/landing/landing-product-demo";
import { LandingFeatures } from "@/components/bjt/landing/landing-features";
import { LandingCodeTabs } from "@/components/bjt/landing/landing-code-tabs";
import { LandingStack } from "@/components/bjt/landing/landing-stack";
import { LandingFooter } from "@/components/bjt/landing/landing-footer";

export const metadata: Metadata = {
  title: "Background Job Tracker | Real-Time Background Job Telemetry & Reliability",
  description: "Track executions, monitor performance percentiles, and resolve background-job incidents in real time.",
};

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans selection:bg-primary/20 selection:text-primary">
      <LandingNav />
      <main className="flex-1">
        <LandingHero />
        <LandingPipeline />
        <LandingProductDemo />
        <LandingFeatures />
        <LandingCodeTabs />
        <LandingStack />
      </main>
      <LandingFooter />
    </div>
  );
}
