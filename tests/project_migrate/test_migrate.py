"""End-to-end behaviour of the project migration tool against two fake Rhesis instances."""

import json

import pytest
from conftest import World
from fake_rhesis import Crash, FakeRhesis
from project_migrate.api import Abort, Api, HttpError
from project_migrate.cli import build_parser, count_table, load_snapshot
from project_migrate.state import State

SOURCE_TESTS = 10  # 9 with a prompt, plus one multi-turn test without
PROMPTED_TESTS = 9


def assert_in_sync(world: World, snap: dict) -> None:
    """The same check `verify` makes: nothing left to do, and nothing duplicated."""
    report = world.run(snap, dry=True)
    assert report.pending_work() == 0, report.render()
    tests = world.rows("tests")
    prompts = world.rows("prompts")
    assert len(tests) == SOURCE_TESTS
    assert len(prompts) == PROMPTED_TESTS, "orphan or duplicate prompts"
    assert len({t["prompt_id"] for t in tests if t.get("prompt_id")}) == PROMPTED_TESTS
    # 2 project metrics plus the org-level custom one, copied into the project.
    for table, n in (("endpoints", 2), ("requirements", 3), ("metrics", 3), ("test_sets", 2)):
        names = [r["name"] for r in world.rows(table)]
        assert len(names) == n == len(set(names)), table


def target_test(world: World, content: str) -> dict:
    prompt = next(p for p in world.rows("prompts") if p["content"] == content)
    return next(t for t in world.rows("tests") if t.get("prompt_id") == prompt["id"])


def by_name(world: World, table: str, name: str) -> dict:
    return next(r for r in world.rows(table) if r["name"] == name)


def test_fresh_copy_matches_source(world):
    snap = world.snapshot()
    world.run(snap)
    assert_in_sync(world, snap)

    copied = target_test(world, "question 1")
    assert copied["test_parameters"] == {"account": "A1"}
    assert copied["test_metadata"] == {"case": 1}
    prompt = world.dst.db["prompts"][copied["prompt_id"]]
    assert (prompt["language_code"], prompt["expected_response"]) == ("de", "expected: question 1")
    assert world.dst.db["requirements"][copied["requirement_id"]]["name"] == "Answers are grounded"

    child = by_name(world, "requirements", "Answers are grounded")
    assert child["parent_id"] == by_name(world, "requirements", "Answers")["id"]

    # A test in two sets stays one test.
    core, regression = (
        by_name(world, "test_sets", "Core"),
        by_name(world, "test_sets", "Regression"),
    )
    shared = target_test(world, "question 2")["id"]
    assert shared in world.dst.set_tests[core["id"]]
    assert shared in world.dst.set_tests[regression["id"]]

    # The built-in metric link points at the target's own seeded copy.
    builtin = next(m for m in world.dst.db["metrics"].values() if m["name"] == "Answer Relevancy")
    assert builtin["id"] in world.dst.set_metrics[core["id"]]


def test_endpoint_secrets_are_not_copied(world):
    snap = world.snapshot()
    report = world.run(snap)
    chat = by_name(world, "endpoints", "Chat API")
    assert chat["has_auth_token"] is False
    assert chat["request_mapping"]["account"] == "{{ test_parameters.account }}"
    assert any("Chat API" in n and "secret" in n for n in report.notes)


def test_soft_deleted_requirement_is_rebuilt(world):
    snap = world.snapshot()
    assert any("Retired requirement" in line for line in world.logs)
    world.run(snap)
    copied = target_test(world, "old question")
    assert world.dst.db["requirements"][copied["requirement_id"]]["name"] == "Retired requirement"


def test_second_apply_makes_no_writes(world):
    snap = world.snapshot()
    world.run(snap)
    writes = world.dst.writes
    report = world.run(snap)
    assert world.dst.writes == writes
    assert report.pending_work() == 0


