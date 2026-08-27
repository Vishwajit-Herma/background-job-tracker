import { JobReliabilityClient } from "./job-reliability-client";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Job Reliability | Background Job Tracker",
  description: "Reliability analysis, schedule expectations, baselines, and findings for a background job",
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function JobReliabilityPage({ params }: Props) {
  const resolvedParams = await params;
  const jobId = parseInt(resolvedParams.id, 10);

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-7xl mx-auto">
      <JobReliabilityClient jobId={jobId} />
    </div>
  );
}
