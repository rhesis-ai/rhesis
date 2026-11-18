"""Experiments with their version history, and the environments that point at them.

Versions are immutable and numbered by the server (v1, v2, ...) on each new save, so they are
replayed in order on the target, which gives them the same names. That keeps every
environment's `(experiment, version)` pointer valid after the copy.
"""

from __future__ import annotations

from project_migrate.api import Abort, AmbiguousWrite, HttpError
from project_migrate.compare import changed_fields
from project_migrate.engine import UNCLEAR_RETRIES, UNCLEAR_WAIT_SECONDS, Migration, index_by_name

KIND_EXPERIMENT = "experiment"
KIND_VERSION = "experiment version"
KIND_ENVIRONMENT = "environment"
# Always available without registering; the API refuses to register them.
BUILT_IN_ENVIRONMENTS = frozenset({"default", "development", "staging", "production"})
EXPERIMENT_FIELDS = ("name", "description", "visibility")


def experiments(m: Migration) -> None:
    if not m.snap.get("experiments"):
        return
    path = f"/projects/{m.dst.project_id}/experiments"
    try:
        # Other users' private experiments are dropped after paging, so pages can be short.
        rows = m.dst.get_all(path, until_empty=True)
    except HttpError as e:
        if e.status != 404:
            raise
        m.experiments_skipped = True
        m.report.notes.append("the target has no experiments API; experiments were skipped")
        return
    by_id = {r["id"]: r for r in rows}
    by_name = index_by_name(rows)
    for src in m.snap["experiments"]:
        target_id = _upsert_experiment(m, src, by_id, by_name, path)
        _replay_versions(m, src, target_id)


def _find_experiment(
    m: Migration, src: dict, by_id: dict[str, dict], by_name: dict[str, list[dict]]
) -> dict | None:
    """The state's target id first, so a rename on the source renames the copy."""
    entry = m.state.get(f"experiment:{src['id']}") or {}
    if entry.get("target_id") in by_id:
        return by_id[entry["target_id"]]
    matches = by_name.get(src["name"], [])
    if len(matches) > 1:
        raise Abort(f"target has {len(matches)} experiments named '{src['name']}'; resolve by hand")
    return matches[0] if matches else None


def _upsert_experiment(
    m: Migration, src: dict, by_id: dict[str, dict], by_name: dict[str, list[dict]], path: str
) -> str:
    payload = {k: src.get(k) for k in EXPERIMENT_FIELDS if src.get(k) is not None}
    key = f"experiment:{src['id']}"
    target = _find_experiment(m, src, by_id, by_name)
    if target:
        diff = changed_fields(payload, target)
        # A refused update still leaves a copy, so its versions and environments are synced.
        if not diff:
            m.report.add(KIND_EXPERIMENT, "unchanged")
        elif _patch_experiment(m, src, target, {k: payload[k] for k in diff}):
            m.report.add(KIND_EXPERIMENT, "update")
        m.state.put(key, status="done", target_id=target["id"], name=src["name"])
        m.remember("experiment", src["id"], target["id"])
        return target["id"]

    m.report.add(KIND_EXPERIMENT, "create")
    m.log(f"  create experiment '{src['name']}'")
    m.state.put(key, status="pending", name=src["name"])

    def reconcile() -> dict | None:
        found = [r for r in m.dst.get_all(path, until_empty=True) if r["name"] == src["name"]]
        return found[0] if found else None

    new_id = m.create(KIND_EXPERIMENT, path, payload, reconcile)
    m.state.put(key, status="done", target_id=new_id, name=src["name"])
    m.remember("experiment", src["id"], new_id)
    return new_id


def _patch_experiment(m: Migration, src: dict, target: dict, body: dict) -> bool:
    """False when the target refuses: 403 when another user owns the copy, 409 when making it
    private while an environment still points at it."""
    m.log(f"  update experiment '{src['name']}': {sorted(body)}")
    try:
        m.send("PATCH", f"/experiments/{target['id']}", body)
    except HttpError as e:
        if e.status not in (403, 409):
            raise
        m.report.add(KIND_EXPERIMENT, "refused")
        m.report.notes.append(
            f"experiment '{src['name']}' could not be updated on the target (HTTP {e.status}); "
            "resolve it by hand"
        )
        return False
    return True


