# AI Reliability Assistant

The **AI Reliability Assistant** provides grounded, evidence-backed investigation and remediation guidance for active and historical background task incidents.

---

## 🔍 How It Works

When an incident occurs, the AI Reliability Assistant gathers domain context and telemetry:
1. **Representative Failed Executions:** Recent error types, error messages, and formatted application tracebacks.
2. **Telemetry Correlates:** Queue latencies, affected worker nodes, retry counts, and duration metrics.
3. **Incident Intelligence:** Anomaly metrics, baseline deviations, and initial probable cause hypotheses.
4. **Historical Knowledge:** Existing postmortems and associated mitigation runbooks.

The AI assistant analyzes this telemetry payload and generates a structured, verified diagnosis.

---

## 🛡️ Grounding & Evidence-Based Reasoning

To prevent hallucinations, the engine strictly enforces grounding rules:

### 1. Distinct Evidence Categories
Every claim in the AI response is anchored to an empirical evidence source:
- `execution`: Error details, stack frames, or runtime durations observed in task executions.
- `incident`: Trigger time, severity, status, or alert rule context.
- `analytics`: Queue wait time spikes or aggregate failure percentages.
- `reliability`: Historical baseline comparisons or SLA deviations.
- `runbook`: Mitigation playbook steps.
- `postmortem`: Confirmed conclusions from prior resolutions.

### 2. Confidence Estimation
Every investigation response includes a confidence rating:
- **`HIGH`**: Strong, direct evidence present in tracebacks and telemetry.
- **`MEDIUM`**: Clear correlation across multiple signals, but missing exact root-cause frame.
- **`LOW`**: Partial or noisy telemetry.
- **`INSUFFICIENT_EVIDENCE`**: Telemetry does not contain enough data to draw safe conclusions.

---

## 📡 API Endpoint

### Investigate an Incident

`POST /api/incidents/<incident_id>/ai-investigate/`

#### Request Payload
```json
{
  "question": "Why did this incident trigger, and what should we check first?"
}
```

#### Response Structure
```json
{
  "answer": "The incident was triggered by a connection timeout in `reports.tasks.generate_pdf` when attempting to reach the remote rendering engine...",
  "confidence": "HIGH",
  "evidence": [
    {
      "source": "execution",
      "reference_id": "job-42",
      "fact": "Execution failed with ConnectionTimeoutError at line 84 in renderer.py."
    },
    {
      "source": "analytics",
      "reference_id": "queue-reports",
      "fact": "Failure rate spiked to 84% over the last 15-minute window."
    }
  ],
  "recommendations": [
    {
      "action": "Check health of the internal rendering microservice at render-worker-02.",
      "reason": "All failed executions timed out after 30 seconds connecting to this endpoint."
    }
  ]
}
```
