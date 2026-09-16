# Alerting & Notifications

Background Job Tracker includes an alerting engine that detects reliability anomalies and dispatches alerts to team notification channels.

---

## 🔔 Alert Rules & Thresholds

Alert rules evaluate execution metrics across sliding time windows:

- **Failure Rate Threshold:** Trigger an incident if task error rate exceeds $X\%$ (e.g. $> 10\%$ over 5 minutes).
- **Consecutive Failures:** Trigger if a task crashes $N$ times consecutively.
- **Duration SLA Threshold:** Trigger if $p95$ or $p99$ execution duration exceeds $T$ seconds.
- **Queue Stall:** Trigger if tasks remain pending without worker consumption.

---

## 📢 Notification Channels

Configure notification endpoints per project:

| Channel Type | Description | Configuration |
|---|---|---|
| **Email** | Direct incident alerts sent via SMTP. | Recipient email addresses. |
| **Webhook** | HTTPS POST webhook with JSON payload. | Endpoint URL, HMAC secret key (`X-BJT-Signature`). |
| **In-App** | Real-time notification feed in the web dashboard. | Automatically enabled for team members. |

---

## 🛡️ Webhook Security & Signatures

Every webhook delivery includes security headers:
- `X-BJT-Signature`: `sha256=<HMAC-SHA256 signature of request body>`
- `X-BJT-Timestamp`: Epoch timestamp of when the webhook was generated
- `Content-Type`: `application/json`

### Example Webhook Verification (Python)
```python
import hmac
import hashlib

def verify_bjt_webhook(payload_bytes: bytes, secret: str, signature_header: str) -> bool:
    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)
```
