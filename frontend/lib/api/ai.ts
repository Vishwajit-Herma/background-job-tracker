import { apiClient } from "./client";

export type AIEvidenceSource =
  | "incident"
  | "incident_event"
  | "analytics"
  | "reliability"
  | "incident_intelligence"
  | "runbook"
  | "postmortem"
  | "execution";

export type AIConfidenceLevel = "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT_EVIDENCE";

export interface AIEvidenceItem {
  source: AIEvidenceSource;
  reference_id: string;
  fact: string;
}

export interface AIRecommendationItem {
  action: string;
  reason: string;
}

export interface AIInvestigationResponse {
  answer: string;
  confidence: AIConfidenceLevel;
  evidence: AIEvidenceItem[];
  recommendations: AIRecommendationItem[];
}

export interface AIInvestigationRequest {
  question: string;
}

/**
 * Send an incident question to the AI Reliability Assistant.
 */
export async function investigateIncidentAI(
  incidentId: number,
  question: string
): Promise<AIInvestigationResponse> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/ai/investigate/`, {
    question,
  });
  return res.data?.data ?? res.data;
}
