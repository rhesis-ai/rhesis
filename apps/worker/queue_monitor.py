#!/usr/bin/env python3
"""
Live Celery queue monitor for stress-testing the Rhesis worker.

Flower cannot report time-in-queue here because the publisher (the FastAPI
process) does not emit the `task-sent` event (``task_send_sent_event=False``
in ``celery/config.py``). This tool fills that gap **without any worker code
changes** by combining two external signals:

  1. Broker introspection (Redis): each Celery queue is a Redis list, so the
     instantaneous backlog is simply ``LLEN <queue>``. Sampled over time this
     shows the queue building up and draining.

  2. Worker events: ``rh dev worker`` starts Celery with ``-E``, so the worker
     emits ``task-received`` / ``task-started`` / ``task-succeeded`` /
     ``task-failed``. From these we measure real throughput, task runtime, and
     the directly-observable in-worker wait (received -> started).

From backlog + throughput we estimate the **average queue wait** via Little's
Law:  W = L / λ  (mean time waiting in queue = backlog / completion rate).
This is the "average waiting time in the queue" number Flower won't give you.

It renders two live tables — PER QUEUE and PER TASK — each with an `ALL` row
(the general/overall aggregate). Per-task throughput, runtime, and in-worker
wait come from events; per-task backlog and est.wait need `--peek` (which
samples queue messages to estimate the task mix).

Usage (run from apps/backend so the backend venv resolves):
    cd apps/backend
    uv run python ../worker/queue_monitor.py                    # both tables
    uv run python ../worker/queue_monitor.py --peek 500         # + per-task backlog/wait
    uv run python ../worker/queue_monitor.py --queues telemetry # one queue
    uv run python ../worker/queue_monitor.py --interval 1 --window 20
    uv run python ../worker/queue_monitor.py --csv run1.csv     # append samples to CSV
    uv run python ../worker/queue_monitor.py --no-events        # backlog only (no -E worker)
    uv run python ../worker/queue_monitor.py --once             # print one sample and exit

Requirements:
    BROKER_URL in ../backend/.env (or pass --broker / set BROKER_URL).
    The worker must run with `-E` for throughput/wait metrics (default in dev).
"""

import argparse
import json
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv

    _backend_env = Path(__file__).parent.parent / "backend" / ".env"
    if _backend_env.exists():
        load_dotenv(_backend_env)
except Exception:
    pass

import redis
from celery import Celery

# Task-name prefix -> queue. Mirrors task_routes in celery/config.py so that
# event-derived metrics can be attributed to the right queue.
ROUTE_PREFIXES = (
    ("rhesis.backend.tasks.execution.", "execution"),
    ("rhesis.backend.tasks.telemetry.", "telemetry"),
    ("rhesis.backend.tasks.architect.", "architect"),
)
DEFAULT_QUEUES = ["celery", "execution", "telemetry", "architect"]


def route_queue(task_name):
    if not task_name:
        return "celery"
    for prefix, queue in ROUTE_PREFIXES:
        if task_name.startswith(prefix):
            return queue
    return "celery"


def short_name(task_name):
    """Trim the common module prefix for compact display."""
    if not task_name:
        return "?"
    return task_name.replace("rhesis.backend.tasks.", "")


def pct(values, p):
    """Percentile (linear interpolation), pure-python."""
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fmt_ms(seconds):
    if seconds is None:
        return "  -  "
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def fmt_rate(r):
    return f"{r:.1f}/s" if r is not None else "  -  "


