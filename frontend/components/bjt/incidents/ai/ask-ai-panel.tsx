"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  investigateIncidentAI,
  AIInvestigationResponse,
  AIConfidenceLevel,
  AIEvidenceSource,
} from "@/lib/api/ai";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  Send,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  BookOpen,
  Activity,
  FileText,
  Clock,
  ShieldCheck,
  Zap,
  ArrowRight,
  GripVertical,
} from "lucide-react";
import { toastError } from "@/lib/toast";

interface AskAIPanelProps {
  incidentId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectTab?: (tab: string) => void;
}

const SUGGESTED_QUESTIONS = [
  "Summarize this incident",
  "Why did this incident happen?",
  "What was affected?",
  "What should I investigate first?",
  "Have we seen this before?",
  "Which runbook is relevant?",
];

const MIN_WIDTH = 420;
const MAX_WIDTH_VW = 0.9; // 90vw

function getConfidenceBadge(confidence: AIConfidenceLevel) {
  switch (confidence) {
    case "HIGH":
      return (
        <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 font-medium">
          <CheckCircle2 className="h-3 w-3 mr-1" /> High Confidence
        </Badge>
      );
    case "MEDIUM":
      return (
        <Badge className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 font-medium">
          <Activity className="h-3 w-3 mr-1" /> Medium Confidence
        </Badge>
      );
    case "LOW":
      return (
        <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 font-medium">
          <AlertTriangle className="h-3 w-3 mr-1" /> Low Confidence
        </Badge>
      );
    case "INSUFFICIENT_EVIDENCE":
    default:
      return (
        <Badge className="bg-muted text-muted-foreground border-border font-medium">
          <HelpCircle className="h-3 w-3 mr-1" /> Insufficient Evidence
        </Badge>
      );
  }
}

function getSourceIcon(source: AIEvidenceSource) {
  switch (source) {
    case "incident":
    case "incident_event":
      return <Clock className="h-3.5 w-3.5 text-blue-500 shrink-0" />;
    case "incident_intelligence":
      return <Sparkles className="h-3.5 w-3.5 text-violet-500 shrink-0" />;
    case "analytics":
    case "execution":
      return <Activity className="h-3.5 w-3.5 text-amber-500 shrink-0" />;
    case "reliability":
      return <ShieldCheck className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
    case "runbook":
      return <BookOpen className="h-3.5 w-3.5 text-cyan-500 shrink-0" />;
    case "postmortem":
      return <FileText className="h-3.5 w-3.5 text-purple-500 shrink-0" />;
    default:
      return <Activity className="h-3.5 w-3.5 text-muted-foreground shrink-0" />;
  }
}

