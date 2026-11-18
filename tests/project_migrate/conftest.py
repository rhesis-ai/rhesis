"""Put `scripts` on sys.path so `project_migrate` imports the way `./rh project-migrate` runs it."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_rhesis import FakeClock, FakeRhesis  # noqa: E402
from project_migrate.api import Api  # noqa: E402
from project_migrate.cli import run_migration  # noqa: E402
from project_migrate.snapshot import take_snapshot  # noqa: E402
from project_migrate.state import State  # noqa: E402


def quiet(_msg: str) -> None:
    pass


def seed_source(src: FakeRhesis) -> dict:
    """A small project that exercises every path: parents, a soft-deleted requirement, a built-in
    metric link, a test in two sets, tests in no set, and two identical tests."""
    pid = src.insert("projects", name="Source project")["id"]
    single = src.lookup_id("TestType", "Single-Turn")
    custom = src.lookup_id("BackendType", "custom")

    src.insert(
        "endpoints", project_id=pid, name="Chat API", connection_type="REST",
        url="https://chat.example.com/v1/run", method="POST",
        request_headers={"x-api-key": "{{ auth_token }}", "X-Partner-Token": "plain-value"},
        request_mapping={"input": "{{ input }}", "account": "{{ test_parameters.account }}"},
        response_mapping={"output": "$.reply"}, has_auth_token=True,
    )  # fmt: skip
    src.insert("endpoints", project_id=pid, name="Local API", connection_type="REST",
               url="http://localhost:9000/run", method="POST")  # fmt: skip
    src.insert("endpoints", project_id=pid, name="Connector function", connection_type="SDK")
    src.db["projects"][pid]["parameters_schema"] = {
        "fields": [{"name": "temperature", "type": "number", "default": 0.2}]
    }
    handbook = src.insert(
        "sources", project_id=pid, title="Policy handbook", description="Refund rules",
        content="Refunds are allowed within 30 days.",
        source_metadata={"file_type": "pdf", "file_path": "org/1/policy.pdf", "file_hash": "ab12"},
        source_type_id=src.lookup_id("SourceType", "Document"),
    )  # fmt: skip

    parent = src.insert("requirements", project_id=pid, name="Answers", description="Top level",
                        impact_id=src.lookup_id("RequirementImpact", "High"))  # fmt: skip
    child = src.insert("requirements", project_id=pid, name="Answers are grounded",
                       parent_id=parent["id"])  # fmt: skip
    retired = src.insert("requirements", project_id=pid, name="Retired requirement")
    src.req_source[(parent["id"], handbook["id"])] = "section 3"

    grounded = src.insert(
        "metrics", project_id=pid, name="Grounded", evaluation_prompt="Is it grounded?",
        score_type="categorical", categories=["OK", "BAD"], passing_categories=["OK"],
        class_name="CategoricalJudge", metric_scope=["Single-Turn"], backend_type_id=custom,
    )  # fmt: skip
    tone = src.insert(
        "metrics", project_id=pid, name="Tone", evaluation_prompt="Rate the tone",
        score_type="numeric", threshold=3.0, class_name="NumericJudge",
        metric_scope=["Single-Turn"],
    )  # fmt: skip
    builtin = src.insert("metrics", project_id=None, name="Answer Relevancy",
                         class_name="DeepEvalAnswerRelevancy", evaluation_prompt="[deepeval]",
                         score_type="numeric", metric_scope=["Single-Turn"])  # fmt: skip
    org_custom = src.insert("metrics", project_id=None, name="Org policy",
                            class_name="CategoricalJudge", evaluation_prompt="Follows policy?",
                            score_type="categorical", categories=["YES", "NO"],
                            passing_categories=["YES"], metric_scope=["Single-Turn"])  # fmt: skip
    src.req_metric |= {(parent["id"], grounded["id"]), (child["id"], grounded["id"]),
                       (child["id"], tone["id"]), (parent["id"], org_custom["id"])}  # fmt: skip

    topics = [src.insert("topics", project_id=pid, name=n)["id"] for n in ("Billing", "Refunds")]
    cats = [src.insert("categories", project_id=pid, name=n)["id"] for n in ("Harmless", "Edge")]

    def add_test(content, req, n, params, meta=None):
        prompt = src.insert("prompts", project_id=pid, content=content, language_code="de",
                            expected_response=f"expected: {content}")  # fmt: skip
        return src.insert(
            "tests", project_id=pid, prompt_id=prompt["id"], requirement_id=req["id"],
            topic_id=topics[n % 2], category_id=cats[n % 2], test_type_id=single,
            test_parameters=params, test_metadata=meta,
        )["id"]  # fmt: skip

    t = [add_test(f"question {i}", child if i % 2 else parent, i, {"account": f"A{i}"},
                  {"case": i}) for i in range(5)]  # fmt: skip
    twin_a = add_test("same question", child, 0, {"account": "A9"})
    twin_b = add_test("same question", child, 0, {"account": "A9"})
    on_retired = add_test("old question", retired, 1, {"account": "A0"})
    src.deleted.add(retired["id"])
    multi_turn = src.insert(
        "tests", project_id=pid, requirement_id=parent["id"], topic_id=topics[0],
        category_id=cats[0], test_type_id=src.lookup_id("TestType", "Multi-Turn"),
        test_configuration={"goal": "Get a refund", "max_turns": 5},
    )["id"]  # fmt: skip
    # Older data: a test (and its prompt) with no project, reachable only through its set.
    loose_prompt = src.insert("prompts", project_id=None, content="loose question",
                              language_code="en")  # fmt: skip
    loose = src.insert("tests", project_id=None, prompt_id=loose_prompt["id"],
                       requirement_id=parent["id"], topic_id=topics[1], category_id=cats[1],
                       test_type_id=single)["id"]  # fmt: skip

    set_type = src.lookup_id("TestSetType", "Single-Turn")
    s1 = src.insert("test_sets", project_id=pid, name="Core", description="core set",
                    test_set_type_id=set_type)["id"]  # fmt: skip
    s2 = src.insert("test_sets", project_id=pid, name="Regression",
                    test_set_type_id=set_type)["id"]  # fmt: skip
    src.set_tests = {s1: [t[0], t[1], t[2], loose], s2: [t[2], t[3], on_retired, multi_turn]}
    src.set_metrics = {s1: [grounded["id"], builtin["id"]], s2: [tone["id"]]}
    return {"project_id": pid, "tests": t, "twins": [twin_a, twin_b]}


def seed_target(dst: FakeRhesis) -> str:
    pid = dst.insert("projects", name="Target project")["id"]
    dst.insert("metrics", project_id=None, name="Answer Relevancy",
               class_name="DeepEvalAnswerRelevancy", evaluation_prompt="[deepeval]",
               score_type="numeric", metric_scope=["Single-Turn"])  # fmt: skip
    dst.insert("metrics", project_id=None, name="Toxicity", class_name="DeepEvalToxicity",
               evaluation_prompt="[deepeval]", score_type="numeric",
               metric_scope=["Single-Turn"])  # fmt: skip
    return pid


class World:
    """A seeded source, an empty target project, and helpers to run the tool between them."""

    def __init__(self, tmp_path: Path):
        self.clock = FakeClock()
        self.src = FakeRhesis(self.clock)
        self.seed = seed_source(self.src)
        self.state_path = tmp_path / "state.json"
        self.dst = FakeRhesis(self.clock)
        self.dst_pid = seed_target(self.dst)
        self.logs: list[str] = []

    def api(self, side: str) -> Api:
        fake, pid = (
            (self.src, self.seed["project_id"]) if side == "src" else (self.dst, self.dst_pid)
        )
        return Api(f"https://{side}.test", "key", pid, transport=fake, clock=self.clock, log=quiet)

    def snapshot(self) -> dict:
        # Round-trip through JSON like the real file on disk.
        snap = take_snapshot(self.api("src"), log=self.logs.append)
        return json.loads(json.dumps(snap, default=str))

    def run(
        self,
        snap: dict,
        *,
        dry: bool = False,
        limit: int | None = None,
        prune: bool = False,
        state_path=None,
    ):
        state = State(state_path or self.state_path, dry)
        return run_migration(
            snap, self.api("dst"), state, dry=dry, limit=limit, prune=prune, log=self.logs.append
        )

    def rows(self, table: str) -> list[dict]:
        return [r for r in self.dst.db[table].values() if r.get("project_id") == self.dst_pid]


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)
