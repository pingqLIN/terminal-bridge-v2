#!/usr/bin/env python3
"""Run a real-browser smoke check for the TB2 GUI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke-test the TB2 GUI in Chromium. The script connects to an existing "
            "server when --base-url is reachable; otherwise it self-starts "
            "`python -m tb2 gui --no-browser` for the requested host/port. The JSON "
            "summary includes server_mode=pre-existing or self-started."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:3191")
    parser.add_argument("--out", default=".tb2-gui-smoke")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--self-start",
        action="store_true",
        help="Require this script to start the GUI server from the current checkout.",
    )
    parser.add_argument("--keep-server", action="store_true")
    return parser.parse_args()


def require_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing Playwright. Install with `.venv/bin/python -m pip install -e .[dev]` "
            "and then `.venv/bin/python -m playwright install chromium`."
        ) from exc
    return sync_playwright


def http_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.8) as response:
            return 200 <= int(response.status) < 500
    except (OSError, URLError):
        return False


def start_server(base_url: str) -> subprocess.Popen[str]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or (443 if parsed.scheme == "https" else 80))
    return subprocess.Popen(
        [sys.executable, "-m", "tb2", "gui", "--host", host, "--port", port, "--no-browser"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def wait_for_server(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if http_ready(url):
            return
        time.sleep(0.15)
    raise RuntimeError(f"GUI server did not become ready within {timeout:.1f}s: {url}")


def page_url(base_url: str, viewport: str, reduced: bool = False) -> str:
    suffix = "home=workspace&tab=topology&design=v3&lang=zh-TW"
    if reduced:
        suffix += "&reduced=1"
    return base_url.rstrip("/") + "/?" + suffix + "&viewport=" + viewport


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in (Path("tb2/gui.py"), Path("tools/gui_browser_smoke.py")):
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def collect_metrics(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const active = document.querySelector('.relation-link.is-active');
          const main = document.querySelector('main');
          const root = document.documentElement;
          const actions = document.getElementById('topology-actions');
          const diagram = document.getElementById('relation-diagram');
          const details = document.getElementById('relation-details');
          const tabs = document.getElementById('workspace-nav');
          const strip = document.getElementById('workspace-strip');
          const fleet = document.querySelector('.fleet-sidebar');
          const box = node => {
            if (!node) return null;
            const rect = node.getBoundingClientRect();
            return {
              top: Math.round(rect.top),
              bottom: Math.round(rect.bottom),
              left: Math.round(rect.left),
              right: Math.round(rect.right),
              width: Math.round(rect.width),
              height: Math.round(rect.height)
            };
          };
          const nodes = Array.from(document.querySelectorAll('.relation-node')).map(box).filter(Boolean);
          const overlaps = [];
          for (let i = 0; i < nodes.length; i += 1) {
            for (let j = i + 1; j < nodes.length; j += 1) {
              const a = nodes[i];
              const b = nodes[j];
              const overlap = a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
              if (overlap) overlaps.push([i, j]);
            }
          }
          return {
            actionCount: document.querySelectorAll('[data-topology-action]').length,
            hasTopologyActions: Boolean(actions),
            hasRelationDiagram: Boolean(diagram),
            mastheadMode: document.body.dataset.masthead || '',
            workspaceTab: document.body.dataset.workspaceTab || '',
            relationDetailsOpen: Boolean(details && details.open),
            interventionChecked: Boolean(document.getElementById('intervention')?.checked),
            activeLinkCount: document.querySelectorAll('.relation-link.is-active').length,
            activeAnimation: active ? getComputedStyle(active).animationName : '',
            documentHeight: root.scrollHeight,
            documentWidth: root.scrollWidth,
            viewportHeight: window.innerHeight,
            viewportWidth: window.innerWidth,
            heightRatio: root.scrollHeight / window.innerHeight,
            horizontalOverflow: root.scrollWidth > window.innerWidth + 2,
            mainOverflowY: main ? getComputedStyle(main).overflowY : '',
            mainScrollHeight: main ? main.scrollHeight : 0,
            mainClientHeight: main ? main.clientHeight : 0,
            topologyActionsWidth: actions ? Math.ceil(actions.getBoundingClientRect().width) : 0,
            topologyActionsBox: box(actions),
            relationDiagramBox: box(diagram),
            relationDetailsBox: box(details),
            workspaceTabsBox: box(tabs),
            relationNodeBoxes: nodes,
            relationNodeOverlapCount: overlaps.length,
            workspaceStripDisplay: strip ? getComputedStyle(strip).display : '',
            fleetDisplay: fleet ? getComputedStyle(fleet).display : ''
          };
        }"""
    )


