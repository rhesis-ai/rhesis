# ruff: noqa: E501
# This file has example strings in templatize() that are intentionally formatted
import copy
import itertools
import json
import logging
import pathlib
import re
import urllib.parse
import uuid
from typing import TYPE_CHECKING, Callable, Union

import numpy as np
import pandas as pd

from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode
from rhesis.sdk.adaptive_testing.tree_data_ops import return_eval_ids

# from ._scorer import expand_template, clean_template, Scorer
from .comm import JupyterComm
from .generators import Generator
from .utils import is_subtopic

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
        # +++ Change to use remove_scores function
        if recompute_scores is True:
            for c in self.test_tree.columns:
                if c.endswith("score"):
                    self.test_tree.drop(c, axis=1, inplace=True)

        # if regenerating outputs, force all tests to be re-evaluated
        # +++ Change to use set_evaluation_status function
        if regenerate_outputs is True:
            self.test_tree["to_eval"] = True

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

        # change the current topic
        elif event_id == "change_topic":
            self.current_topic = msg["topic"]
            # self.suggestions = pd.DataFrame([], columns=self.test_tree.columns)

            # see if we have only topics as direct children, if so,
            # we suggest topics, otherwise we suggest tests
            has_direct_tests = self.test_tree.topic_has_direct_tests(self.current_topic)
            has_known_subtopics = self.test_tree.topic_has_subtopics(self.current_topic)
            if not has_direct_tests and has_known_subtopics:
                self.mode = "topics"
            else:
                self.mode = "tests"

            self._refresh_interface()

        # clear the current set of suggestions
        elif event_id == "clear_suggestions":
            self._clear_suggestions()
            # self.suggestions = pd.DataFrame([], columns=self.test_tree.columns)
            self._refresh_interface()

        # add a new empty subtopic to the current topic
        elif event_id == "add_new_topic":
            node = TestTreeNode(
                topic=self.current_topic + "/New topic",
                label="topic_marker",
                input="",
                output="",
                labeler=self.user,
            )
            self.test_tree[node.id] = node
            self._compute_embeddings_and_scores()
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
        elif event_id == "set_first_model":
            name = msg["model"]

            # move to front of score columns
            pos = len(self.test_tree.columns) - len(self.score_columns)
            tmp = self.test_tree[name]
            self.test_tree.drop(labels=[name], axis=1, inplace=True)
            self.test_tree.insert(pos, name, tmp)

            # update score columns list
            self.score_columns.remove(name)
            self.score_columns.insert(0, name)

            self._refresh_interface()

        elif event_id == "change_mode":
            self.mode = msg["mode"]

        elif event_id == "change_filter":
            print("change_filter")
            self.filter_text = msg["filter_text"]
            self._refresh_interface()

        # Move a test/topic to a new topic
        # Also used to rename
        elif event_id == "move_test":
            log.debug("move_test")
            test_ids = msg["test_ids"]
            # test_id can either be a unique test ID or a topic name
            for test_id in test_ids:
                if test_id in self.test_tree.index:
                    self.test_tree[test_id].topic = msg["topic"]
                if "/" in test_id:
                    for node in self.test_tree:
                        if is_subtopic(test_id, node.topic):
                            node.topic = msg["topic"] + node.topic[len(test_id) :]
            # Recompute any missing embeddings to handle any changes
            self._compute_embeddings_and_scores()
            self._refresh_interface()

        elif event_id == "delete_test":
            log.debug("delete_test")
            test_ids = msg["test_ids"]
            # test_id can either be a unique test ID or a topic name
            ids_to_delete = []
            for test_id in test_ids:
                if test_id in self.test_tree.index:
                    ids_to_delete.append(test_id)
                if "/" in test_id:
                    # Collect tests from subtopics to delete
                    for node in self.test_tree:
                        if is_subtopic(test_id, node.topic):
                            ids_to_delete.append(node.id)
            # Delete collected nodes
            for node_id in ids_to_delete:
                del self.test_tree._nodes[node_id]
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

        # get the children of the current topic
        data = {}

        def create_children(data, tests, topic):
            children = []

            # add tests and topics to the data lookup structure
            subtopic_ids = [
                node.id for node in tests if re.match(r"^%s(/|$)" % re.escape(topic), node.topic)
            ]
            for k in subtopic_ids:
                test = tests[k]

                # add a topic
                if test.label == "topic_marker":
                    if test.topic != topic:
                        name = test.topic[len(topic) + 1 :]
                        if "/" not in name:  # only add direct children
                            data[test.topic] = {
                                "label": test.label,
                                "labeler": test.labeler,
                                "scores": {"model_score": []},
                                "topic_marker_id": k,
                                "topic_name": name,
                                "editing": test.topic.endswith("/New topic"),
                            }
                            children.append(test.topic)

                # add a test
                elif matches_filter(test, self.filter_text):
                    data[k] = {
                        "input": test.input,
                        "output": test.output,
                        "label": test.label,
                        "labeler": test.labeler,
                        "scores": {
                            "model_score": [
                                [k, v] for v in ui_score_parts(test.model_score, test.label)
                            ]
                        },
                        "editing": test.input == "New test",
                    }

                    data[k].update(self.test_display_parts(test))
                    if test.topic == topic:
                        children.append(k)

            # fill in the scores for the child topics
            for k in subtopic_ids:
                test = tests[k]
                if (
                    "/__suggestions__" not in test.topic
                    and is_subtopic(topic, test.topic)
                    and test.topic != topic
                ):
                    child_topic = test.topic[len(topic) :].split("/", 2)[1]
                    scores = data[topic + "/" + child_topic]["scores"]
                    scores["model_score"].extend(
                        [[k, v] for v in ui_score_parts(test.model_score, test.label)]
                    )

            # sort by score and always put new topics first
            def sort_key(id):
                try:
                    total = 0
                    count = 0
                    # offset = 0 if data[id]["label"] == "fail" else -1
                    for s in data[id]["scores"]["model_score"]:
                        val = score_max(s[1], nan_val=np.nan)
                        if not np.isnan(val) and val is not None:
                            total += val  # + offset
                            count += 1
                    if count == 0:
                        return 1e3
                    else:
                        return -total / count
                except Exception as e:
                    log.warning(f"Error sorting {id}: {e}")
                    return 1e3  # default sort to end

            sorted_children = sorted(children, key=sort_key)
            sorted_children = sorted(
                sorted_children,
                key=lambda id: 0 if data[id].get("label", "") == "topic_marker" else 1,
            )  # put folders first
            sorted_children = sorted(
                sorted_children, key=lambda id: 1 if data[id].get("label", "") == "off_topic" else 0
            )  # off topic last
            sorted_children = sorted(
                sorted_children,
                key=lambda id: 0
                if id.endswith("/New topic") or data[id].get("value1", "") == "New test"
                else 1,
            )  # put new items first

            return sorted_children

        # get the children of the current topic
        children = create_children(data, self.test_tree, self.current_topic)
        suggestions_children = create_children(
            data, self.test_tree, self.current_topic + "/__suggestions__"
        )

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

    def _clear_suggestions(self):
        """Clear the suggestions for the current topic."""
        ids_to_delete = [
            node.id
            for node in self.test_tree
            if node.topic.startswith(self.current_topic + "/__suggestions__")
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
        test_map = {}
        for _, test in self.test_tree.iterrows():
            if test.label == "topic_marker":
                test_map[test.topic + " __topic_marker__"] = True
            else:
                test_map[test.topic + " __JOIN__ " + test.input] = True

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

        # all topics should be URI encoded
        if self.mode == "topics":
            proposals = [urllib.parse.quote(x) for x in proposals]

        # Build up suggestions catalog, unless generating from a test tree source.
        # NOTE: Doing safe checks for TestTree type in order to prevent circular imports
        if isinstance(proposals, pd.DataFrame) or proposals.__class__.__name__ == "TestTree":
            suggestions = proposals
            suggestions["topic"] = (
                self.current_topic
                + "/__suggestions__"
                + suggestions["topic"].apply(
                    lambda x: x[len(self.current_topic) :] if x != "" else ""
                )
            )
            self.test_tree.append(suggestions)
            print("appended suggestions into self.test_tree")
            # assert False, "This needs to be fixed to dump into /__suggestions__"
        else:
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
                    node = TestTreeNode(
                        topic=(
                            self.current_topic
                            + "/__suggestions__"
                            + ("/" + input if self.mode == "topics" else "")
                        ),
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
                        test_map_tmp[str_val] = True

            # suggestions = pd.DataFrame(
            #     suggestions, index=[uuid.uuid4().hex for _ in range(len(suggestions))],
            #     columns=self.test_tree.columns
            # )
            # make sure any duplicates we may have introduced are removed
            self.test_tree.deduplicate()

            # compute the scores for the new tests
            self._compute_embeddings_and_scores()

    def _get_topic_marker_id(self, topic):
        """
        Returns the id of the topic marker row for the given topic.
        Returns None if not found.
        """
        # next() returns first match from generator, or None if no match
        topic_marker_index = next(
            (
                node.id
                for node in self.test_tree
                if node.topic == topic and node.label == "topic_marker"
            ),
            None,
        )
        return topic_marker_index

    def _compute_embeddings_and_scores(
        self, recompute=False, overwrite_outputs=False, save_outputs=False
    ):
        log.debug(
            f"compute_embeddings_and_scores(tests=<TestTreeData len={len(self.test_tree)}>, "
            f"recompute={recompute})"
        )

        eval_ids = return_eval_ids(self.test_tree)

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