class EventCollector:
    """Subscribes to worker events and keeps rolling samples.

    Every sample is tagged with both the queue and the task name, so the same
    raw data can be grouped either way (per-queue or per-task) at render time.
    """

    def __init__(self, broker_url, window):
        self.window = window
        self.app = Celery(broker=broker_url)
        self.state = self.app.events.State()
        self.lock = threading.Lock()
        # each deque holds (timestamp, queue, name, value)
        self.arrivals = deque()       # task-received      (value=None)
        self.completions = deque()    # succeeded/failed   (value="ok"/"fail")
        self.runtimes = deque()       # task runtime seconds
        self.inworker = deque()       # started - received seconds
        self.events_seen = 0
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _handle(self, event):
        self.state.event(event)
        etype = event.get("type", "")
        if not etype.startswith("task-"):
            return
        uuid = event.get("uuid")
        ts = event.get("timestamp") or time.time()
        task = self.state.tasks.get(uuid) if uuid else None
        name = getattr(task, "name", None) or "?"
        queue = route_queue(name)
        with self.lock:
            self.events_seen += 1
            if etype == "task-received":
                self.arrivals.append((ts, queue, name, None))
            elif etype == "task-started":
                recv = getattr(task, "received", None)
                started = getattr(task, "started", None)
                if recv and started and started >= recv:
                    self.inworker.append((ts, queue, name, started - recv))
            elif etype == "task-succeeded":
                self.completions.append((ts, queue, name, "ok"))
                rt = getattr(task, "runtime", None)
                if rt is not None:
                    self.runtimes.append((ts, queue, name, rt))
            elif etype == "task-failed":
                self.completions.append((ts, queue, name, "fail"))

    def _run(self):
        handlers = {"*": self._handle}
        while not self._stop.is_set():
            try:
                with self.app.connection() as conn:
                    recv = self.app.events.Receiver(conn, handlers=handlers)
                    for _ in recv.itercapture(limit=None, timeout=2.0, wakeup=True):
                        if self._stop.is_set():
                            return
            except Exception:
                # Receiver returns control on timeout via socket.timeout raised
                # out of drain_events; loop again unless asked to stop.
                if self._stop.is_set():
                    return
                time.sleep(0.5)

    def _prune(self, now):
        cutoff = now - self.window
        for dq in (self.arrivals, self.completions, self.runtimes, self.inworker):
            while dq and dq[0][0] < cutoff:
                dq.popleft()

    def snapshot_raw(self, now):
        """Return pruned copies of the rolling sample buffers."""
        with self.lock:
            self._prune(now)
            return {
                "arrivals": list(self.arrivals),
                "completions": list(self.completions),
                "runtimes": list(self.runtimes),
                "inworker": list(self.inworker),
                "events_seen": self.events_seen,
            }


def compute_metrics(raw, window, key_index, keys=None):
    """Group raw samples by tuple element `key_index` (1=queue, 2=name).

    Returns {key: {arrival_rate, completion_rate, fail_rate, runtime_p50,
    runtime_p95, inworker_p95, done, failed}}. If `keys` is given only those
    groups are returned (in that order); otherwise every observed key is used.
    """
    span = max(window, 1e-6)
    if keys is None:
        keys = sorted(
            {s[key_index] for s in raw["arrivals"]}
            | {s[key_index] for s in raw["completions"]}
        )
    out = {}
    for k in keys:
        arr = sum(1 for s in raw["arrivals"] if s[key_index] == k)
        ok = sum(1 for s in raw["completions"] if s[key_index] == k and s[3] == "ok")
        fail = sum(1 for s in raw["completions"] if s[key_index] == k and s[3] == "fail")
        rts = [s[3] for s in raw["runtimes"] if s[key_index] == k]
        iws = [s[3] for s in raw["inworker"] if s[key_index] == k]
        out[k] = {
            "arrival_rate": arr / span,
            "completion_rate": (ok + fail) / span,
            "fail_rate": fail / span,
            "runtime_p50": pct(rts, 50),
            "runtime_p95": pct(rts, 95),
            "inworker_p95": pct(iws, 95),
            "done": ok,
            "failed": fail,
        }
    return out


def compute_overall(raw, window):
    """Aggregate metrics across all tasks/queues (the 'general' row)."""
    span = max(window, 1e-6)
    ok = sum(1 for s in raw["completions"] if s[3] == "ok")
    fail = sum(1 for s in raw["completions"] if s[3] == "fail")
    rts = [s[3] for s in raw["runtimes"]]
    iws = [s[3] for s in raw["inworker"]]
    return {
        "arrival_rate": len(raw["arrivals"]) / span,
        "completion_rate": (ok + fail) / span,
        "fail_rate": fail / span,
        "runtime_p50": pct(rts, 50),
        "runtime_p95": pct(rts, 95),
        "inworker_p95": pct(iws, 95),
        "done": ok,
        "failed": fail,
    }


def get_broker_url(args):
    if args.broker:
        return args.broker
    url = os.environ.get("BROKER_URL")
    if url:
        return url
    return "redis://localhost:6379/0"


def llen_safe(r, queue):
    try:
        return r.llen(queue)
    except Exception:
        return None


