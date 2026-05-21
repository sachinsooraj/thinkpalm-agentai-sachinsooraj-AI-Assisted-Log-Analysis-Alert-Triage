#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          AIOps Log Intelligence — ReAct Agent Pipeline          ║
║  Tools: classify_errors() · check_logs() · restart_pod()        ║
║  Lab   : AIOps Log Intelligence                                  ║
║  Track : AI/ML Engineering                                       ║
╚══════════════════════════════════════════════════════════════════╝

This script demonstrates a ReAct (Reason + Act) agent loop that:
  1. Ingests a raw log file
  2. Classifies errors via Claude LLM (classify_errors tool)
  3. Checks pod/service health for CRITICAL alerts (check_logs tool)
  4. Simulates a pod restart for crash-level severities (restart_pod tool)
  5. Prints a formatted alert table and saves structured JSON output

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 aiops_log_analyzer.py [--log app.log] [--out alert_summary.json]
"""

import re
import json
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
MODEL    = "claude-sonnet-4-20250514"
API_URL  = "https://api.anthropic.com/v1/messages"
# ─────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
SEV_COLORS = {
    "CRITICAL": "\033[91m",
    "HIGH":     "\033[93m",
    "MEDIUM":   "\033[94m",
    "LOW":      "\033[92m",
}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — classify_errors (LLM)
# ══════════════════════════════════════════════════════════════════════════════

def parse_log(path: str) -> list[dict]:
    """Extract ERROR/WARN lines with timestamp and message."""
    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(ERROR|WARN)\s+(.+)"
    )
    entries = []
    with open(path) as fh:
        for line in fh:
            m = pattern.match(line.strip())
            if m:
                entries.append({
                    "timestamp": m.group(1),
                    "level":     m.group(2),
                    "message":   m.group(3),
                })
    return entries


def classify_errors(entries: list[dict]) -> list[dict]:
    """
    TOOL 1 — classify_errors
    Sends log entries to Claude in a single API call.
    Returns a list of dicts with: timestamp, error, severity, suggested_fix.
    """
    print(f"\n  {BOLD}[TOOL 1] classify_errors{RESET} — calling Claude API …")

    log_block = "\n".join(
        f"[{e['timestamp']}] {e['level']}: {e['message']}"
        for e in entries
    )

    prompt = f"""You are an expert SRE / AIOps engineer.
Analyse the following log entries and for EACH one return a JSON array.
Each element must have exactly these keys:
  - "timestamp"    : original timestamp string
  - "error"        : short error label (<=8 words)
  - "severity"     : one of  CRITICAL | HIGH | MEDIUM | LOW
  - "suggested_fix": one concrete remediation action (<=15 words)
  - "service"      : inferred service/component name (1-3 words, e.g. "JVM", "Database", "Kafka")

Return ONLY the JSON array — no markdown fences, no commentary.

