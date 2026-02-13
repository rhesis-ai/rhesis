# ruff: noqa: E501
# This file has example strings in templatize() that are intentionally formatted
import copy
import itertools
import json
import logging
import pathlib
import re
import uuid
from typing import TYPE_CHECKING, Callable, Union

import numpy as np

from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode

# from ._scorer import expand_template, clean_template, Scorer
from .comm import JupyterComm
from .generators import Generator

if TYPE_CHECKING:
    from rhesis.sdk.models import BaseEmbedder

    from ._prompt_builder import PromptBuilder
    from .embedders import EmbedderAdapter

log = logging.getLogger(__name__)


# import sys
# sys.stderr = open('/tmp/err.txt', 'w')


def expand_template(s, keep_braces=False):
    """Expand a template string into a list of strings."""
    # parts = []
    # for s in strings:
    matches = re.findall("{[^}]*}", s)
    s = re.sub("{[^}]*}", "{}", s)
    template_groups = [str(m)[1:-1].split("|") for m in matches]
    try:
        if keep_braces:
            return [
                s.format(*["{{{p}}}" for p in parts])
                for parts in itertools.product(*template_groups)
            ]
        else:
            return [s.format(*parts) for parts in itertools.product(*template_groups)]
    except ValueError:
        return [s]  # we return the template not filled in if it is invalid


def clean_template(s):
    """This removes duplicate template entries."""
    matches = re.findall("{[^}]*}", s)
    s = re.sub("{[^}]*}", "{}", s)
    template_groups = [str(m)[1:-1].split("|") for m in matches]
    clean_groups = [
        "{" + "|".join(list({v: None for v in g}.keys())) + "}" for g in template_groups
    ]
    try:
        return s.format(*clean_groups)
    except ValueError:
        return s  # we return the template not cleaned in if it is invalid


def matches_filter(test, filter_text):
    if filter_text is None or filter_text == "":
        return True
    else:
        return filter_text in test.input or filter_text in test.output


valid_comparators = ["should not be", "should be", "should be the same as for"]
FILLIN_PREFIX = "/Fill-ins"


# model("this is english") => []
# output_sampling="topk(10)"
# output_sampling="topp(10)"
# output_sampling="max"
# output_sampling="temperature(0.9)"


