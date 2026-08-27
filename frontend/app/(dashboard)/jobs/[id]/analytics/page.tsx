import { JobAnalyticsClient } from "./job-analytics-client";
import { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = {
  title: "Job Analytics | Background Job Tracker",
  description: "Analytics and observability for a specific background job",
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function JobAnalyticsPage({ params }: Props) {
  const resolvedParams = await params;
  const jobId = parseInt(resolvedParams.id, 10);

  return (
    <div className="container mx-auto py-8">
      <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading job analytics...</div>}>
        <JobAnalyticsClient jobId={jobId} />
      </Suspense>
    </div>
  );
}
