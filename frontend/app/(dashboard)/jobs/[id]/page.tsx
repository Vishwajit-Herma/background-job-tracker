import { JobOverviewClient } from "./job-overview-client";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Job Details | Background Job Tracker",
  description: "Detailed overview and health monitoring for a background job",
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function JobPage({ params }: Props) {
  const resolvedParams = await params;
  const jobId = parseInt(resolvedParams.id, 10);

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-7xl mx-auto">
      <JobOverviewClient jobId={jobId} />
    </div>
  );
}
