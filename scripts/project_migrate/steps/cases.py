"""Tests and their prompts, created one at a time.

The bulk routes don't fit: /test_sets/bulk drops test_parameters, /tests/bulk drops
test_metadata and returns no ids, and both would duplicate a test that sits in several sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from project_migrate.api import HttpError, odata_str
from project_migrate.compare import changed_fields, subset_equal, test_fingerprint
from project_migrate.engine import Migration

PROGRESS_EVERY = 25


@dataclass
class TargetTests:
    """The target project's tests, indexed every way a source test can be matched."""

    by_id: dict[str, dict] = field(default_factory=dict)
    by_prompt: dict[str, dict] = field(default_factory=dict)
    by_fingerprint: dict[str, list[dict]] = field(default_factory=dict)
    claimed: set[str] = field(default_factory=set)
    used_prompts: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, m: Migration) -> TargetTests:
        idx = cls()
        for t in m.dst.get_all("/tests/", **m.dst.project_filter()):
            idx.by_id[t["id"]] = t
            if t.get("prompt_id"):
                idx.by_prompt[t["prompt_id"]] = t
                idx.used_prompts.add(t["prompt_id"])
            idx.by_fingerprint.setdefault(test_fingerprint(t, t.get("prompt")), []).append(t)
        idx.claimed = {
            e["target_id"] for e in m.state.entries("test:").values() if e.get("target_id")
        }
        return idx

    def match(self, src: dict, entry: dict) -> dict | None:
        target = self.by_id.get(entry.get("target_id", ""))
        if not target and entry.get("prompt_id"):
            target = self.by_prompt.get(entry["prompt_id"])
        if not target:
            # Identical source tests pair one-to-one with identical target tests.
            fp = test_fingerprint(src, src.get("_prompt"))
            free = [x for x in self.by_fingerprint.get(fp, []) if x["id"] not in self.claimed]
            target = free[0] if free else None
        if target:
            self.claimed.add(target["id"])
        return target


def prompt_payload(src: dict) -> dict | None:
    p = src.get("_prompt")
    if not p:
        return None
    payload = {
        "content": p["content"],
        "language_code": p.get("language_code") or "en",
        "expected_response": p.get("expected_response"),
    }
    return {k: v for k, v in payload.items() if v is not None}


def test_payload(m: Migration, src: dict) -> dict:
    test_type = src.get("test_type") or {}
    payload = {
        "topic_id": m.mapped("topic", src.get("topic_id")),
        "category_id": m.mapped("category", src.get("category_id")),
        "requirement_id": m.mapped("requirement", src.get("requirement_id")),
        "test_type_id": (
            m.type_lookup(test_type["type_name"], test_type["type_value"]) if test_type else None
        ),
        "priority": src.get("priority"),
        "test_configuration": src.get("test_configuration"),
        "test_metadata": src.get("test_metadata"),
        "test_parameters": src.get("test_parameters"),
    }
    return {k: v for k, v in payload.items() if v is not None}


def tests(m: Migration) -> None:
    src_tests = m.snap["tests"] if m.limit is None else m.snap["tests"][: m.limit]
    targets = TargetTests.load(m)
    for i, src in enumerate(src_tests, 1):
        key = f"test:{src['id']}"
        entry = m.state.get(key) or {}
        payload = test_payload(m, src)
        target = targets.match(src, entry)
        if target:
            _update(m, src, target, payload)
            m.state.put(
                key, status="done", target_id=target["id"], prompt_id=target.get("prompt_id")
            )
            m.remember("test", src["id"], target["id"])
        else:
            new_id = _create(m, src, entry, payload, targets)
            targets.claimed.add(new_id)
            m.remember("test", src["id"], new_id)
        if i % PROGRESS_EVERY == 0:
            m.log(f"  tests: {i}/{len(src_tests)}")


def _update(m: Migration, src: dict, target: dict, payload: dict) -> None:
    diff = changed_fields(payload, target)
    want_prompt = prompt_payload(src) or {}
    # The prompt nested in a test has no language_code, so only the text is compared.
    pdiff = changed_fields(
        {k: v for k, v in want_prompt.items() if k != "language_code"}, target.get("prompt") or {}
    )
    if not diff and not pdiff:
        m.report.add("test", "unchanged")
        return
    m.report.add("test", "update")
    m.log(f"  update test {src['id']}: {diff + ['prompt.' + k for k in pdiff]}")
    if pdiff:
        m.put(f"/prompts/{target['prompt_id']}", {k: want_prompt[k] for k in pdiff})
    if diff:
        m.put(f"/tests/{target['id']}", {k: payload[k] for k in diff})


def _create(m: Migration, src: dict, entry: dict, payload: dict, targets: TargetTests) -> str:
    """Prompt first, then the test. The prompt id is saved in between, so a crash after the
    prompt reuses it on the next run instead of leaving an orphan."""
    key = f"test:{src['id']}"
    m.report.add("test", "create")
    prompt_id = entry.get("prompt_id")
    if prompt_id and not _prompt_exists(m, prompt_id):
        # Deleted on the target since state saved it; make a new one.
        prompt_id = None
    want_prompt = prompt_payload(src)
    if want_prompt and not prompt_id and entry.get("status") == "pending" and not m.dry:
        # The last run died after posting the prompt but before saving its id.
        found = _recent_unused_prompt(m, want_prompt, targets)
        prompt_id = found["id"] if found else None
    if want_prompt and not prompt_id:
        m.state.put(key, status="pending")
        prompt_id = m.create(
            "prompt",
            "/prompts/",
            {**want_prompt, "project_id": m.dst.project_id},
            lambda: _recent_unused_prompt(m, want_prompt, targets),
        )
    if prompt_id:
        m.state.put(key, status="pending", prompt_id=prompt_id)
        targets.used_prompts.add(prompt_id)
        payload = {**payload, "prompt_id": prompt_id}

    def reconcile() -> dict | None:
        if prompt_id:
            rows = m.dst.get("/tests/", **{"$filter": f"prompt_id eq {odata_str(prompt_id)}"})
            return rows[0] if rows else None
        # A test without a prompt (multi-turn) is found by its fingerprint instead.
        return _recent_unclaimed_test(m, src, targets)

    new_id = m.create("test", "/tests/", {**payload, "project_id": m.dst.project_id}, reconcile)
    m.state.put(key, status="done", target_id=new_id, prompt_id=prompt_id)
    return new_id


def _prompt_exists(m: Migration, prompt_id: str) -> bool:
    try:
        m.dst.get(f"/prompts/{prompt_id}")
    except HttpError as e:
        if e.status in (404, 410):
            return False
        raise
    return True


def _recent_unclaimed_test(m: Migration, src: dict, targets: TargetTests) -> dict | None:
    want = test_fingerprint(src, src.get("_prompt"))
    recent = m.dst.get(
        "/tests/", limit=20, sort_by="created_at", sort_order="desc", **m.dst.project_filter()
    )
    for t in recent:
        if t["id"] not in targets.claimed and test_fingerprint(t, t.get("prompt")) == want:
            return t
    return None


def _recent_unused_prompt(m: Migration, want: dict, targets: TargetTests) -> dict | None:
    recent = m.dst.get(
        "/prompts/", limit=20, sort_by="created_at", sort_order="desc", **m.dst.project_filter()
    )
    for p in recent:
        if p["id"] not in targets.used_prompts and subset_equal(want, p):
            return p
    return None
