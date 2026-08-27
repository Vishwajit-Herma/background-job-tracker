import { JobAnalyticsClient } from "./job-analytics-client";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Job Analytics | Background Job Tracker",
  description: "Analytics and observability for a specific background job",
};

interface Props {
  params: { id: string };
}

export default async function JobAnalyticsPage({ params }: Props) {
  const resolvedParams = await params;
  const jobId = parseInt(resolvedParams.id, 10);

  return (
    <div className="container mx-auto py-8">
      <JobAnalyticsClient jobId={jobId} />
    </div>
  );
}