def test_lost_state_file_still_matches_everything(world, tmp_path):
    snap = world.snapshot()
    world.run(snap)
    writes = world.dst.writes
    report = world.run(snap, state_path=tmp_path / "fresh-state.json")
    assert report.pending_work() == 0, report.render()
    assert world.dst.writes == writes


def test_identical_source_tests_pair_one_to_one(world, tmp_path):
    snap = world.snapshot()
    world.run(snap)
    # Without state, the two identical tests can only be told apart by count.
    world.run(snap, state_path=tmp_path / "fresh-state.json")
    same = [
        t
        for t in world.rows("tests")
        if t.get("prompt_id")
        and world.dst.db["prompts"][t["prompt_id"]]["content"] == "same question"
    ]
    assert len(same) == 2


@pytest.mark.parametrize("path", ["^/tests/$", "^/prompts/$", "^/requirements/$", "^/metrics/$"])
def test_create_that_saved_but_timed_out_is_adopted(world, path):
    world.dst.fail("POST", path, "commit_then_drop")
    snap = world.snapshot()
    report = world.run(snap)
    assert_in_sync(world, snap)
    assert sum(r.get("adopt", 0) for r in report.rows.values()) == 1


def test_create_that_never_landed_is_posted_again(world):
    world.dst.fail("POST", "^/prompts/$", "drop")
    world.dst.fail("POST", "^/tests/$", "drop")
    snap = world.snapshot()
    world.run(snap)
    assert_in_sync(world, snap)


def test_unclear_link_is_checked_before_posting_again(world):
    world.dst.fail("POST", "/associate$", "commit_then_drop")
    world.dst.fail("POST", "^/requirements/.+/metrics/.+$", "commit_then_drop")
    snap = world.snapshot()
    world.run(snap)
    assert_in_sync(world, snap)


def test_crash_at_any_write_resumes_without_duplicates(tmp_path):
    """Kill the run at every single write, both just before and just after the server saves
    it, then resume. Every variant must end in sync with no duplicate or orphan."""
    probe = World(tmp_path / "probe")
    snap = probe.snapshot()
    probe.run(snap)
    total = probe.dst.writes

    for before_commit in (False, True):
        for n in range(1, total + 1):
            world = World(tmp_path / f"{before_commit}-{n}")
            world.dst.crash_after_writes(n, before_commit=before_commit)
            with pytest.raises(Crash):
                world.run(snap)
            world.dst.crash_at = None
            world.run(snap)
            assert_in_sync(world, snap)


def test_source_edit_updates_only_changed_fields(world):
    snap = world.snapshot()
    world.run(snap)
    edited = next(t for t in snap["tests"] if t["_prompt"]["content"] == "question 3")
    edited["test_metadata"] = {"case": 3, "note": "edited"}
    edited["_prompt"]["content"] = "question 3, reworded"
    world.dst.log.clear()

    report = world.run(snap)
    assert report.rows["test"]["update"] == 1
    puts = [(path.split("/")[1], body) for method, path, body in world.dst.log if method == "PUT"]
    assert sorted(puts, key=str) == sorted(
        [("prompts", {"content": "question 3, reworded"}),
         ("tests", {"test_metadata": {"case": 3, "note": "edited"}})], key=str
    )  # fmt: skip


def test_limit_copies_only_the_first_tests_then_the_rest(world):
    snap = world.snapshot()
    world.run(snap, limit=2)
    assert len(world.rows("tests")) == 2
    world.run(snap)
    assert_in_sync(world, snap)


def test_plan_writes_nothing(world):
    snap = world.snapshot()
    report = world.run(snap, dry=True)
    assert world.dst.writes == 0
    assert report.rows["test"]["create"] == SOURCE_TESTS
    assert not world.state_path.exists()


def test_duplicate_source_names_abort_before_writing(world):
    snap = world.snapshot()
    snap["metrics"].append({**snap["metrics"][0], "id": "another-id"})
    with pytest.raises(Abort, match="duplicate metrics names"):
        world.run(snap)
    assert world.dst.writes == 0


