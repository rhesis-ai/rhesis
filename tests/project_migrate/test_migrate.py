"""End-to-end behaviour of the project migration tool against two fake Rhesis instances."""

import json

import pytest
from conftest import World
from fake_rhesis import Crash, FakeRhesis
from project_migrate.api import Abort, Api, HttpError
from project_migrate.cli import build_parser, load_snapshot
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
