# 🤖 AIOps Log Intelligence — ReAct Agent Pipeline

> **Name:** sachin sooraj  
> **Track:** AI/ML Engineering  
> **Lab Name:** AIOps Log Intelligence  
> **Email:** [sachin.s@thinkpalm.com]

---

## 📌 What It Does

This project implements an **AIOps (AI for IT Operations)** pipeline that simulates real-world log intelligence using a **ReAct (Reason + Act) agent** pattern:

1. **Ingests** a raw application log file (`app.log`)
2. **Classifies** every ERROR/WARN line using **Claude LLM** (via Anthropic API) — assigning a severity level and a concrete remediation action
3. **Probes** service health for CRITICAL/HIGH alerts using `check_logs()` — simulates a Prometheus/kubectl health probe
4. **Auto-remediates** crashed or failed pods using `restart_pod()` — simulates `kubectl rollout restart`
5. **Outputs** a colour-coded alert table to the terminal and saves structured JSON

### Three ReAct Tools

| Tool | Purpose |
|---|---|
| `classify_errors()` | Sends log entries to Claude API; returns severity + fix per entry |
| `check_logs(service)` | Simulates health probe — returns pod status, restart count, CPU/mem |
| `restart_pod(service)` | Simulates rolling pod restart for Crashed/Failed/Unhealthy services |

---

## 🗂️ Repo Structure

```
thinkpalm-agentai-[YourName]-AIOpsLogIntelligence/
├── src/
│   ├── aiops_log_analyzer.py   ← Main ReAct agent script
│   └── app.log                 ← Sample input log file (15 entries)
├── screenshots/
│   ├── 01_terminal_output.png  ← Colour-coded alert table
│   ├── 02_react_loop.png       ← ReAct loop (check_logs + restart_pod)
│   └── 03_json_output.png      ← alert_summary.json output
├── aiops_report.pdf            ← Full PDF: log → prompt → script → output
├── requirements.txt
└── README.md
```

---

## 🚀 How to Run

### 1. Clone & install

```bash
git clone https://github.com/sachinsooraj/thinkpalm-agentai-sachinsooraj-AI-Assisted-Log-Analysis-Alert-Triage.git
cd thinkpalm-agentai-sachinsooraj-AI-Assisted-Log-Analysis-Alert-Triage
pip install -r requirements.txt
```

### 2. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

> **No API key?** The script automatically falls back to cached sample data so you can still see the full ReAct loop in action.

### 3. Run the analyzer

```bash
cd src
python3 aiops_log_analyzer.py
```

Optional flags:
```bash
python3 aiops_log_analyzer.py --log app.log --out alert_summary.json
```

### 4. Expected output

```
══════════════════════════════════════════════════════════════════
  AIOps Log Intelligence — ReAct Agent
  Model: claude-sonnet-4-20250514
══════════════════════════════════════════════════════════════════

📂  Parsing 'app.log' …
    Found 12 ERROR/WARN entries.

  [TOOL 1] classify_errors — calling Claude API …
  ✓ Classified 12 entries.  Time: 2.3s

🔁  Running ReAct loop (check_logs + restart_pod) …
  [CRITICAL] JVM          → check_logs: status=Degraded restarts=3
  [CRITICAL] Database     → check_logs: status=Unhealthy restarts=0
      ↳ restart_pod: kubectl rollout restart deploy/database
  [HIGH]     Auth         → check_logs: status=Running restarts=1
  [CRITICAL] TLS/API      → check_logs: status=Failed restarts=5
      ↳ restart_pod: kubectl rollout restart deploy/tls-api
  ...

  AIOps Alert Summary
+---------------------+------------------------------------+----------+--------------------------------------------+
| TIMESTAMP           | ERROR                              | SEVERITY | SUGGESTED FIX                              |
+=====================+====================================+==========+============================================+
| 2024-05-21 08:05:33 | Java Heap OutOfMemoryError         | CRITICAL | Increase JVM heap; add -Xmx4g to flags.   |
| 2024-05-21 08:09:55 | DB Connection Timeout 3 retries    | CRITICAL | Check db-prod-01; scale connection pool.   |
...

✅  Saved → alert_summary.json
```

---

## 🛠️ Tools Used

| Tool / Library | Purpose |
|---|---|
| **Python 3.12** | Core language |
| **Anthropic Claude API** (`claude-sonnet-4-20250514`) | LLM error classification |
| **urllib** (stdlib) | HTTP calls to Claude API — zero extra dependencies |
| **re / json** (stdlib) | Log parsing and structured output |
| **reportlab** | PDF report generation |
| **ReAct pattern** | Reason → Act loop chaining 3 tools |

---

## 💡 Observations

1. **LLM as triage engine:** A single Claude API call (batching all 12 log entries) classified every error with contextually accurate severity — e.g., it correctly rated the expired TLS cert as CRITICAL (not just MEDIUM) because it affects all internal services, not just one endpoint. This would take a human SRE 5–10 minutes manually.

2. **ReAct loop adds real value:** Chaining `check_logs()` after `classify_errors()` meant the agent didn't just surface alerts — it probed actual pod health and made restart decisions. This mirrors a real on-call runbook: "Alert fires → check health → restart if crashed." The third tool (`restart_pod`) turned a passive dashboard into an active remediation system.

3. **Prompt structure matters:** Asking Claude to include a `"service"` field (beyond timestamp/error/severity/fix) unlocked the ability to route each alert to the correct health probe in the ReAct loop — a small prompt change that dramatically increased downstream utility.

4. **Zero-dependency API calls:** Using Python's built-in `urllib` instead of the `anthropic` SDK kept the dependency footprint minimal, making the script portable to any Python 3.8+ environment without pip install.

5. **Fallback design:** The script gracefully degrades when no API key is set — the ReAct loop still runs with sample data, so the full tool-chaining behaviour is demonstrable in any environment.

---

## 📄 PDF Report

`aiops_report.pdf` (included in this repo) contains:
- ① Original log file
- ② LLM prompt used (Copilot-assisted)
- ③ Full annotated script
- ④ Sample output table + terminal simulation
- ⑤ 2-line productivity note

---