class TestTreeBrowser:
    """Used for browsing and expanding a test tree."""

    def __init__(
        self,
        test_tree: "TestTreeData",
        generator: Generator,
        endpoint: Callable[[list[str]], list[str]],
        metrics: Callable[[list[str], list[str]], list[float]],
        embedder: Union["BaseEmbedder", "EmbedderAdapter", None],
        user: str,
        recompute_scores: bool,
        regenerate_outputs: bool,
        max_suggestions: int,
        prompt_variants: int,
        prompt_builder: "PromptBuilder",
        starting_path: str,
        score_filter: Union[float, str],
    ) -> None:
        """Initialize the TestTreeBrowser."""
        from rhesis.sdk.models import BaseEmbedder

        from .embedders import EmbedderAdapter

        self.test_tree = test_tree._tests
        self.topic_tree = self.test_tree.topics

        self.endpoint = endpoint
        self.metrics = metrics
        self.generator = generator
        self.user = user
        self.recompute_scores = recompute_scores
        self.regenerate_outputs = regenerate_outputs
        self.max_suggestions = max_suggestions
        self.prompt_variants = prompt_variants
        self.prompt_builder = prompt_builder
        self.current_topic = starting_path
        self.score_filter = score_filter
        self.filter_text = ""
        self._id = uuid.uuid4().hex
        self.mode = "tests"  # default mode: "tests" or "topics"

        # Set up embedder - wrap BaseEmbedder in adapter for caching compatibility
        if embedder is not None:
            if isinstance(embedder, BaseEmbedder):
                self.embedder = EmbedderAdapter(embedder)
            else:
                # Already an adapter or compatible object
                self.embedder = embedder
        else:
            raise ValueError("Embedder is required")

        # if we are recomputing the scores then we erase all the old scores
        # Reset scores if recomputing
        if recompute_scores is True:
            for node in self.test_tree:
                node.model_score = float("nan")

        # if regenerating outputs, force all tests to be re-evaluated
        if regenerate_outputs is True:
            for node in self.test_tree:
                if node.label != "topic_marker":
                    node.to_eval = True

        # these are all temporary state
        self._hidden_topics = {}
        self.comm = None

        # apply all the scorers to the test tree (this updates the test tree)
        # When regenerate_outputs=True, overwrite existing outputs with fresh ones from endpoint
        self._compute_embeddings_and_scores(
            recompute=self.recompute_scores,
            overwrite_outputs=self.regenerate_outputs,
            save_outputs=not self.regenerate_outputs,
        )

        # # make sure all the tests have scores (if we have a scorer)
        # self._compute_embeddings_and_scores(self.test_tree)

        # ensure test tree based generator has embeddings calculated
        if getattr(self.generator, "gen_type", "") == "test_tree":
            self.generator.source._cache_embeddings(embedder=self.embedder)

        # init a blank set of suggetions
        self._suggestions_error = ""  # tracks if we failed to generate suggestions

    def embed(self, strings):
        """Embed strings using the configured embedder."""
        from .embedders import embed_with_cache

        return embed_with_cache(self.embedder, strings)

    def _repr_html_(self, prefix="", environment="jupyter", websocket_server=None):
        """Returns the HTML interface for this browser.

        Parameters
        ----------
        prefix : str
            The URL prefix this test tree browser is being served from.

        environment : str
            The environment this test tree browser is being served from (jupyter or web).
        """

        # spin up a JupyterComm object if we are called directly (which we assume is in a notebook)
        if self.comm is None and environment == "jupyter":
            self.comm = JupyterComm(f"adatest_interface_target_{self._id}", self.interface_event)

        # dump the client javascript to the interface
        file_path = pathlib.Path(__file__).parent.absolute()
        with open(file_path / "resources" / "main.js", encoding="utf-8") as f:
            js_data = f.read()
        interface_html = f"""
<div id="adatest_container_{self._id}" style="width: 100%; all: initial;"></div>
<script type='text/javascript'>
  {js_data};
  AdaTestReactDOM.render(
    AdaTestReact.createElement(AdaTest, {{
      interfaceId: "{self._id}",
      environment: "{environment}",
      startingTopic: "{self.current_topic}",
      prefix: "{prefix}",
      websocket_server: {"undefined" if websocket_server is None else '"' + websocket_server + '"'},
    }}, null),
    document.getElementById('adatest_container_{self._id}')
  );
</script>
"""
        return interface_html

    def interface_event(self, msg):
        """Handle interface events from the client.

        Parameters
        ----------
        msg : dict
            The event messages from the client. Each key in the dictionary is a
            separate message to either the row specified by the key or to whole
            browser object if the key is 'browser'.
        """

        log.debug(f"interface_event({msg})")

        if "event_id" not in msg:
            log.error("interface_event: missing event_id. msg dump: %s", msg)
            return
        event_id = msg["event_id"]

        # redraw the entire interface
        if event_id == "redraw":
            self._refresh_interface()

        # generate a new set of suggested tests/topics
        elif event_id == "generate_suggestions":
            self._clear_suggestions()
            self._generate_suggestions(filter=msg.get("filter", ""))
            # if self._active_generator_obj is None:
            #     self._suggestions_error = "No adaptive_testing generator has been set!"
            # else:
            #     self._generate_suggestions(filter=msg[k].get("filter", ""))
            # # try:
            # self.suggestions = self._generate_suggestions(filter=msg[k].get("filter", ""))
            # # filter suggestions to relevant types
            # if self.mode == "topics":
            #     self.suggestions = self.suggestions[self.suggestions['type'] == "topic_marker"]
            # elif self.mode == "tests":
            #     self.suggestions = self.suggestions[self.suggestions['type'] != "topic_marker"]

            # # Ensure valid suggestions exist.
            # if self.suggestions.shape[0] > 0:
            #     self.suggestions.sort_values(
            #         self.score_columns[0], inplace=True, ascending=False,
            #         key=np.vectorize(score_max)
            #     )
            #     self._suggestions_error = ""
            # else:
            #     self._suggestions_error = True # Not sure if we should do this?
            # except Exception as e:
            #     log.debug(e)
            #     self.suggestions = pd.DataFrame([], columns=self.test_tree.columns)
            #     self._suggestions_error = True
            self._refresh_interface()

        # change the current topic (navigate to a different topic)
        elif event_id == "change_topic":
            self.current_topic = msg["topic"].lstrip("/")  # Remove leading slash
            self._refresh_interface()

        # clear the current set of suggestions
        elif event_id == "clear_suggestions":
            self._clear_suggestions()
            # self.suggestions = pd.DataFrame([], columns=self.test_tree.columns)
            self._refresh_interface()

        # add a new empty subtopic to the current topic
        elif event_id == "add_new_topic":
            new_topic_path = (
                self.current_topic + "/New topic" if self.current_topic else "New topic"
            )
            self.topic_tree.create(new_topic_path, labeler=self.user)
            self._refresh_interface()

        # add a new empty test to the current topic
        elif event_id == "add_new_test":
            # add the new test row (special value "New test" causes interface to auto-select)
            node = TestTreeNode(
                topic=self.current_topic,
                input="New test",
                output="",
                label="",
                labeler="imputed",
            )
            self.test_tree[node.id] = node

            self._refresh_interface()

        # change which scorer/model is used for sorting tests
        # NOTE: Currently only single model_score supported, this is a no-op
        elif event_id == "set_first_model":
            self._refresh_interface()

        elif event_id == "change_mode":
            self.mode = msg["mode"]

        elif event_id == "change_filter":
            print("change_filter")
            self.filter_text = msg["filter_text"]
            self._refresh_interface()

        # Move a test/topic to a new path (also used for renaming)
        elif event_id == "move_test":
            log.debug(f"move_test: test_ids={msg['test_ids']}, topic={msg['topic']}")
            test_ids = msg["test_ids"]
            new_path = msg["topic"].lstrip("/")  # Remove leading slash if present

            for test_id in test_ids:
                if test_id in self.test_tree.index:
                    # It's a node UUID - move that single node to the new topic
                    self.test_tree[test_id].topic = new_path
                    log.debug(f"  Moved node {test_id} to {new_path}")
                else:
                    # It's a topic path - move/rename the entire topic
                    topic = self.topic_tree.get(test_id)
                    if topic:
                        self.topic_tree.move(topic, new_path)
                        log.debug(f"  Moved topic {test_id} to {new_path}")

            self._compute_embeddings_and_scores()
            self._refresh_interface()

        elif event_id == "delete_test":
            log.debug("delete_test")
            test_ids = msg["test_ids"]
            # test_id can either be a unique test ID or a topic path
            for test_id in test_ids:
                if test_id in self.test_tree.index:
                    # It's a node UUID - delete that single node
                    del self.test_tree._nodes[test_id]
                else:
                    # It's a topic path - delete the topic and all its contents
                    topic = self.topic_tree.get(test_id)
                    if topic:
                        self.topic_tree.delete(topic, move_tests_to_parent=False)
            self._compute_embeddings_and_scores()
            self._refresh_interface()

        # if we are just updating a single row in tests then we only recompute the scores
        elif (
            event_id == "change_label" or event_id == "change_input" or event_id == "change_output"
        ):
            sendback_data = {}
            test_id = msg["test_ids"][0]

            # update the node fields and recompute scores
            node = self.test_tree[test_id]

            # convert template expansions into a standard value update
            if msg.get("action", "") == "template_expand":
                template_value = self.templatize(getattr(node, msg["value"]))
                msg = {msg["value"]: template_value}
                sendback_data[msg["value"]] = template_value

            metadata_fields = ["event_id", "test_ids"]
            for k2 in msg:
                if k2 not in metadata_fields and hasattr(node, k2):
                    setattr(node, k2, msg[k2])
            if event_id == "change_input":
                node.model_score = float("nan")
                node.to_eval = True
                self._compute_embeddings_and_scores(overwrite_outputs="output" not in msg)
            elif event_id == "change_label":
                # sign = -1 if msg["label"] == "pass" else 1
                # self.test_tree.loc[test_id, self.score_columns] = (
                #     abs(float(self.test_tree.loc[test_id, self.score_columns])) * sign
                # )
                # SML: we could recompute the scores here but then that would change
                # the output of stochastic output models
                pass
                # self._compute_embeddings_and_scores(self.test_tree, overwrite_outputs=False)

            # send just the data that changed back to the frontend
            sendback_data["scores"] = {
                "model_score": [[test_id, v] for v in ui_score_parts(node.model_score, node.label)]
            }
            # if the output was given to us the client is managing its current state
            # so we shouldn't send it back
            if "output" not in msg:
                sendback_data["output"] = node.output
            sendback_data["label"] = node.label
            sendback_data["labeler"] = node.labeler
            sendback_data.update(self.test_display_parts(node))
            self.comm.send({test_id: sendback_data})

        else:
            log.error(f"Unable to parse the interface message: {msg}")

    def _refresh_interface(self):
        """Send our entire current state to the frontend interface."""

        data = {}

        # Build data for current topic
        children = self._build_topic_children(data, self.current_topic)

        # Build data for suggestions
        suggestions_topic = (
            self.current_topic + "/__suggestions__" if self.current_topic else "__suggestions__"
        )
        suggestions_children = self._build_topic_children(data, suggestions_topic)

        # TODO: This is a complete hack to hide lower scoring suggestions when we are
        # likely already in the exploit phase
        # this is just for users who don't know when to stop scrolling down...
        # SML: I expect we can delete this at some point?
        if self.score_filter == "auto":
            if len(children) < 10:
                score_filter = -1e12
            else:
                children_scores = sorted(
                    [
                        np.max([score_max(x[1]) for x in data[key]["scores"]["model_score"]])
                        for key in children
                    ]
                )
                suggestions_children_scores = sorted(
                    [
                        np.max([score_max(x[1]) for x in data[key]["scores"]["model_score"]])
                        for key in suggestions_children
                    ]
                )
                score_filter = (
                    children_scores[-5] - (children_scores[-1] - children_scores[-5]) * 0.2
                )
                if len(suggestions_children_scores) > 0:
                    score_filter = min(score_filter, np.nanmax(suggestions_children_scores) - 1e-2)
        else:
            score_filter = self.score_filter

        # Compute mode based on current topic structure
        # "topics" mode: Generate creates subtopics; "tests" mode: Generate creates tests
        current = self.topic_tree.get(self.current_topic) if self.current_topic else None
        if current:
            has_direct_tests = self.topic_tree.has_direct_tests(current)
            has_subtopics = self.topic_tree.has_subtopics(current)
        else:
            # At root level
            has_direct_tests = False
            has_subtopics = len(self.topic_tree.get_children(None)) > 0
        self.mode = "topics" if not has_direct_tests and has_subtopics else "tests"

        topic_marker_id = self._get_topic_marker_id(self.current_topic)
        # compile the global browser state for the frontend
        data["browser"] = {
            "suggestions": suggestions_children,
            "tests": children,
            "user": self.user,
            "topic": self.current_topic,
            "topic_marker_id": topic_marker_id if topic_marker_id is not None else uuid.uuid4().hex,
            "score_filter": score_filter,
            "disable_suggestions": False,
            "read_only": False,
            "score_columns": ["model_score"],
            "suggestions_error": self._suggestions_error,
            "mode": self.mode,
            "test_tree_name": "Tests",
            # "test_types": test_types,
            # "test_type_parts": test_type_parts,
        }

        self.comm.send(data)

    def _build_topic_children(self, data: dict, topic_path: str) -> list[str]:
        """Build UI data for children of a topic and return sorted child IDs.

        Args:
            data: Dictionary to populate with UI data (modified in place)
            topic_path: The topic path to get children for

        Returns:
            Sorted list of child IDs (topic paths for folders, node IDs for tests)
        """
        children = []

        # Get child topics (folders)
        child_topics = self._get_child_topics_for_path(topic_path)
        for child_topic in child_topics:
            marker_id = self.topic_tree.get_topic_marker_id(child_topic)

            # Get all tests under this topic for aggregate scoring
            all_tests = self.topic_tree.get_tests(child_topic, recursive=True)
            scores = []
            for test in all_tests:
                scores.extend([[test.id, v] for v in ui_score_parts(test.model_score, test.label)])

            data[child_topic.path] = {
                "label": "topic_marker",
                "labeler": "",
                "scores": {"model_score": scores},
                "topic_marker_id": marker_id,
                "topic_name": child_topic.name,
                "editing": child_topic.name == "New topic",
            }
            children.append(child_topic.path)

        # Get direct tests (not in subtopics)
        direct_tests = self._get_direct_tests_for_path(topic_path)
        for test in direct_tests:
            if not matches_filter(test, self.filter_text):
                continue

            data[test.id] = {
                "input": test.input,
                "output": test.output,
                "label": test.label,
                "labeler": test.labeler,
                "scores": {
                    "model_score": [
                        [test.id, v] for v in ui_score_parts(test.model_score, test.label)
                    ]
                },
                "editing": test.input == "New test",
            }
            data[test.id].update(self.test_display_parts(test))
            children.append(test.id)

        # Sort children
        return self._sort_children(children, data)

    def _get_child_topics_for_path(self, topic_path: str) -> list:
        """Get child topics for a path, handling __suggestions__ pseudo-topics."""
        from .schemas import TopicNode

        if "__suggestions__" in topic_path:
            # For suggestions, manually find child topic markers
            child_topics = []
            prefix = topic_path + "/"
            seen = set()
            for node in self.test_tree:
                if node.label == "topic_marker" and node.topic.startswith(prefix):
                    # Extract direct child only
                    remainder = node.topic[len(prefix) :]
                    if "/" not in remainder and node.topic not in seen:
                        seen.add(node.topic)
                        child_topics.append(TopicNode(path=node.topic))
            return child_topics
        else:
            # Use TopicTree for regular topics
            topic = self.topic_tree.get(topic_path) if topic_path else None
            return self.topic_tree.get_children(topic)

    def _get_direct_tests_for_path(self, topic_path: str) -> list:
        """Get direct tests for a path, handling __suggestions__ pseudo-topics."""
        if "__suggestions__" in topic_path:
            # For suggestions, manually find direct tests
            return [
                node
                for node in self.test_tree
                if node.topic == topic_path and node.label != "topic_marker"
            ]
        else:
            # Use TopicTree for regular topics
            topic = self.topic_tree.get(topic_path) if topic_path else None
            if topic:
                return self.topic_tree.get_tests(topic, recursive=False)
            else:
                # Root level - get tests with empty topic
                return [
                    node
                    for node in self.test_tree
                    if node.topic == "" and node.label != "topic_marker"
                ]

    def _sort_children(self, children: list[str], data: dict) -> list[str]:
        """Sort children by score and type."""

        def sort_key(id):
            try:
                total = 0
                count = 0
                for s in data[id]["scores"]["model_score"]:
                    val = score_max(s[1], nan_val=np.nan)
                    if not np.isnan(val) and val is not None:
                        total += val
                        count += 1
                if count == 0:
                    return 1e3
                else:
                    return -total / count
            except Exception as e:
                log.warning(f"Error sorting {id}: {e}")
                return 1e3

        # Sort by score
        sorted_children = sorted(children, key=sort_key)
        # Put folders first
        sorted_children = sorted(
            sorted_children,
            key=lambda id: 0 if data[id].get("label", "") == "topic_marker" else 1,
        )
        # Put off_topic last
        sorted_children = sorted(
            sorted_children,
            key=lambda id: 1 if data[id].get("label", "") == "off_topic" else 0,
        )
        # Put new items first
        sorted_children = sorted(
            sorted_children,
            key=lambda id: (
                0
                if id.endswith("/New topic")
                or id == "New topic"
                or data[id].get("value1", "") == "New test"
                else 1
            ),
        )

        return sorted_children

    def _clear_suggestions(self):
        """Clear the suggestions for the current topic."""
        suggestions_prefix = (
            self.current_topic + "/__suggestions__" if self.current_topic else "__suggestions__"
        )
        ids_to_delete = [
            node.id for node in self.test_tree if node.topic.startswith(suggestions_prefix)
        ]
        for node_id in ids_to_delete:
            del self.test_tree._nodes[node_id]

    def generate_suggestions(self, topic=None, filter=""):
        if topic is not None:
            self.current_topic = topic
        self._clear_suggestions()
        self._generate_suggestions(filter=filter)

    def _generate_suggestions(self, filter):
        """Generate suggestions for the current topic.

        Parameters
        ----------
        filter : str
            The filter to apply to the tests while generating suggestions.
        """

        # --Backend-driven suggestions--

        # save a lookup we can use to detect duplicate tests
        test_map = {
            f"{test.topic} __topic_marker__"
            if test.label == "topic_marker"
            else f"{test.topic} __JOIN__ {test.input}"
            for test in self.test_tree
        }

        # validity focused (focus first on making valid in-topic tests,
        #   then secondarily on making those tests high scoring)
        # failure focused (focus on making high scoring (failing) tests,
        #   then secondarily on making those tests valid and in-topic)
        # topics (suggest new sub-topics)
        # file_name dataset (suggest tests based on samples from the provided dataset)

        # generate the prompts for the backend
        prompts = self.prompt_builder(
            test_tree=self.test_tree,
            topic=self.current_topic,
            score_column="model_score",
            repetitions=self.prompt_variants,
            filter=filter,
            suggest_topics=self.mode == "topics",
            embed_fn=self.embed,
        )

        # generate the suggestions
        proposals = self.generator(
            prompts,
            self.current_topic,
            self.mode,
            num_samples=self.max_suggestions // len(prompts)
            if len(prompts) > 0
            else self.max_suggestions,
        )

        if self.mode == "topics":
            proposals = list(proposals)

        # Build up suggestions catalog
        if True:  # Always use node-based approach
            # suggestions = []
            test_map_tmp = copy.copy(test_map)
            for input in proposals:
                if self.mode == "topics" and ("/" in input or "\n" in input):
                    input = input.replace("/", " or ").replace(
                        "\n", " "
                    )  # topics can't have newlines or slashes in their names
                    input = input.replace(
                        "  ", " "
                    ).strip()  # kill any double spaces we may have introduced
                    str_val = self.current_topic + "/" + input + " __topic_marker__"
                else:
                    str_val = self.current_topic + " __JOIN__ " + input
                if str_val not in test_map_tmp:
                    # Build suggestion topic path
                    if self.current_topic:
                        suggestion_topic = (
                            self.current_topic
                            + "/__suggestions__"
                            + ("/" + input if self.mode == "topics" else "")
                        )
                    else:
                        # Root level suggestions
                        suggestion_topic = "__suggestions__" + (
                            "/" + input if self.mode == "topics" else ""
                        )
                    node = TestTreeNode(
                        topic=suggestion_topic,
                        input="" if self.mode == "topics" else input,
                        output="[no output]",
                        label="topic_marker" if self.mode == "topics" else "",
                        labeler="imputed",
                        model_score=float("nan"),
                        to_eval=True,
                    )
                    self.test_tree[node.id] = node

                    # s = {
                    #     "topic": self.current_topic + "/__suggestions__"
                    #         + ("/" + input if self.mode == "topics" else ""),
                    #     "input": "" if self.mode == "topics" else input,
                    #     "output": "",
                    #     "label": "",
                    #     "labeler": "imputed",
                    #     "description": ""
                    # }
                    # for c in self.score_columns:
                    #     s[c] = ""
                    # suggestions.append(s)
                    if str_val is not None:
                        test_map_tmp.add(str_val)

            # suggestions = pd.DataFrame(
            #     suggestions, index=[uuid.uuid4().hex for _ in range(len(suggestions))],
            #     columns=self.test_tree.columns
            # )

            # compute the scores for the new tests
            self._compute_embeddings_and_scores()

    def _get_topic_marker_id(self, topic_path: str) -> str | None:
        """
        Returns the id of the topic marker row for the given topic path.
        Returns None if not found.
        """
        topic = self.topic_tree.get(topic_path)
        if topic:
            return self.topic_tree.get_topic_marker_id(topic)
        return None

    def _compute_embeddings_and_scores(
        self, recompute=False, overwrite_outputs=False, save_outputs=False
    ):
        log.debug(
            f"compute_embeddings_and_scores(tests=<TestTreeData len={len(self.test_tree)}>, "
            f"recompute={recompute})"
        )

        eval_ids = [
            node.id for node in self.test_tree if node.to_eval and node.label != "topic_marker"
        ]

        if len(eval_ids) > 0:
            # run the scorer

            eval_inputs = []
            eval_inds = []
            for i, id in enumerate(eval_ids):
                test = self.test_tree[id]
                template_expansions = expand_template(test.input)
                for expansion in template_expansions:
                    eval_inputs.append(expansion)
                    eval_inds.append(i)

            new_outputs = self.endpoint(eval_inputs)

            scores = self.metrics(eval_inputs, new_outputs)

            # update the scores in the test tree
            for i, id in enumerate(eval_ids):
                node = self.test_tree[id]
                # skip topic markers - they shouldn't have outputs or scores
                if node.label == "topic_marker":
                    continue
                node.output = new_outputs[i]
                node.model_score = scores[i]
                node.label = "fail" if scores[i] > 0.5 else "pass"
                node.labeler = "scored"
                node.to_eval = False

    def test_display_parts(self, test):
        # # find which template instantiation has the highest score (and so should be displayed)
        # ui_score_parts = test[self.score_columns[0]].split("|")
        # if len(ui_score_parts) == 1:
        #     max_score_ind = 0
        # else:
        #     max_score_ind = np.argmax([float(v) for v in test[self.score_columns[0]].split("|")])

        # if test.type == "{} should not be completed to become {}":
        #     value1_outputs = safe_json_load(
        #         test.get(self.score_columns[0][:-6] + " value1 outputs", "{}")
        #     ).get("string", [""])
        #     if not isinstance(value1_outputs, list):
        #         value1_outputs = [value1_outputs]
        #     if len(value1_outputs) == 1:
        #         value1_outputs_str = value1_outputs[0]
        #     else:
        #         value1_outputs_str = "{" + "|".join(value1_outputs) + "}"

        #     # hispanic / 95f08d610df74679afc1217f03b9c1b3.template[0]
        #     # "this is a test of[]" should not be completed to become "toxic"
        #     # {}

        #     out = []
        #     expansion_str = test.value1 + "|||" + value1_outputs_str + "|||" + test.value2
        #     for i, option in enumerate(expand_template(expansion_str, keep_braces=False)):
        #         value1_disp,d_text1b,value2_disp = option.split("|||")
        #         out.append({
        #             "d_text1a": '"',
        #             "d_value1": "{}",
        #             "value1_disp": value1_disp,
        #             "d_text1b": d_text1b + '"',
        #             "d_text2a": '"',
        #             "d_value2": "{}",
        #             "value2_disp": value2_disp,
        #             "d_text2b": '"',
        #             "d_text3a": '',
        #             "d_value3": "",
        #             "d_text3b": ''
        #         })
        # else: # this is the default two-value test format that only varies in the select value
        out = [
            {
                "d_text1a": '"',
                "d_value1": "{}",
                "d_text1b": '"',
                "d_text2a": '"',
                "d_value2": "{}",
                "d_text2b": '"',
                "d_text3a": "",
                "d_value3": "",
                "d_text3b": "",
            }
        ]

        return {"display_parts": out}

    def templatize(self, s):
        """This is an experimental function that is not meant to be used generally."""
        from openai import OpenAI

        client = OpenAI()
        prompt = """INPUT: "Where are regular people on Twitter"
    OUTPUT: "Where are {regular|normal|sane|typical} people on {Twitter|Facebook|Reddit|Instagram}"
    ###
    INPUT: "Anyone who says this food tastes horrible is out of their mind"
    OUTPUT: "{Anyone|Someone|He|She} who says this food tastes {horrible|terrible|rotten} is out of their mind"
    ###
    INPUT: "great"
    OUTPUT: "{great|excellent|wonderful|superb|delightful}"
    ###
    INPUT: "If you haven't come here before, you probably live under a rock"
    OUTPUT: "If you haven't come here {before|in the past|before now|yet}, you probably {live under a rock|never get out|are a hermit|are isolated}"
    ###
    INPUT: "Only crazy people would say they had a lousy time"
    OUTPUT: "Only {crazy people|insane people|people with no sense|those out of their mind} would say they had a {lousy|terrible|bad|miserable} time"
    ###
    INPUT: "If I didn't come here again, I would be very happy for the rest of my life"
    OUTPUT: "If I didn't come {here|hereabouts|around here} {again|once more|all over again}, I would be very {happy|glad|pleased|elated} for the rest of my life"
    ###
    INPUT: "I don't know what James was talking about when they said they loved the food."
    OUTPUT: "I don't know what {James|John|Robert|Steve|Bob} was talking about when they {said they|stated that|claimed that|mentioned that} they {loved|liked|adored|appreciated} the food."
    ###
    INPUT: "new_input_value"
    OUTPUT: \""""
        prompt = prompt.replace("new_input_value", s)
        # Use a default model if self.engine is not set (experimental function)
        model = getattr(self, "engine", "text-davinci-003")
        response = client.completions.create(
            model=model, prompt=prompt, max_tokens=300, temperature=0.7, n=4, stop='"'
        )

        lines = [choice.text for choice in response.choices]
        options = []
        for line in lines:
            line = clean_template(line)
            valid = False
            for option in expand_template(line):
                if option == s:
                    valid = True
                    break
            if valid:
                options.append((-len(line), line))
        options.sort()
        log.debug(f"options = {options}")
        return options[0][1]


def score_max(s, nan_val=-1e3):
    if s == "" or s is None:
        return nan_val
    elif isinstance(s, str):
        return np.max([convert_float(v) for v in s.split("|")])
    elif np.isnan(s):
        return nan_val
    else:
        return np.max(s)


def ui_score_parts(s, label):
    """Split a score into its parts and encode the label into the sign.

    Note this encoding is just used for passing scores to the UI
    (scores are not signed in the TestTree).
    """
    offset = 0
    if label == "pass":
        sign = 1
        offset = -1 - 1e-6
    elif label == "fail":
        sign = 1
        offset = 1e-6  # just so we have a positive number to encode that this was a failure
    else:
        sign = np.nan
    if isinstance(s, str):
        return [np.clip(offset + convert_float(v) * sign, -1, 1) for v in s.split("|")]
    else:
        return [np.clip(offset + s * sign, -1, 1)]


def convert_float(s):
    if s == "":
        return np.nan
    try:
        f = float(s)
    except ValueError:
        f = np.nan
    return f


def safe_json_load(input):
    if isinstance(input, float):  # catch NaN's
        return {}
    else:
        return json.loads(input)