function formatSourceLabel(source: AIEvidenceSource): string {
  return source.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function AskAIPanel({ incidentId, open, onOpenChange, onSelectTab }: AskAIPanelProps) {
  const [question, setQuestion] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [response, setResponse] = useState<AIInvestigationResponse | null>(null);

  // Resizable panel state
  const [panelWidth, setPanelWidth] = useState(520);
  const isDragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);

  const mutation = useMutation({
    mutationFn: (q: string) => investigateIncidentAI(incidentId, q),
    onSuccess: (data, variables) => {
      setResponse(data);
      setLastQuestion(variables);
    },
    onError: (err: any) => {
      toastError("Failed to analyze incident with AI", err);
    },
  });

  const handleSubmit = (qToSubmit?: string) => {
    const query = (qToSubmit || question).trim();
    if (!query || mutation.isPending) return;
    mutation.mutate(query);
  };

  const handleChipClick = (suggested: string) => {
    setQuestion(suggested);
    handleSubmit(suggested);
  };

  // --- Resize logic ---
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    dragStartX.current = e.clientX;
    dragStartWidth.current = panelWidth;
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  }, [panelWidth]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = dragStartX.current - e.clientX; // dragging left = wider
      const maxWidth = window.innerWidth * MAX_WIDTH_VW;
      const newWidth = Math.min(maxWidth, Math.max(MIN_WIDTH, dragStartWidth.current + delta));
      setPanelWidth(newWidth);
    };
    const onMouseUp = () => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        style={{ width: `${panelWidth}px`, maxWidth: "90vw" }}
        className="p-0 flex flex-col h-full bg-background border-l shadow-2xl overflow-hidden transition-none"
      >
        {/* Drag Handle — left edge */}
        <div
          onMouseDown={onMouseDown}
          className="absolute left-0 top-0 bottom-0 w-1.5 cursor-ew-resize group z-50 flex items-center"
          title="Drag to resize"
        >
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-border/0 group-hover:bg-primary/20 transition-colors rounded-l" />
          <GripVertical className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary/50 absolute left-0 top-1/2 -translate-y-1/2 transition-colors" />
        </div>

        {/* Header */}
        <SheetHeader className="pl-6 pr-5 py-5 border-b bg-muted/20 shrink-0">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                <Sparkles className="h-4 w-4 animate-pulse" />
              </div>
              <div className="min-w-0">
                <SheetTitle className="text-base font-semibold flex items-center gap-2 flex-wrap">
                  AI Reliability Assistant
                  <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0 shrink-0">
                    INC-{incidentId}
                  </Badge>
                </SheetTitle>
                <SheetDescription className="text-xs text-muted-foreground mt-0.5 leading-snug">
                  Context-grounded explanation based strictly on observed BJT telemetry.
                </SheetDescription>
              </div>
            </div>
            {/* Width indicator */}
            <span className="text-[10px] text-muted-foreground/50 font-mono shrink-0 hidden sm:block">
              {Math.round(panelWidth)}px
            </span>
          </div>
        </SheetHeader>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto pl-6 pr-5 py-6 space-y-6">
          {/* Query Input Box */}
          <div className="space-y-3">
            <div className="relative">
              <Textarea
                placeholder="Ask about root cause, impact, timeline, or runbooks…"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                rows={3}
                className="resize-none pr-12 text-sm focus-visible:ring-primary break-words"
              />
              <Button
                size="icon"
                variant="default"
                disabled={!question.trim() || mutation.isPending}
                onClick={() => handleSubmit()}
                className="absolute bottom-2.5 right-2.5 h-8 w-8 rounded-md"
              >
                {mutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>

            {/* Quick Prompt Chips */}
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">Suggested Prompts</p>
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTED_QUESTIONS.map((sq) => (
                  <button
                    key={sq}
                    type="button"
                    onClick={() => handleChipClick(sq)}
                    disabled={mutation.isPending}
                    className="text-xs bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 rounded-full px-3 py-1 transition-colors text-left flex items-center gap-1 disabled:opacity-50"
                  >
                    <span>{sq}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Loading State */}
          {mutation.isPending && (
            <div className="p-8 rounded-xl border border-dashed border-primary/30 bg-primary/5 flex flex-col items-center justify-center text-center space-y-3 animate-in fade-in duration-300">
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
              <div>
                <p className="text-sm font-medium">Analyzing Incident Telemetry…</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                  Grounding response with timeline events, error baselines, correlations, and runbook history.
                </p>
              </div>
            </div>
          )}

          {/* Error Banner for High Model Demand */}
          {mutation.isError && !mutation.isPending && (
            <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-950 dark:text-amber-200 text-xs space-y-1.5 animate-in fade-in duration-300">
              <div className="flex items-center gap-2 font-semibold text-sm text-amber-800 dark:text-amber-300">
                <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                High Model Usage
              </div>
              <p className="leading-relaxed text-xs">
                The AI provider is currently experiencing high demand. Automatic retries were attempted, but the service remains busy. Please try again in a few moments.
              </p>
            </div>
          )}

          {/* Response Container */}
          {response && !mutation.isPending && (
            <div className="space-y-6 animate-in fade-in duration-300">
              {/* Question Echo & Confidence */}
              <div className="flex items-start justify-between gap-3 border-b pb-3">
                <div className="flex items-start gap-1.5 text-xs text-muted-foreground min-w-0">
                  <span className="font-semibold text-foreground shrink-0">Q:</span>
                  {/* ✅ wraps instead of truncating */}
                  <span className="break-words">{lastQuestion}</span>
                </div>
                <div className="shrink-0">{getConfidenceBadge(response.confidence)}</div>
              </div>

              {/* AI Answer */}
              <div className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-primary uppercase tracking-wider">
                  <Sparkles className="h-3.5 w-3.5 shrink-0" /> AI Analysis &amp; Synthesis
                </div>
                {/* ✅ whitespace-pre-wrap + break-words for full text wrapping */}
                <div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap break-words">
                  {response.answer}
                </div>
              </div>

              {/* Observed Evidence */}
              {response.evidence && response.evidence.length > 0 && (
                <div className="rounded-xl border border-border/80 bg-muted/20 p-5 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                      Observed Empirical Evidence ({response.evidence.length})
                    </h4>
                    <span className="text-[10px] text-muted-foreground font-mono shrink-0">BJT Grounding</span>
                  </div>
                  <div className="space-y-2.5">
                    {response.evidence.map((ev, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg border bg-background text-xs space-y-1.5 shadow-2xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium flex items-center gap-1.5 text-foreground">
                            {getSourceIcon(ev.source)}
                            {formatSourceLabel(ev.source)}
                          </span>
                          {ev.reference_id && (
                            <Badge variant="secondary" className="text-[10px] font-mono px-1.5 py-0 shrink-0">
                              {ev.reference_id}
                            </Badge>
                          )}
                        </div>
                        {/* ✅ evidence facts wrap fully */}
                        <p className="text-muted-foreground text-xs leading-normal break-words whitespace-pre-wrap">
                          {ev.fact}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {response.recommendations && response.recommendations.length > 0 && (
                <div className="rounded-xl border bg-card p-5 space-y-3 shadow-sm">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-amber-500 shrink-0" /> Recommended Actions ({response.recommendations.length})
                  </h4>
                  <div className="space-y-2.5">
                    {response.recommendations.map((rec, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs space-y-1.5"
                      >
                        {/* ✅ action text wraps */}
                        <p className="font-medium text-foreground flex items-start gap-1.5 text-sm">
                          <ArrowRight className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                          <span className="break-words">{rec.action}</span>
                        </p>
                        <p className="text-muted-foreground text-xs pl-5.5 break-words leading-relaxed">
                          {rec.reason}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Footer hint */}
              <p className="text-[10px] text-center text-muted-foreground">
                AI Reliability Assistant provides explanations and recommendations based on BJT telemetry. It does not perform autonomous changes.
              </p>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
