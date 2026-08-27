import { JobExecutionsClient } from "./job-executions-client";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Job Executions | Background Job Tracker",
  description: "Detailed execution telemetry, logs, and timeline for a background job",
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function JobExecutionsPage({ params }: Props) {
  const resolvedParams = await params;
  const jobId = parseInt(resolvedParams.id, 10);

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-7xl mx-auto">
      <JobExecutionsClient jobId={jobId} />
    </div>
  );
}