def peek_backlog_by_task(r, queues, sample):
    """Estimate per-task backlog by sampling messages from each Redis queue.

    Celery's Redis broker stores each message as a JSON envelope whose
    ``headers.task`` holds the task name (no body decode needed). We read up to
    `sample` items from the head of each list and scale the observed task mix to
    the full LLEN. Returns {task_name: estimated_backlog}.
    """
    est = {}
    if sample <= 0:
        return est
    for q in queues:
        try:
            total = r.llen(q)
            if not total:
                continue
            items = r.lrange(q, 0, sample - 1)
            counts = {}
            for it in items:
                try:
                    name = json.loads(it).get("headers", {}).get("task") or "?"
                except Exception:
                    name = "?"
                counts[name] = counts.get(name, 0) + 1
            scale = total / len(items) if items else 1.0
            for name, c in counts.items():
                est[name] = est.get(name, 0.0) + c * scale
        except Exception:
            continue
    return est


CLEAR = "\033[2J\033[H"

LABEL_W = 46


def _est_wait(backlog, comp):
    """Little's Law avg queue wait = backlog / completion rate."""
    if backlog is not None and comp and comp > 0:
        return backlog / comp
    return None


def _row(label, backlog, m, label_w):
    backlog_s = "  -  " if backlog is None else (
        str(int(round(backlog))) if isinstance(backlog, float) else str(backlog)
    )
    comp = m.get("completion_rate")
    est_wait = _est_wait(backlog, comp)
    return (
        f"  {label[:label_w]:<{label_w}}{backlog_s:>9}"
        f"{fmt_rate(m.get('arrival_rate')):>8}{fmt_rate(comp):>8}"
        f"{fmt_rate(m.get('fail_rate')):>8}{fmt_ms(est_wait):>10}"
        f"{fmt_ms(m.get('runtime_p50')):>9}{fmt_ms(m.get('runtime_p95')):>9}"
        f"{fmt_ms(m.get('inworker_p95')):>9}"
    )


def _table_header(label, label_w):
    header = (
        f"  {label:<{label_w}}{'backlog':>9}{'in/s':>8}{'done/s':>8}{'fail/s':>8}"
        f"{'est.wait':>10}{'run p50':>9}{'run p95':>9}{'wkrwait':>9}"
    )
    return [header, "  " + "-" * (len(header) - 2)]


def render(broker_url, queues, backlogs, qmetrics, tmetrics, tbacklog, overall,
           events_seen, events_enabled, now, interval, window, peek_on):
    lines = []
    lines.append(
        f"  Rhesis Celery queue monitor   "
        f"{datetime.now().strftime('%H:%M:%S')}   "
        f"(interval {interval}s, window {window}s)"
    )
    lines.append(f"  broker: {broker_url}")
    if not events_enabled:
        lines.append("  events: DISABLED (--no-events)  -> backlog only")
    elif events_seen == 0:
        lines.append(
            "  events: no task events received yet "
            "(is the worker running with -E? is there traffic?)"
        )
    else:
        lines.append(f"  events: ok ({events_seen} seen)")
    lines.append("")

    # Per-queue table
    lines.append("  PER QUEUE")
    lines.extend(_table_header("queue", 11))
    for q in queues:
        lines.append(_row(q, backlogs.get(q), qmetrics.get(q, {}), 11))
    total_backlog = sum(b for b in backlogs.values() if b is not None)
    lines.append(_row("ALL", total_backlog, overall, 11))
    lines.append("")

    # Per-task table
    lines.append("  PER TASK" + ("" if peek_on else "   (backlog/est.wait need --peek)"))
    lines.extend(_table_header("task", LABEL_W))
    task_names = sorted(
        tmetrics.keys(),
        key=lambda n: tmetrics[n].get("completion_rate", 0) + tmetrics[n].get("arrival_rate", 0),
        reverse=True,
    )
    for name in task_names:
        backlog = tbacklog.get(name) if peek_on else None
        lines.append(_row(short_name(name), backlog, tmetrics[name], LABEL_W))
    lines.append(_row("ALL", total_backlog, overall, LABEL_W))
    lines.append("")
    lines.append(
        "  est.wait = backlog / done-rate (Little's Law avg queue wait).  "
        "wkrwait = received->started p95."
    )
    return "\n".join(lines)


def _csv(v):
    return "" if v is None else round(v, 4)