def test_two_target_records_with_one_name_abort(world):
    snap = world.snapshot()
    for _ in range(2):
        world.dst.insert("test_sets", project_id=world.dst_pid, name="Core")
    with pytest.raises(Abort, match="named 'Core'"):
        world.run(snap)


def test_client_error_aborts_and_keeps_state(world):
    world.dst.fail("POST", "^/metrics/$", "422")
    snap = world.snapshot()
    with pytest.raises(HttpError, match="HTTP 422"):
        world.run(snap)
    state = State(world.state_path, dry=True).data["entries"]
    assert any(e["status"] == "pending" for k, e in state.items() if k.startswith("metric:"))
    world.run(snap)
    assert_in_sync(world, snap)


def test_429_waits_for_retry_after(world):
    world.dst.fail("GET", "^/endpoints/$", "429", retry_after="7")
    world.run(world.snapshot())
    assert 7.0 in world.clock.sleeps


def test_5xx_on_read_is_retried(world):
    world.dst.fail("GET", "^/tests/$", "503")
    world.dst.fail("GET", "^/tests/$", "connect")
    snap = world.snapshot()
    world.run(snap)
    assert_in_sync(world, snap)


def test_gives_up_after_repeated_failures():
    fake = FakeRhesis()
    for _ in range(10):
        fake.fail("GET", "^/projects/", "503")
    from fake_rhesis import FakeClock

    api = Api("https://x.test", "key", "p", transport=fake, clock=FakeClock(), log=lambda m: None)
    with pytest.raises(Abort, match="gave up"):
        api.get("/projects/p")


def test_writes_are_paced(world):
    snap = world.snapshot()
    world.dst.write_times.clear()
    world.run(snap)
    gaps = [b - a for a, b in zip(world.dst.write_times, world.dst.write_times[1:], strict=False)]
    assert gaps and min(gaps) >= 0.5 - 1e-9  # default 2 writes per second


def test_old_snapshot_without_version_loads_and_unknown_version_fails(tmp_path):
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"meta": {}, "tests": []}))
    assert load_snapshot(str(old))["tests"] == []
    new = tmp_path / "new.json"
    new.write_text(json.dumps({"format_version": 99}))
    with pytest.raises(Abort, match="format 99"):
        load_snapshot(str(new))


def test_multi_turn_test_is_copied_and_never_duplicated(world):
    world.dst.fail("POST", "^/tests/$", "commit_then_drop")
    snap = world.snapshot()
    report = world.run(snap)
    assert report.rows["test"]["adopt"] == 1
    assert_in_sync(world, snap)
    copied = [t for t in world.rows("tests") if not t.get("prompt_id")]
    assert [t["test_configuration"] for t in copied] == [{"goal": "Get a refund", "max_turns": 5}]


def test_first_test_create_unclear_without_prompt_is_adopted(world):
    # Order the multi-turn test first so the very first unclear create is the prompt-less one.
    snap = world.snapshot()
    snap["tests"].sort(key=lambda t: t.get("prompt_id") is not None)
    world.dst.fail("POST", "^/tests/$", "commit_then_500")
    report = world.run(snap)
    assert report.rows["test"]["adopt"] == 1
    assert_in_sync(world, snap)


def test_org_level_custom_metric_is_copied_but_builtins_are_matched(world):
    snap = world.snapshot()
    report = world.run(snap)
    org = by_name(world, "metrics", "Org policy")
    assert org["project_id"] == world.dst_pid
    assert any("Org policy" in n for n in report.notes)
    builtins = [m for m in world.dst.db["metrics"].values() if m["name"] == "Answer Relevancy"]
    assert len(builtins) == 1


def test_test_without_project_in_a_set_is_copied(world):
    snap = world.snapshot()
    world.run(snap)
    copied = target_test(world, "loose question")
    assert copied["id"] in world.dst.set_tests[by_name(world, "test_sets", "Core")["id"]]


