"use client";

import { useQuery } from "@tanstack/react-query";
import { getJobReliability, ReliabilityState } from "@/lib/api/reliability";
import { useWorkspace } from "@/hooks/use-workspace";
import { JobHeader } from "@/components/bjt/jobs/job-header";
import { CurrentStatusCard } from "@/components/bjt/reliability/current-status-card";
import { ExpectationCard } from "@/components/bjt/reliability/expectation-card";
import { BaselineCard } from "@/components/bjt/reliability/baseline-card";
import { ReliabilityActivity } from "@/components/bjt/reliability/reliability-activity";
import { ReliabilityPageSkeleton } from "@/components/bjt/reliability/reliability-skeletons";
import { ErrorState } from "@/components/bjt/states";

interface JobReliabilityClientProps {
  jobId: number;
}

export function JobReliabilityClient({ jobId }: JobReliabilityClientProps) {
  const { jobs, projectMap, canManageProject, isLoading: isLoadingWorkspace } = useWorkspace();

  const {
    data: reliability,
    isLoading: isLoadingReliability,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["job-reliability", jobId],
    queryFn: () => getJobReliability(jobId),
  });

  const job = jobs.find((j) => j.id === jobId);
  const project = job ? projectMap.get(job.project) : null;
  const canManage = project ? canManageProject(project.id) : false;

  const isLoading = isLoadingReliability || isLoadingWorkspace;

  if (isLoading) {
    return <ReliabilityPageSkeleton />;
  }

  if (isError || !reliability) {
    return (
      <div className="space-y-6">
        <ErrorState
          title="Unable to load job reliability"
          description="Failed to fetch reliability metrics and expectation configuration for this job."
          retry={() => { refetch(); }}
        />
      </div>
    );
  }

  const jobHeaderInfo = {
    id: reliability.job_id,
    name: reliability.job_name,
    task_identifier: reliability.task_identifier,
    status: job?.status || "active",
    operational_status: job?.operational_status,
    reliability_state: (reliability.is_enabled ? reliability.current_state : "DISABLED") as ReliabilityState | "DISABLED",
    project_id: project?.id,
    project_name: project?.name,
  };

  return (
    <div className="space-y-6">
      {/* Shared Job Header with Tabs */}
      <JobHeader job={jobHeaderInfo} />

      {/* Main 2-Column Grid: Status & Expectations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <CurrentStatusCard reliability={reliability} />
        <ExpectationCard reliability={reliability} canManage={canManage} />
      </div>

      {/* Baseline Section */}
      <BaselineCard jobId={jobId} baseline={reliability.baseline} canManage={canManage} />

      {/* Reliability Activity Section */}
      <ReliabilityActivity
        activeFindings={reliability.active_findings}
        recentFindings={reliability.recent_findings}
      />
    </div>
  );
}
