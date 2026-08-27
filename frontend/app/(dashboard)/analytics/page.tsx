import { AnalyticsPageClient } from "./analytics-page-client";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analytics | Background Job Tracker",
  description: "Project background job analytics and observability",
};

export default function AnalyticsPage() {
  return (
    <div className="container mx-auto py-8">
      <AnalyticsPageClient />
    </div>
  );
}