def test_test_and_prompt_deleted_on_target_are_recreated(world):
    snap = world.snapshot()
    world.run(snap)
    gone = target_test(world, "question 4")
    del world.dst.db["prompts"][gone["prompt_id"]]
    del world.dst.db["tests"][gone["id"]]
    world.run(snap)
    assert_in_sync(world, snap)


def test_key_removed_on_source_is_removed_on_target(world):
    snap = world.snapshot()
    world.run(snap)
    edited = next(
        t for t in snap["tests"] if (t.get("_prompt") or {}).get("content") == "question 2"
    )
    # What's left is a subset of the target's value, so only an exact compare catches it.
    edited["test_parameters"] = {}
    world.run(snap)
    assert target_test(world, "question 2")["test_parameters"] == {}
    assert world.run(snap, dry=True).pending_work() == 0


def test_limit_must_be_positive():
    parser = build_parser()
    common = ["--snapshot", "s", "--dst-url", "u", "--dst-project", "p"]
    assert parser.parse_args(["plan", *common, "--limit", "3"]).limit == 3
    with pytest.raises(SystemExit):
        parser.parse_args(["plan", *common, "--limit", "0"])


def test_500_on_read_is_retried(world):
    world.dst.fail("GET", "^/test_sets/$", "500")
    snap = world.snapshot()
    world.run(snap)
    assert_in_sync(world, snap)


def test_journal_replays_and_ignores_a_torn_line(tmp_path):
    path = tmp_path / "state.json"
    state = State(path, dry=False)
    state.put("test:a", status="pending")
    state.put("test:a", status="done", target_id="t1")
    with open(state.journal_path, "a") as f:
        f.write('{"key": "test:b", "fie')  # the process died mid-write
    reloaded = State(path, dry=False)
    assert reloaded.get("test:a")["target_id"] == "t1"
    assert reloaded.get("test:b") is None
    reloaded.save()
    assert not reloaded.journal_path.exists()
    assert State(path, dry=True).get("test:a")["status"] == "done"


def test_sources_and_their_links_are_copied(world):
    snap = world.snapshot()
    world.run(snap)
    assert_in_sync(world, snap)
    copied = next(r for r in world.dst.db["sources"].values() if r["title"] == "Policy handbook")
    assert copied["content"] == "Refunds are allowed within 30 days."
    # The file isn't copied, so the source's storage path and hash are left behind.
    assert copied["source_metadata"] == {"file_type": "pdf"}
    assert world.dst.db["type_lookups"][copied["source_type_id"]]["type_value"] == "Document"
    parent = by_name(world, "requirements", "Answers")
    assert world.dst.req_source == {(parent["id"], copied["id"]): "section 3"}


def test_a_changed_link_note_is_updated(world):
    snap = world.snapshot()
    world.run(snap)
    parent = next(r for r in snap["requirements"] if r["name"] == "Answers")
    parent["sources"][0]["note"] = "section 4"
    report = world.run(snap)
    assert report.rows["requirement-source link"]["link"] == 1
    assert list(world.dst.req_source.values()) == ["section 4"]


def test_parameter_schema_is_copied_once(world):
    snap = world.snapshot()
    world.run(snap)
    stored = world.dst.db["projects"][world.dst_pid]["parameters_schema"]
    assert stored == {"fields": [{"name": "temperature", "type": "number", "default": 0.2}]}
    assert world.run(snap).rows["parameter schema"] == {"unchanged": 1}


def test_target_without_parameters_api_skips_the_schema(world):
    world.dst.has_parameters_api = False
    world.dst.has_experiments_api = False  # both arrived in the same release
    snap = world.snapshot()
    report = world.run(snap)
    assert any("no parameters API" in n for n in report.notes)
    assert_in_sync(world, snap)


def test_sdk_endpoints_are_skipped_with_a_note(world):
    snap = world.snapshot()
    report = world.run(snap)
    assert "Connector function" not in {e["name"] for e in world.rows("endpoints")}
    assert report.rows["endpoint"]["skipped"] == 1
    assert any("Connector function" in n and "SDK" in n for n in report.notes)