LOG ENTRIES:
{log_block}
"""
    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": 1800,
        "messages":   [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        API_URL, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        raw = data["content"][0]["text"].strip()
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
        alerts = json.loads(raw)
        print(f"  ✓ Classified {len(alerts)} entries.")
        return alerts
    except urllib.error.HTTPError as e:
        print(f"  ✗ API error {e.code}: {e.reason}. Using cached sample data.")
        return _sample_alerts()


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — check_logs (simulated pod/service health probe)
# ══════════════════════════════════════════════════════════════════════════════

_POD_HEALTH = {
    "JVM":       {"status": "Degraded",  "restarts": 3,  "cpu": "94%", "mem": "91%"},
    "Database":  {"status": "Unhealthy", "restarts": 0,  "cpu": "12%", "mem": "45%"},
    "Auth":      {"status": "Running",   "restarts": 1,  "cpu": "22%", "mem": "38%"},
    "TLS/API":   {"status": "Failed",    "restarts": 5,  "cpu": "0%",  "mem": "0%"},
    "Disk":      {"status": "Warning",   "restarts": 0,  "cpu": "8%",  "mem": "87% disk"},
    "Kafka":     {"status": "Degraded",  "restarts": 2,  "cpu": "78%", "mem": "62%"},
    "Inventory": {"status": "Unhealthy", "restarts": 4,  "cpu": "5%",  "mem": "30%"},
    "Security":  {"status": "Running",   "restarts": 0,  "cpu": "15%", "mem": "20%"},
    "OpenCV":    {"status": "Crashed",   "restarts": 7,  "cpu": "0%",  "mem": "0%"},
    "Weather API": {"status": "Running", "restarts": 0,  "cpu": "10%", "mem": "25%"},
    "Cert":      {"status": "Failed",    "restarts": 0,  "cpu": "0%",  "mem": "0%"},
}

def check_logs(service: str) -> dict:
    """
    TOOL 2 — check_logs
    Simulates a kubectl/Prometheus health probe for a given service.
    Returns current pod status, restart count, CPU and memory.
    """
    key = next((k for k in _POD_HEALTH if k.lower() in service.lower()), None)
    if key:
        info = _POD_HEALTH[key]
    else:
        info = {"status": "Unknown", "restarts": 0, "cpu": "N/A", "mem": "N/A"}
    return {"service": service, **info}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — restart_pod (simulated remediation action)
# ══════════════════════════════════════════════════════════════════════════════

def restart_pod(service: str) -> dict:
    """
    TOOL 3 — restart_pod
    Simulates a rolling restart of the affected pod/container.
    In production this would call: kubectl rollout restart deploy/<service>
    """
    time.sleep(0.3)   # simulate network round-trip
    return {
        "service":   service,
        "action":    "Rolling restart initiated",
        "command":   f"kubectl rollout restart deploy/{service.lower().replace(' ','-')}",
        "eta":       "~45 seconds",
        "status":    "RESTARTING",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ReAct Agent Loop
# ══════════════════════════════════════════════════════════════════════════════

def react_loop(alerts: list[dict]) -> list[dict]:
    """
    Reason → Act loop:
      For CRITICAL/HIGH alerts → check_logs() to probe service health.
      For Crashed/Failed pods  → restart_pod() to remediate.
    Enriches each alert dict with health info and any action taken.
    """
    print(f"\n  {BOLD}[ReAct Loop]{RESET} Processing {len(alerts)} alerts …")

    for a in alerts:
        sev = a.get("severity", "LOW")
        svc = a.get("service", "unknown")

        if sev in ("CRITICAL", "HIGH"):
            # Reason: high-severity → probe the service
            health = check_logs(svc)
            a["pod_status"]   = health["status"]
            a["pod_restarts"] = health["restarts"]
            a["pod_cpu"]      = health["cpu"]
            a["pod_mem"]      = health["mem"]

            print(f"  {SEV_COLORS[sev]}[{sev}]{RESET} {svc:<14} "
                  f"→ check_logs: status={health['status']} "
                  f"restarts={health['restarts']}")

            # Act: crashed or failed pod → restart it
            if health["status"] in ("Crashed", "Failed", "Unhealthy"):
                result = restart_pod(svc)
                a["action_taken"] = result["action"]
                a["kubectl_cmd"]  = result["command"]
                print(f"    {'':3}↳ {BOLD}restart_pod{RESET}: "
                      f"{result['command']}")
            else:
                a["action_taken"] = "Monitor — no restart needed"
                a["kubectl_cmd"]  = ""
        else:
            a["pod_status"]   = "N/A"
            a["pod_restarts"] = "N/A"
            a["action_taken"] = "Log only"
            a["kubectl_cmd"]  = ""

    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# Output — Formatted Table
# ══════════════════════════════════════════════════════════════════════════════

def print_table(alerts: list[dict]) -> None:
    col_w = [19, 36, 10, 42]
    sep   = "+" + "+".join("-" * (w + 2) for w in col_w) + "+"
    hdr   = ("| " + " | ".join(
        h.ljust(col_w[i])
        for i, h in enumerate(["TIMESTAMP", "ERROR", "SEVERITY", "SUGGESTED FIX"])
    ) + " |")

    print(f"\n{BOLD}  AIOps Alert Summary{RESET}")
    print(sep)
    print(BOLD + hdr + RESET)
    print(sep.replace("-", "="))

    for a in alerts:
        sev   = a.get("severity", "LOW")
        color = SEV_COLORS.get(sev, "")
        sev_cell = (color + sev + RESET).ljust(col_w[2] + len(color) + len(RESET))
        row = ("| " + " | ".join([
            a.get("timestamp", "")[:19].ljust(col_w[0]),
            a.get("error",     "")[:36].ljust(col_w[1]),
            sev_cell,
            a.get("suggested_fix", "")[:42].ljust(col_w[3]),
        ]) + " |")
        print(row)
        print(sep)

    # Summary counts
    counts = {}
    for a in alerts:
        counts[a.get("severity","LOW")] = counts.get(a.get("severity","LOW"),0) + 1
    print()
    for sev in ["CRITICAL","HIGH","MEDIUM","LOW"]:
        if sev in counts:
            print(f"  {SEV_COLORS[sev]}{BOLD}{sev:<10}{RESET} {counts[sev]} alert(s)")


# ══════════════════════════════════════════════════════════════════════════════
# Fallback sample data (used when API key is not set)
# ══════════════════════════════════════════════════════════════════════════════

def _sample_alerts():
    return [
      {"timestamp":"2024-05-21 08:05:33","error":"Java Heap OutOfMemoryError",
       "severity":"CRITICAL","suggested_fix":"Increase JVM heap; add -Xmx4g to flags.",
       "service":"JVM"},
      {"timestamp":"2024-05-21 08:07:14","error":"High JVM Memory Warning (91%)",
       "severity":"HIGH","suggested_fix":"Tune GC; fix DataProcessor memory leak.",
       "service":"JVM"},
      {"timestamp":"2024-05-21 08:09:55","error":"DB Connection Timeout 3 retries",
       "severity":"CRITICAL","suggested_fix":"Check db-prod-01; scale connection pool.",
       "service":"Database"},
      {"timestamp":"2024-05-21 08:13:45","error":"NullPointerException Auth Token",
       "severity":"HIGH","suggested_fix":"Add null guard in validateToken() method.",
       "service":"Auth"},
      {"timestamp":"2024-05-21 08:15:19","error":"TLS Handshake Failure Payments",
       "severity":"CRITICAL","suggested_fix":"Verify TLS version; check cert chain.",
       "service":"TLS/API"},
      {"timestamp":"2024-05-21 08:17:30","error":"Disk Usage 87% on /var/data",
       "severity":"MEDIUM","suggested_fix":"Archive old logs; alert at 80% threshold.",
       "service":"Disk"},
      {"timestamp":"2024-05-21 08:20:01","error":"Kafka Consumer Lag 142k Messages",
       "severity":"HIGH","suggested_fix":"Scale order-events consumers urgently.",
       "service":"Kafka"},
      {"timestamp":"2024-05-21 08:22:44","error":"Inventory Service HTTP 503",
       "severity":"HIGH","suggested_fix":"Enable circuit breaker; check pod health.",
       "service":"Inventory"},
      {"timestamp":"2024-05-21 08:26:38","error":"DB Permission Denied svc-etl",
       "severity":"MEDIUM","suggested_fix":"Grant SELECT on analytics to svc-etl.",
       "service":"Security"},
      {"timestamp":"2024-05-21 08:28:55","error":"Segfault in libopencv Native Lib",
       "severity":"CRITICAL","suggested_fix":"Update or recompile libopencv.so.",
       "service":"OpenCV"},
      {"timestamp":"2024-05-21 08:30:12","error":"Rate Limit Approaching Weather API",
       "severity":"LOW","suggested_fix":"Cache responses; request quota upgrade.",
       "service":"Weather API"},
      {"timestamp":"2024-05-21 08:32:47","error":"TLS Cert Expired internal.corp",
       "severity":"CRITICAL","suggested_fix":"Renew cert now; automate cert-manager.",
       "service":"Cert"},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AIOps Log Intelligence Analyzer")
    parser.add_argument("--log", default="app.log",          help="Input log file")
    parser.add_argument("--out", default="alert_summary.json", help="Output JSON file")
    args = parser.parse_args()

    print(f"\n{BOLD}{'═'*62}{RESET}")
    print(f"{BOLD}  AIOps Log Intelligence — ReAct Agent{RESET}")
    print(f"{DIM}  Model: {MODEL}{RESET}")
    print(f"{BOLD}{'═'*62}{RESET}")

    # Step 1: Parse
    print(f"\n📂  Parsing '{args.log}' …")
    entries = parse_log(args.log)
    print(f"    Found {len(entries)} ERROR/WARN entries.")

    # Step 2: TOOL 1 — classify
    t0 = time.time()
    alerts = classify_errors(entries)
    print(f"    Time: {time.time()-t0:.1f}s")

    # Step 3: ReAct — TOOL 2 + TOOL 3
    print(f"\n🔁  Running ReAct loop (check_logs + restart_pod) …")
    alerts = react_loop(alerts)

    # Step 4: Print table
    print_table(alerts)

    # Step 5: Save JSON
    with open(args.out, "w") as fh:
        json.dump(alerts, fh, indent=2)
    print(f"\n✅  Saved → {args.out}")
    print(f"{BOLD}{'═'*62}{RESET}\n")


if __name__ == "__main__":
    main()