def assert_metrics(metrics: dict[str, Any], *, reduced: bool) -> list[str]:
    failures: list[str] = []
    if metrics["actionCount"] != 6:
        failures.append(f"expected 6 topology actions, got {metrics['actionCount']}")
    if not metrics["hasTopologyActions"]:
        failures.append("missing #topology-actions")
    if not metrics["hasRelationDiagram"]:
        failures.append("missing #relation-diagram")
    if metrics["workspaceTab"] != "topology":
        failures.append(f"expected body[data-workspace-tab=topology], got {metrics['workspaceTab']!r}")
    if metrics["mastheadMode"] != "compact":
        failures.append(f"workspace masthead should default compact, got {metrics['mastheadMode']!r}")
    if not metrics["relationDetailsOpen"]:
        failures.append("topology relation details should be open by default")
    actions_box = metrics.get("topologyActionsBox") or {}
    diagram_box = metrics.get("relationDiagramBox") or {}
    if actions_box and actions_box["top"] > metrics["viewportHeight"]:
        failures.append(
            f"topology actions start below first viewport: top {actions_box['top']} > {metrics['viewportHeight']}"
        )
    if actions_box and actions_box["bottom"] > metrics["viewportHeight"] + 24:
        failures.append(
            f"topology actions do not fit near first viewport: bottom {actions_box['bottom']} > {metrics['viewportHeight'] + 24}"
        )
    if diagram_box and diagram_box["top"] > metrics["viewportHeight"] + 24:
        failures.append(
            f"relation diagram starts too low: top {diagram_box['top']} > {metrics['viewportHeight'] + 24}"
        )
    if metrics.get("relationNodeOverlapCount", 0) > 0:
        failures.append(f"relation diagram nodes overlap: {metrics['relationNodeOverlapCount']}")
    if metrics["horizontalOverflow"]:
        failures.append(
            f"horizontal overflow: document {metrics['documentWidth']} > viewport {metrics['viewportWidth']}"
        )
    if metrics["heightRatio"] > 2.5:
        failures.append(f"document height ratio exceeds 2.5 viewport: {metrics['heightRatio']:.3f}")
    if metrics["activeLinkCount"] < 1:
        failures.append("missing active topology line")
    if reduced and metrics["activeAnimation"] != "none":
        failures.append(f"reduced motion should disable active line animation, got {metrics['activeAnimation']!r}")
    if not reduced and metrics["activeAnimation"] != "relation-flow":
        failures.append(f"active line animation should be relation-flow, got {metrics['activeAnimation']!r}")
    return failures


def check_view(sync_playwright: Any, base_url: str, out: Path, name: str, viewport: dict[str, int]) -> dict[str, Any]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True)
        context = browser.new_context(viewport=viewport)
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.goto(page_url(base_url, name), wait_until="networkidle")
        metrics = collect_metrics(page)
        page.screenshot(path=str(out / f"{name}.png"), full_page=True)
        page.locator('[data-topology-action="review"]').click()
        page.wait_for_timeout(120)
        action_metrics = collect_metrics(page)
        page.screenshot(path=str(out / f"{name}-after-review-action.png"), full_page=True)
        reduced_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
        reduced_page = reduced_context.new_page()
        reduced_page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        reduced_page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        reduced_page.goto(page_url(base_url, name, reduced=True), wait_until="networkidle")
        reduced_metrics = collect_metrics(reduced_page)
        reduced_page.screenshot(path=str(out / f"{name}-reduced-motion.png"), full_page=True)
        browser.close()
    failures = assert_metrics(metrics, reduced=False) + assert_metrics(reduced_metrics, reduced=True)
    if not action_metrics["interventionChecked"]:
        failures.append("Review Gate click did not check #intervention")
    if console_errors:
        failures.extend("console error: " + item for item in console_errors)
    if page_errors:
        failures.extend("page error: " + item for item in page_errors)
    return {
        "name": name,
        "metrics": metrics,
        "after_review_action_metrics": action_metrics,
        "reduced_motion_metrics": reduced_metrics,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    sync_playwright = require_playwright()
    base_url = args.base_url.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen[str] | None = None
    try:
        if args.self_start and http_ready(base_url):
            raise SystemExit(f"--self-start requested, but {base_url} is already reachable")
        server_mode = "self-started" if args.self_start or not http_ready(base_url) else "pre-existing"
        if server_mode == "self-started":
            process = start_server(base_url)
            wait_for_server(base_url, args.timeout)
        cases = [
            check_view(sync_playwright, base_url, out, "desktop-topology-v3", {"width": 1440, "height": 900}),
            check_view(sync_playwright, base_url, out, "mobile-topology-v3", {"width": 390, "height": 844}),
        ]
        failures = [failure for case in cases for failure in case["failures"]]
        summary = {
            "ok": not failures,
            "base_url": base_url,
            "server_mode": server_mode,
            "ui_source_hash": source_hash(),
            "cwd": str(Path.cwd()),
            "screenshots": str(out),
            "cases": cases,
            "failures": failures,
        }
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if not failures else 1
    finally:
        if process and not args.keep_server:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