def test_literal_credential_headers_are_flagged(world):
    report = world.run(world.snapshot())
    flagged = [n for n in report.notes if "X-Partner-Token" in n]
    assert len(flagged) == 1
    assert "x-api-key" not in flagged[0]  # a template, not a literal


def test_verify_counts_match_after_a_copy(world):
    snap = world.snapshot()
    world.run(snap)
    report = world.run(snap, dry=True)
    counts = count_table(report, world.api("dst"))
    assert all(expected == actual for _, expected, actual in counts), counts
    assert dict((name, n) for name, n, _ in counts)["custom metrics"] == 3  # 2 + org-level copy


def _add_extra_links(world: World) -> None:
    core = by_name(world, "test_sets", "Core")
    stray = target_test(world, "question 4")["id"]  # a real test, but not in Core on the source
    world.dst.set_tests[core["id"]].append(stray)
    toxicity = next(m for m in world.dst.db["metrics"].values() if m["name"] == "Toxicity")
    world.dst.set_metrics[core["id"]].append(toxicity["id"])
    child = by_name(world, "requirements", "Answers are grounded")
    world.dst.req_metric.add((child["id"], toxicity["id"]))
    handbook = next(iter(world.dst.db["sources"].values()))
    world.dst.req_source[(child["id"], handbook["id"])] = None


def test_extra_target_links_stay_without_prune(world):
    snap = world.snapshot()
    world.run(snap)
    _add_extra_links(world)
    report = world.run(snap)
    assert "unlink" not in str(report.rows)
    assert any("extra test" in n for n in report.notes)
    assert len(world.dst.req_source) == 2


def test_prune_removes_only_the_extra_links(world):
    snap = world.snapshot()
    world.run(snap)
    _add_extra_links(world)
    report = world.run(snap, prune=True)
    assert sum(r.get("unlink", 0) for r in report.rows.values()) == 4
    assert world.run(snap, dry=True, prune=True).pending_work() == 0
    assert_in_sync(world, snap)
    assert len(world.dst.req_source) == 1


def test_prune_with_an_old_snapshot_leaves_source_links_alone(world):
    snap = world.snapshot()
    world.run(snap)
    old = {k: v for k, v in snap.items() if k not in ("sources", "parameter_schema")}
    report = world.run(old, prune=True)
    assert "requirement-source link" not in report.rows
    assert len(world.dst.req_source) == 1


def test_prune_skips_a_requirement_with_an_unmapped_source(world, tmp_path):
    snap = world.snapshot()
    world.run(snap)
    # The linked source is missing from this snapshot, so its target link can't be mapped and
    # must not be mistaken for an extra one.
    partial = {**snap, "sources": []}
    world.run(partial, prune=True, state_path=tmp_path / "fresh-state.json")
    assert len(world.dst.req_source) == 1


def test_duplicate_source_titles_abort_before_writing(world):
    snap = world.snapshot()
    snap["sources"].append({**snap["sources"][0], "id": "another-id"})
    with pytest.raises(Abort, match="duplicate sources names"):
        world.run(snap)
    assert world.dst.writes == 0


def _target_schema(world: World) -> list[str]:
    stored = world.dst.db["projects"][world.dst_pid].get("parameters_schema") or {"fields": []}
    return [f["name"] for f in stored["fields"]]


def test_schema_fields_only_on_the_target_are_kept_unless_pruned(world):
    world.dst.db["projects"][world.dst_pid]["parameters_schema"] = {
        "fields": [{"name": "local_only", "type": "text"}]
    }
    snap = world.snapshot()
    world.run(snap)
    assert sorted(_target_schema(world)) == ["local_only", "temperature"]
    assert world.run(snap, dry=True).pending_work() == 0
    world.run(snap, prune=True)
    assert _target_schema(world) == ["temperature"]


