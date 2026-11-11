"""Compare upstream market breadth snapshot with the data used by the last report.

A scheduled poll only rebuilds if upstream content differs; manual/push rebuilds.
No personal access token or cross-repository write permission required.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

UPSTREAM = "https://raw.githubusercontent.com/angel92051400-code/my-market-breadth/main/index.html"
REPORT = Path("docs/summary.json")


def upstream_hash(url=UPSTREAM):
    req = Request(url, headers={"User-Agent": "market-breadth-backtest-sync/1.0", "Accept": "text/html"})
    with urlopen(req, timeout=60) as response:
        html = response.read()
    if b'id="market-data"' not in html or b"</script>" not in html:
        raise RuntimeError("上游市場寬度 HTML 缺少 market-data，停止自動回測")
    return hashlib.sha256(html).hexdigest()


def should_run(event, current_digest, previous_digest):
    return event != "schedule" or not previous_digest or current_digest != previous_digest


def main():
    event = os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    old = {}
    if REPORT.exists():
        old = json.loads(REPORT.read_text(encoding="utf-8"))
    previous = old.get("source", {}).get("source_sha256")
    # Only scheduled runs require a network check; manual/push rebuild directly.
    if event == "schedule":
        current = upstream_hash()
        changed = should_run(event, current, previous)
        print(f"上游快照 {current[:12]}；上次回測 {str(previous)[:12]}；重新回測={changed}")
    else:
        changed = True
        print(f"{event}: 依指定動作重新跑回測")
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
    return changed


if __name__ == "__main__":
    main()