def _metric_row(iso, scope, key, backlog, m):
    comp = m.get("completion_rate")
    est_wait = _est_wait(backlog, comp)
    return [
        iso,
        scope,
        key,
        "" if backlog is None else round(backlog, 2),
        _csv(m.get("arrival_rate")),
        _csv(comp),
        _csv(m.get("fail_rate")),
        _csv(est_wait),
        _csv(m.get("runtime_p50")),
        _csv(m.get("runtime_p95")),
        _csv(m.get("inworker_p95")),
    ]


def csv_rows(queues, backlogs, qmetrics, tmetrics, tbacklog, overall, peek_on, now):
    iso = datetime.fromtimestamp(now, timezone.utc).isoformat()
    rows = []
    for q in queues:
        rows.append(_metric_row(iso, "queue", q, backlogs.get(q), qmetrics.get(q, {})))
    for name, m in tmetrics.items():
        backlog = tbacklog.get(name) if peek_on else None
        rows.append(_metric_row(iso, "task", short_name(name), backlog, m))
    total_backlog = sum(b for b in backlogs.values() if b is not None)
    rows.append(_metric_row(iso, "overall", "ALL", total_backlog, overall))
    return rows


CSV_HEADER = [
    "timestamp",
    "scope",
    "key",
    "backlog",
    "arrival_rate",
    "completion_rate",
    "fail_rate",
    "est_wait_s",
    "runtime_p50_s",
    "runtime_p95_s",
    "inworker_wait_p95_s",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker", help="Broker URL (default: BROKER_URL env or .env)")
    parser.add_argument(
        "--queues",
        default=",".join(DEFAULT_QUEUES),
        help="Comma-separated queue names to watch",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Refresh seconds")
    parser.add_argument(
        "--window",
        type=float,
        default=30.0,
        help="Rolling window (s) for rates/percentiles",
    )
    parser.add_argument("--csv", help="Append samples to this CSV file")
    parser.add_argument(
        "--no-events",
        action="store_true",
        help="Skip event subscription (backlog only)",
    )
    parser.add_argument(
        "--peek",
        type=int,
        default=0,
        metavar="N",
        help="Sample up to N head messages per queue to estimate per-task "
        "backlog and est.wait (0=off). Try 500.",
    )
    parser.add_argument("--once", action="store_true", help="Print one sample and exit")
    args = parser.parse_args()

    queues = [q.strip() for q in args.queues.split(",") if q.strip()]
    broker_url = get_broker_url(args)

    try:
        r = redis.from_url(broker_url, socket_connect_timeout=5, socket_timeout=5)
        r.ping()
    except Exception as e:
        print(f"Could not connect to broker {broker_url}: {e}", file=sys.stderr)
        sys.exit(1)

    collector = None
    if not args.no_events:
        collector = EventCollector(broker_url, args.window)
        collector.start()

    csv_file = None
    csv_writer = None
    if args.csv:
        import csv as _csvmod

        new_file = not Path(args.csv).exists()
        csv_file = open(args.csv, "a", newline="")
        csv_writer = _csvmod.writer(csv_file)
        if new_file:
            csv_writer.writerow(CSV_HEADER)

    peek_on = args.peek > 0
    try:
        while True:
            now = time.time()
            backlogs = {q: llen_safe(r, q) for q in queues}
            tbacklog = peek_backlog_by_task(r, queues, args.peek) if peek_on else {}
            if collector:
                raw = collector.snapshot_raw(now)
                qmetrics = compute_metrics(raw, args.window, 1, keys=queues)
                tmetrics = compute_metrics(raw, args.window, 2)
                overall = compute_overall(raw, args.window)
                events_seen = raw["events_seen"]
            else:
                qmetrics, tmetrics, overall, events_seen = {}, {}, {}, 0
            if not args.once:
                sys.stdout.write(CLEAR)
            print(
                render(
                    broker_url,
                    queues,
                    backlogs,
                    qmetrics,
                    tmetrics,
                    tbacklog,
                    overall,
                    events_seen,
                    not args.no_events,
                    now,
                    args.interval,
                    args.window,
                    peek_on,
                )
            )
            if csv_writer and csv_file:
                for row in csv_rows(
                    queues, backlogs, qmetrics, tmetrics, tbacklog, overall, peek_on, now
                ):
                    csv_writer.writerow(row)
                csv_file.flush()
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if collector:
            collector.stop()
        if csv_file:
            csv_file.close()


if __name__ == "__main__":
    main()