def test_an_empty_source_schema_leaves_the_target_alone(world):
    world.dst.db["projects"][world.dst_pid]["parameters_schema"] = {
        "fields": [{"name": "local_only", "type": "text"}]
    }
    snap = world.snapshot()
    snap["parameter_schema"] = {"fields": []}
    world.run(snap, prune=True)
    assert _target_schema(world) == ["local_only"]


def test_schema_keys_the_target_does_not_know_are_ignored(world):
    snap = world.snapshot()
    snap["parameter_schema"]["fields"][0]["added_in_a_newer_version"] = True
    world.run(snap)
    assert world.run(snap, dry=True).rows["parameter schema"] == {"unchanged": 1}


def test_an_sdk_endpoint_registered_on_the_target_later_keeps_verify_green(world):
    snap = world.snapshot()
    world.run(snap)
    world.dst.insert(
        "endpoints", project_id=world.dst_pid, name="Connector function", connection_type="SDK"
    )
    counts = count_table(world.run(snap, dry=True), world.api("dst"))
    assert all(expected == actual for _, expected, actual in counts), counts


def test_prune_counts_and_names_each_removed_test(world):
    snap = world.snapshot()
    world.run(snap)
    core = by_name(world, "test_sets", "Core")
    for content in ("question 3", "question 4", "loose question"):
        test_id = target_test(world, content)["id"]
        if test_id not in world.dst.set_tests[core["id"]]:
            world.dst.set_tests[core["id"]].append(test_id)
    world.logs.clear()
    report = world.run(snap, dry=True, prune=True)
    assert report.rows["test set-test link"]["unlink"] == 2
    assert any("unlink test set-test link: test set 'Core'" in line for line in world.logs)


def test_an_unlink_that_went_through_but_timed_out_is_not_an_error(world):
    snap = world.snapshot()
    world.run(snap)
    _add_extra_links(world)
    world.dst.fail("DELETE", "/sources/", "commit_then_drop")
    world.dst.fail("POST", "/disassociate$", "commit_then_drop")
    world.run(snap, prune=True)
    assert world.run(snap, dry=True, prune=True).pending_work() == 0


def test_target_without_sources_api_skips_sources_and_their_links(world):
    world.dst.has_sources_api = False
    snap = world.snapshot()
    report = world.run(snap, prune=True)
    assert any("no sources API" in n for n in report.notes)
    assert "requirement-source link" not in report.rows
    assert_in_sync(world, snap)
    counts = count_table(world.run(snap, dry=True), world.api("dst"))
    assert "sources" not in {name for name, _, _ in counts}


def _experiments(world: World) -> dict[str, dict]:
    return {
        e["name"]: e for e in world.dst.experiments.values() if e["project_id"] == world.dst_pid
    }


def _values(exp: dict) -> list[float]:
    return [v["values"]["temperature"]["value"] for v in exp["versions"]]


def test_experiments_are_copied_with_their_history(world):
    snap = world.snapshot()
    world.run(snap)
    copied = _experiments(world)
    tuning = copied["Prompt tuning"]
    assert (tuning["visibility"], tuning["description"]) == ("shared", "Lower temperature")
    assert [v["version"] for v in tuning["versions"]] == ["v1", "v2", "v3"]
    assert _values(tuning) == [0.2, 0.1, 0.4]
    assert [v["message"] for v in tuning["versions"]] == ["baseline", "cooler", "warmer"]
    assert copied["Scratch"]["visibility"] == "private"


def test_environments_point_at_the_copied_versions(world):
    snap = world.snapshot()
    world.run(snap)
    envs = world.dst.environments[world.dst_pid]
    tuning = _experiments(world)["Prompt tuning"]
    assert envs["production"] == {"experiment_id": tuning["id"], "version": "v2"}
    assert envs["canary"] is None
    assert "staging" not in envs  # built in: never registered


