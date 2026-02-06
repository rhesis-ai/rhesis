import urllib.parse
import uuid
from typing import TYPE_CHECKING, Any, Callable, List, Optional

import pandas as pd

from rhesis.sdk import adaptive_testing
from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode, TopicNode
from rhesis.sdk.entities import Prompt, Test, TestSet
from rhesis.sdk.models import BaseEmbedder, BaseLLM

from ._prompt_builder import PromptBuilder
from ._test_tree_browser import TestTreeBrowser


def _is_under_topic(parent_path: str, child_path: str) -> bool:
    """Check if child_path is equal to or under parent_path."""
    if parent_path == child_path:
        return True
    if not parent_path:
        return True  # Everything is under root
    parent = TopicNode(path=parent_path)
    child = TopicNode(path=child_path)
    return parent.is_ancestor_of(child)


if TYPE_CHECKING:
    from rhesis.sdk.entities import TestSet

# class TestTreeIterator():
#     def __init__(self, test_tree):
#         self.test_tree = test_tree
#         self.position = 0

#     def __next__(self):
#         if self.position >= len(self.test_tree):
#             raise StopIteration
#         else:
#             self.position += 1
#             return self.test_tree.iloc[self.position - 1]


class TestTree:
    """A hierarchically organized set of tests represented as a DataFrame.

    This represents a hierarchically organized set of tests that all target a
    specific class of models (such as sentiment analysis models, or translation
    models). To interact with a test tree you can use either the `__call__`
    method to view and create tests directly in a Jupyter notebook, or you can
    call the `serve` method to launch a standalone webserver. A TestTree object
    also conforms to most of the standard pandas DataFrame API.
    """

    def __init__(
        self,
        tests=None,
        index=None,
        ensure_topic_markers=True,
        cache_file=None,
        **kwargs,
    ):
        """Create a new test tree.

        Parameters
        ----------
        tests : str or DataFrame or list or tuple or None
            The tests to load as a test tree. If a string is provided, it is
            assumed to be a path to a CSV file containing the tests. If tests
            is a tuple of two elements, it is assumed to be a dataset of
            (data, labels) which will be used to build a test tree. Otherwise
            tests is passed to the pandas DataFrame constructor.

        index : list or list-like or None
            Assigns an index to underlying tests frame, or auto generates if not provided.

        kwargs : dict
            Additional keyword arguments are passed to the pandas DataFrame constructor.
        """

        self._tests = tests

    @property
    def name(self):
        return "Tests"

    # NOTE: Can't delegate to df.append as it is deprecated in favor of
    # pd.concat, which we can't use due to type checks
    def append(self, test_tree, axis=0):
        if isinstance(test_tree, pd.DataFrame):
            self._tests = pd.concat([self._tests, test_tree], axis=axis)
        elif isinstance(test_tree, TestTree):
            self._tests = pd.concat([self._tests, test_tree._tests], axis=axis)
        elif isinstance(test_tree, dict):
            # check if the values are strings or lists of strings
            if any([isinstance(v, str) for v in test_tree.values()]):
                self._tests = pd.concat(
                    [
                        self._tests,
                        pd.DataFrame(
                            {k: [test_tree[k]] for k in test_tree}, index=[uuid.uuid4().hex]
                        ),
                    ],
                    axis=axis,
                )
            else:
                self._tests = pd.concat([self._tests, pd.DataFrame(test_tree)], axis=axis)

        return None  # TODO: Rethink append logic -- return copy vs. in place update?

    def __len__(self):
        return len(self._tests)

    def to_test_set(
        self,
        include_suggestions: bool = False,
    ) -> "TestSet":
        """Convert the TestTree to an SDK TestSet for persistence.

        This method converts the hierarchical test tree into SDK entities that can
        be pushed to the Rhesis backend.

        Parameters
        ----------

        include_suggestions : bool, optional
            Whether to include suggestion rows (under /__suggestions__ topics).
            Default is False.

        Returns
        -------
        TestSet
            An SDK TestSet instance containing Test objects converted from the tree.
            The TestSet is not yet pushed to the backend - call .push() on it to save.

        Examples
        --------
        >>> tree = TestTree("my_tests.csv")
        >>> test_set = tree.to_test_set(name="My Test Set")
        >>> test_set.push()  # Save to backend

        >>> # Or load, adapt, and save
        >>> tree = TestTree("tests.csv")
        >>> browser = tree.adapt(generator=gen, endpoint=endpoint, metrics=scorer)
        >>> # ... interactive editing ...
        >>> tree.to_test_set(name="Updated Tests").push()

        Notes
        -----
        - Topic markers (rows with label="topic_marker") are skipped
        - The full topic path (e.g., "/Safety/Violence") is preserved in Test.topic
        - All node fields are stored in metadata for complete round-trip support:
          tree_id, output, label, labeler, model_score
        """
        tests = []

        for node in self._tests:
            # Skip suggestions unless explicitly included
            if not include_suggestions and "/__suggestions__" in node.topic:
                continue

            # Decode URI-encoded topic (spaces are encoded as %20)
            topic = urllib.parse.unquote(node.topic) if node.topic else ""

            prompt = Prompt(content=node.input)

            # Store all node fields in metadata for complete round-trip
            metadata = {
                "tree_id": str(node.id),
                "output": node.output,
                "label": node.label,
                "labeler": node.labeler,
                "model_score": node.model_score,
            }

            test = Test(
                topic=topic,
                prompt=prompt,
                metadata=metadata,
                behavior="Adaptive Testing",
                category="Adaptive Testing",
            )
            tests.append(test)

        return TestSet(name=self.name, tests=tests)

    @classmethod
    def from_test_set(cls, test_set: "TestSet") -> "TestTreeData":
        """Create a TestTree from an SDK TestSet.

        This method converts SDK Test entities back into the hierarchical
        test tree format, enabling adaptive testing on existing test sets.

        Parameters
        ----------
        test_set : TestSet
            An SDK TestSet instance. Can be either fetched from the backend
            (with .pull()) or created locally.

        Returns
        -------
        TestTree
            A new TestTree instance populated with tests from the TestSet.

        Examples
        --------
        >>> from rhesis.sdk.entities import TestSet
        >>> # Load from backend
        >>> test_set = TestSet(id="test-set-uuid")
        >>> test_set.pull()
        >>> tree = TestTree.from_test_set(test_set)
        >>> browser = tree.adapt(generator=gen, endpoint=endpoint, metrics=scorer)

        >>> # Round-trip: edit and save back
        >>> tree = TestTree.from_test_set(test_set)
        >>> # ... interactive editing ...
        >>> updated_test_set = tree.to_test_set(name=test_set.name)
        >>> updated_test_set.push()

        Notes
        -----
        - Test.topic is used directly as the hierarchical topic path
        - Test.prompt.content becomes input
        - All fields (output, label, labeler, model_score) are restored from metadata
          with sensible defaults for backward compatibility
        - Tests without prompts are skipped (e.g., multi-turn tests)
        """
        nodes = []

        for test in test_set.tests or []:
            # Handle both dict and Test objects
            if isinstance(test, dict):
                test = Test(**test)

            # Extract metadata early to check for topic markers
            meta = test.metadata or {}
            is_topic_marker = meta.get("label") == "topic_marker"

            # Skip tests without prompts (multi-turn tests use test_configuration)
            # But allow topic markers which have empty prompts
            if not is_topic_marker and (not test.prompt or not test.prompt.content):
                continue

            # Get topic and URI encode for internal consistency
            topic = test.topic or ""
            topic = urllib.parse.quote(topic, safe="/")

            # Build node kwargs - use test.id (database ID) if available,
            # otherwise fall back to tree_id from metadata
            node_kwargs = {
                "topic": topic,
                "input": test.prompt.content if test.prompt else "",
                "output": meta.get("output", "[no output]"),
                "label": meta.get("label", ""),
                "labeler": meta.get("labeler", "imported"),
                "model_score": meta.get("model_score", 0.0),
            }
            if test.id:
                node_kwargs["id"] = test.id
            elif meta.get("tree_id"):
                node_kwargs["id"] = meta["tree_id"]

            nodes.append(TestTreeNode(**node_kwargs))

        return TestTreeData(nodes=nodes)

    def topic(self, topic_path: str) -> "TestTree":
        """Return a subset of the test tree containing only tests that match the given topic.

        Parameters
        ----------
        topic_path : str
            The topic to filter the test tree by.
        """
        filtered_nodes = [node for node in self._tests if _is_under_topic(topic_path, node.topic)]
        return TestTree(TestTreeData(nodes=filtered_nodes), ensure_topic_markers=False)

    def topic_has_direct_tests(self, target_topic: str) -> bool:
        """Check if a topic has direct tests."""
        return any(
            node.topic == target_topic and node.label != "topic_marker" for node in self._tests
        )

    def topic_has_subtopics(self, target_topic: str) -> bool:
        """Check if a topic has subtopics."""
        return any(
            node.topic != target_topic and _is_under_topic(target_topic, node.topic)
            for node in self._tests
        )

    def adapt(
        self,
        generator: Optional[Any] = None,
        endpoint: Optional[Callable[[List[str]], List[str]]] = None,
        metrics: Optional[Callable[[List[str], List[str]], List[float]]] = None,
        embedder: Optional[BaseEmbedder] = None,
        user: str = "anonymous",
        recompute_scores: bool = False,
        regenerate_outputs: bool = False,
        max_suggestions: int = 100,
        prompt_variants: int = 4,
        prompt_builder: PromptBuilder = PromptBuilder(),
        starting_path: str = "",
        score_filter: float = -1e10,
    ) -> TestTreeBrowser:
        """Apply this test tree to an endpoint and metrics scorer to browse/edit tests.

        Parameters
        ----------
        generator : adaptive_testing.Generator
            A source to generate new tests from. Currently supported generator types are language
            models, existing test trees, or datasets.

        endpoint : callable
            The Rhesis endpoint function that takes a list of input strings and returns a list of
            output strings. This is the target model/system being tested.

        metrics : callable
            The Rhesis scorer/metrics function that takes (inputs, outputs) and returns a list of
            scores. Scores should be between 0 and 1, where higher values indicate failures.

        embedder : BaseEmbedder
            The text embedding model to use for similarity-based suggestions. Should be an
            instance of `rhesis.sdk.models.BaseEmbedder` (e.g., from `get_embedder()`).
            If not provided, defaults to OpenAI text-embedding-3-small (768 dimensions).

        user : str
            The user name to author new tests with.

        recompute_scores : bool
            Whether to recompute the scores of the tests that already have score values.
            This will re-run the endpoint but preserve existing outputs if they differ.

        regenerate_outputs : bool
            Whether to regenerate outputs by re-running all tests through the endpoint.
            This will overwrite existing outputs with fresh ones from the endpoint and
            recompute scores. Implies recompute_scores=True.

        max_suggestions : int
            The maximum number of suggestions to generate each time the user asks for suggestions.

        prompt_variants : int
            Number of different prompt variants to generate. Each variant contains different
            example tests, leading to more diverse suggestions. Default is 4.

        prompt_builder : adaptive_testing.PromptBuilder
            A prompt builder to use when generating prompts for new tests.

        starting_path : str
            The path to start browsing the test tree from.

        score_filter : float
            Minimum score threshold for filtering suggestions.
        """
        # Wrap BaseLLM instances in LLMGenerator
        if generator is not None and isinstance(generator, BaseLLM):
            generator = adaptive_testing.generators.LLMGenerator(generator)

        # regenerate_outputs implies recompute_scores
        if regenerate_outputs:
            recompute_scores = True

        # build the test tree browser
        return TestTreeBrowser(
            self,
            generator=generator,
            endpoint=endpoint,
            metrics=metrics,
            embedder=embedder,
            user=user,
            recompute_scores=recompute_scores,
            regenerate_outputs=regenerate_outputs,
            max_suggestions=max_suggestions,
            prompt_variants=prompt_variants,
            prompt_builder=prompt_builder,
            starting_path=starting_path,
            score_filter=score_filter,
        )

    def __repr__(self):
        return self._tests.__repr__()

    def _repr_html_(self):
        return self._tests._repr_html_()

    def _cache_embeddings(self, ids=None, embedder=None):
        """Pre-compute the embeddings for the given test cases.

        This is used so we can batch the computation don't compute them one at a time later.

        Parameters
        ----------
        ids : list, optional
            List of test IDs to cache embeddings for. If None, uses all tests.
        embedder : object
            The embedder to use for computing embeddings.
        """
        from .embedders import embed_with_cache

        if embedder is None:
            return  # No embedder provided, skip caching

        if ids is None:
            ids = self._tests.index

        # see what new embeddings we need to compute
        all_strings = []
        for node_id in ids:
            node = self._tests[node_id]
            if node.label == "topic_marker":
                parts = node.topic.rsplit("/", 1)
                s = parts[1] if len(parts) == 2 else ""
                all_strings.append(s)
            else:
                for s in [node.input, node.output]:
                    all_strings.append(s)

        # cache the embeddings
        if all_strings:
            embed_with_cache(embedder, all_strings)

    def drop_topic(self, topic_path: str):
        """Remove a topic and all its direct contents from the test tree."""
        ids_to_remove = [node.id for node in self._tests if node.topic == topic_path]
        for node_id in ids_to_remove:
            del self._tests._nodes[node_id]
        # Invalidate topic tree cache
        if hasattr(self._tests, "_topic_tree"):
            self._tests._topic_tree.invalidate_cache()

    def validate(self) -> dict:
        """Validate the test tree structure.

        This method checks that for every topic used by tests, there exists a
        corresponding topic_marker node. It also checks all parent topics in
        the hierarchy.

        Returns
        -------
        dict
            A dictionary with validation results:
            - 'valid': bool - True if all topics have markers
            - 'missing_markers': list[str] - List of topic paths missing markers
            - 'topics_with_tests': list[str] - All topics that have tests
            - 'topics_with_markers': list[str] - All topics that have markers

        Examples
        --------
        >>> tree = TestTree(data)
        >>> result = tree.validate()
        >>> if not result['valid']:
        ...     print(f"Missing markers for: {result['missing_markers']}")
        """
        return self._tests.validate()
