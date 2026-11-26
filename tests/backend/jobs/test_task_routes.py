"""Every job is routed to a named queue, and the stock worker consumes every queue.

A job with no route lands on Celery's default queue, behind whatever else is there.
Add a new job to the queue in celery/queues.py QUEUES whose rule it fits.
"""

import pathlib
import re

import yaml

from rhesis.backend.celery.queues import QUEUES, TASK_ROUTES
from rhesis.backend.worker import app

ROOT = pathlib.Path(__file__).parents[3]
START_SH = ROOT / "apps" / "worker" / "start.sh"
DEV_WORKER = ROOT / "scripts" / "rh" / "services.sh"


def _core_jobs() -> set[str]:
    app.loader.import_default_modules()
    return {name for name in app.tasks if name.startswith("rhesis.backend.jobs.")}


def test_every_job_has_a_queue():
    unrouted = sorted(_core_jobs() - set(TASK_ROUTES))
    assert not unrouted, f"Add these to a queue in celery/queues.py QUEUES: {unrouted}"


def test_every_route_names_a_real_job():
    stale = sorted(set(TASK_ROUTES) - _core_jobs())
    assert not stale, f"Routed but not registered (renamed or removed?): {stale}"


def _start_sh_layouts() -> dict[str, set[str]]:
    """The queues each WORKER_LAYOUT in apps/worker/start.sh consumes."""
    script = START_SH.read_text()
    split, combined = script.split("else\n    # Every queue", 1)
    combined = "MAIN_QUEUES=" + combined.split("MAIN_QUEUES=", 1)[1]
    main_queues = re.search(r'MAIN_QUEUES="([^"]+)"', combined).group(1).split(",")

    def queues_in(block: str) -> set[str]:
        found = set()
        for spec in re.findall(r'^\s+"([^"]+)"$', block, re.M):
            spec = spec.replace("$MAIN_QUEUES", ",".join(main_queues))
            found |= set(spec.split("|")[1].split(","))
        return found

    return {"split": queues_in(split), "combined": queues_in(combined)}


def test_every_worker_layout_consumes_every_queue():
    for layout, queues in _start_sh_layouts().items():
        missing = set(QUEUES) - queues
        assert not missing, f"WORKER_LAYOUT={layout} in start.sh consumes none of {missing}"


def test_the_dev_worker_consumes_every_queue():
    # ./rh dev worker runs one process for everything.
    script = DEV_WORKER.read_text()
    queues = set(re.search(r"--queues=(\S+) ", script).group(1).split(","))

    assert set(QUEUES) <= queues


def test_the_chart_scales_on_real_queues():
    # hpa.keda.queues in the Helm values name Redis lists; a typo would never trigger.
    charts = ROOT / "charts" / "rhesis"
    for values in sorted(charts.glob("values*.yaml")):
        for worker in yaml.safe_load(values.read_text()).get("workers") or []:
            queues = set(((worker.get("hpa") or {}).get("keda") or {}).get("queues") or {})
            unknown = queues - set(QUEUES)
            assert not unknown, f"{values.name}: hpa.keda.queues names unknown queues {unknown}"