def test_experiments_rerun_and_lost_state_make_no_writes(world, tmp_path):
    snap = world.snapshot()
    world.run(snap)
    writes = world.dst.writes
    assert world.run(snap).pending_work() == 0
    assert world.run(snap, state_path=tmp_path / "fresh-state.json").pending_work() == 0
    assert world.dst.writes == writes


def test_a_new_source_version_is_appended_alone(world):
    snap = world.snapshot()
    world.run(snap)
    tuning = next(e for e in snap["experiments"] if e["name"] == "Prompt tuning")
    tuning["versions"].append(
        {"version": "v4", "values": {"temperature": {"type": "number", "value": 0.3}},
         "message": "middle", "parent_version": "v3"}
    )  # fmt: skip
    report = world.run(snap)
    assert report.rows["experiment version"] == {"unchanged": 4, "create": 1}  # 3 + Scratch v1
    assert _values(_experiments(world)["Prompt tuning"]) == [0.2, 0.1, 0.4, 0.3]


def test_a_target_history_that_differs_is_left_alone(world):
    snap = world.snapshot()
    target = world.dst.add_experiment(world.dst_pid, "Prompt tuning")
    world.dst.db["projects"][world.dst_pid]["parameters_schema"] = {
        "fields": [{"name": "temperature", "type": "number", "default": 0.2}]
    }
    world.dst.add_version(target, {"temperature": {"type": "number", "value": 0.7}})
    report = world.run(snap)
    assert _values(target) == [0.7]
    assert report.rows["experiment version"]["diverged"] == 1
    assert any("Prompt tuning" in n and "differs" in n for n in report.notes)
    # production points at v2 of that experiment, so it is not bound either
    assert "production" not in world.dst.environments.get(world.dst_pid, {})


def test_versions_that_collapse_on_the_target_stop_the_replay(world):
    snap = world.snapshot()
    scratch = next(e for e in snap["experiments"] if e["name"] == "Scratch")
    # Two versions that differ only in a field the target's schema doesn't have.
    scratch["versions"] = [
        {"version": "v1", "values": {"temperature": {"type": "number", "value": 0.9},
                                     "retired": {"type": "text", "value": "a"}}},
        {"version": "v2", "values": {"temperature": {"type": "number", "value": 0.9},
                                     "retired": {"type": "text", "value": "b"}}},
    ]  # fmt: skip
    report = world.run(snap)
    assert any("Scratch" in n for n in report.notes)
    assert len(_experiments(world)["Scratch"]["versions"]) == 1


def test_an_unclear_version_save_is_not_duplicated(world):
    world.dst.fail("POST", "^/experiments/.+/versions$", "commit_then_drop")
    snap = world.snapshot()
    report = world.run(snap)
    assert report.rows["experiment version"]["adopt"] == 1
    assert [v["version"] for v in _experiments(world)["Prompt tuning"]["versions"]] == [
        "v1", "v2", "v3"
    ]  # fmt: skip


def test_target_without_experiments_api_skips_them(world):
    world.dst.has_experiments_api = False
    snap = world.snapshot()
    report = world.run(snap, prune=True)
    assert any("no experiments API" in n for n in report.notes)
    assert "environment" not in report.rows
    assert_in_sync(world, snap)


def test_old_snapshot_without_experiments_changes_nothing(world):
    snap = world.snapshot()
    old = {k: v for k, v in snap.items() if k not in ("experiments", "environments")}
    world.run(old, prune=True)
    assert _experiments(world) == {}


def test_prune_unbinds_environments_the_source_lacks(world):
    snap = world.snapshot()
    world.run(snap)
    world.dst.environments[world.dst_pid]["qa"] = None
    report = world.run(snap, prune=True)
    assert report.rows["environment"]["unlink"] == 1
    assert "qa" not in world.dst.environments[world.dst_pid]