def _replay_versions(m: Migration, src: dict, target_id: str) -> None:
    """Append the source versions the target lacks, in order. A target whose history already
    differs from the source is left alone, so its version names never shift."""
    src_versions = src.get("versions") or []
    have = [] if m.is_placeholder(target_id) else _target_versions(m, target_id)
    for i, version in enumerate(src_versions):
        if i < len(have):
            if changed_fields(version.get("values") or {}, have[i].get("values") or {}):
                _stop(m, src, f"its {have[i]['version']} differs from the source")
                return
            m.report.add(KIND_VERSION, "unchanged")
            m.remember("experiment version", f"{src['id']}:{version['version']}", "ok")
            continue
        m.report.add(KIND_VERSION, "create")
        if m.dry:
            m.remember("experiment version", f"{src['id']}:{version['version']}", "ok")
            continue
        try:
            made = _post_version(m, target_id, version, expected_count=i + 1)
        except HttpError as e:
            if e.status not in (403, 422):
                raise
            # 422: the target's schema rejects these values (a changed type or option).
            # 403: another user owns the target copy.
            _stop(m, src, f"the target rejected {version['version']} (HTTP {e.status}): {e.body}")
            return
        if made["version"] != version["version"]:
            _stop(m, src, f"the target numbered {version['version']} as {made['version']}")
            return
        if changed_fields(version.get("values") or {}, made.get("values") or {}):
            # The target's schema lacks fields the version uses, so it saved other values.
            _stop(m, src, f"the target saved {version['version']} with different values")
            return
        m.remember("experiment version", f"{src['id']}:{version['version']}", "ok")


def _target_versions(m: Migration, target_id: str) -> list[dict]:
    return m.dst.get(f"/experiments/{target_id}").get("versions") or []


def _post_version(m: Migration, target_id: str, version: dict, expected_count: int) -> dict:
    """Saving the latest version's values again is a no-op on the server, so after an unclear
    outcome the history is re-read before posting again."""
    body = {
        "values": version.get("values") or {},
        "message": version.get("message"),
        "parent_version": version.get("parent_version"),
    }
    for _ in range(UNCLEAR_RETRIES):
        try:
            return m.dst.request("POST", f"/experiments/{target_id}/versions", body=body)
        except AmbiguousWrite:
            m.dst.clock.sleep(UNCLEAR_WAIT_SECONDS)
            have = _target_versions(m, target_id)
            if len(have) >= expected_count:
                m.report.add(KIND_VERSION, "adopt")
                return have[expected_count - 1]
    raise Abort(f"could not save version {version['version']} of experiment {target_id}")


def _stop(m: Migration, src: dict, why: str) -> None:
    m.report.add(KIND_VERSION, "diverged")
    m.report.notes.append(
        f"experiment '{src['name']}' was not replayed further: {why}. Fix it by hand on the target"
    )


def environments(m: Migration) -> None:
    want = (m.snap.get("environments") or {}).get("environments")
    if want is None or m.experiments_skipped:
        return
    path = f"/projects/{m.dst.project_id}/parameters/environments"
    try:
        have = m.dst.get(path).get("environments") or {}
    except HttpError as e:
        if e.status != 404:
            raise
        m.report.notes.append("the target has no environments API; environments were skipped")
        return
    for name, pointer in sorted(want.items()):
        if pointer is None:
            _register(m, path, name, have)
        else:
            _bind(m, path, name, pointer, have)
    if m.prune:
        for name in sorted(set(have) - set(want)):
            m.unlink(KIND_ENVIRONMENT, "DELETE", f"{path}/{name}", label=f"environment '{name}'")


def _register(m: Migration, path: str, name: str, have: dict) -> None:
    if have.get(name):
        # Bound on the target but not on the source: a binding only the target has.
        if m.prune:
            m.unlink(KIND_ENVIRONMENT, "DELETE", f"{path}/{name}", label=f"environment '{name}'")
            if name not in BUILT_IN_ENVIRONMENTS:
                _post_register(m, path, name)
        else:
            m.report.add(KIND_ENVIRONMENT, "kept")
            m.report.notes.append(
                f"environment '{name}' is bound on the target but not on the source (left alone)"
            )
        return
    if name in have or name in BUILT_IN_ENVIRONMENTS:
        m.report.add(KIND_ENVIRONMENT, "unchanged")
        return
    m.report.add(KIND_ENVIRONMENT, "create")
    _post_register(m, path, name)


def _post_register(m: Migration, path: str, name: str) -> None:
    m.log(f"  register environment '{name}'")

    def exists() -> bool:
        return name in (m.dst.get(path).get("environments") or {})

    m.post_link(path, exists, body={"name": name})


def _bind(m: Migration, path: str, name: str, pointer: dict, have: dict) -> None:
    experiment_id = m.mapped("experiment", pointer["experiment_id"])
    copied = m.mapped("experiment version", f"{pointer['experiment_id']}:{pointer['version']}")
    if not experiment_id or not copied:
        m.report.add(KIND_ENVIRONMENT, "skipped")
        m.report.notes.append(
            f"environment '{name}' points at an experiment version that wasn't copied "
            "(another user's private experiment, or one whose history differs); bind it by hand"
        )
        return
    body = {"experiment_id": experiment_id, "version": pointer["version"]}
    if have.get(name) and not changed_fields(body, have[name]):
        m.report.add(KIND_ENVIRONMENT, "unchanged")
        return
    m.report.add(KIND_ENVIRONMENT, "update" if name in have else "create")
    m.log(f"  bind environment '{name}' to {pointer['version']}")
    m.put(f"{path}/{name}", body)