def test_a_version_the_target_rejects_is_reported_and_the_run_continues(world):
    snap = world.snapshot()
    scratch = next(e for e in snap["experiments"] if e["name"] == "Scratch")
    scratch["versions"][0]["values"]["temperature"] = {"type": "text", "value": "hot"}
    report = world.run(snap)
    assert any("Scratch" in n and "rejected v1" in n for n in report.notes)
    assert_in_sync_except_experiments(world, snap)


def assert_in_sync_except_experiments(world: World, snap: dict) -> None:
    report = world.run(snap, dry=True)
    rows = {k: v for k, v in report.rows.items() if not k.startswith("experiment")}
    assert all(a in ("unchanged", "linked", "skipped") for r in rows.values() for a in r), rows


def test_experiment_pages_shortened_by_hidden_private_ones_are_all_read(world):
    for i in range(150):
        world.src.add_experiment(world.seed["project_id"], f"hidden {i}", visibility="private",
                                 owner="someone-else")  # fmt: skip
    for i in range(30):
        world.src.add_experiment(world.seed["project_id"], f"late {i}")
    snap = world.snapshot()
    names = {e["name"] for e in snap["experiments"]}
    assert {f"late {i}" for i in range(30)} <= names
    assert not any(n.startswith("hidden") for n in names)


def test_a_renamed_source_experiment_renames_the_copy(world):
    snap = world.snapshot()
    world.run(snap)
    next(e for e in snap["experiments"] if e["name"] == "Scratch")["name"] = "Scratch pad"
    world.run(snap)
    assert sorted(_experiments(world)) == ["Prompt tuning", "Scratch pad"]


def test_an_update_the_target_refuses_is_reported(world):
    snap = world.snapshot()
    world.run(snap)
    _experiments(world)["Prompt tuning"]["owner"] = "someone-else"
    next(e for e in snap["experiments"] if e["name"] == "Prompt tuning")["description"] = "new"
    report = world.run(snap)
    assert report.rows["experiment"]["refused"] == 1
    assert any("Prompt tuning" in n and "403" in n for n in report.notes)


def test_a_binding_only_the_target_has_is_kept_unless_pruned(world):
    snap = world.snapshot()
    world.run(snap)
    tuning = _experiments(world)["Prompt tuning"]
    world.dst.environments[world.dst_pid]["canary"] = {
        "experiment_id": tuning["id"],
        "version": "v1",
    }
    report = world.run(snap)
    assert report.rows["environment"]["kept"] == 1
    assert world.dst.environments[world.dst_pid]["canary"] is not None
    world.run(snap, prune=True)
    assert world.dst.environments[world.dst_pid]["canary"] is None


def test_a_refused_update_still_syncs_versions_and_environments(world):
    snap = world.snapshot()
    world.run(snap)
    tuning = next(e for e in snap["experiments"] if e["name"] == "Prompt tuning")
    tuning["description"] = "new"
    tuning["versions"].append(
        {"version": "v4", "values": {"temperature": {"type": "number", "value": 0.3}},
         "message": "middle", "parent_version": "v3"}
    )  # fmt: skip
    snap["environments"]["environments"]["production"]["version"] = "v4"
    copy = _experiments(world)["Prompt tuning"]
    # An environment points at it, so the target refuses to make it private: 409.
    tuning["visibility"] = "private"
    report = world.run(snap)
    assert report.rows["experiment"]["refused"] == 1
    assert [v["version"] for v in copy["versions"]][-1] == "v4"
    assert world.dst.environments[world.dst_pid]["production"]["version"] == "v4"


def test_versions_on_a_copy_another_user_owns_are_reported(world):
    snap = world.snapshot()
    world.run(snap)
    _experiments(world)["Prompt tuning"]["owner"] = "someone-else"
    tuning = next(e for e in snap["experiments"] if e["name"] == "Prompt tuning")
    tuning["versions"].append(
        {"version": "v4", "values": {"temperature": {"type": "number", "value": 0.3}}}
    )
    report = world.run(snap)
    assert any("Prompt tuning" in n and "HTTP 403" in n for n in report.notes)
    assert_in_sync_except_experiments(world, snap)
