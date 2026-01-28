import urllib.parse
import uuid
from typing import TYPE_CHECKING, Any, Callable, List, Optional

import pandas as pd

from rhesis.sdk import adaptive_testing
from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode
from rhesis.sdk.entities import Prompt, Test, TestSet
from rhesis.sdk.models import BaseEmbedder, BaseLLM

from ._prompt_builder import PromptBuilder
from ._test_tree_browser import TestTreeBrowser, is_subtopic

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

    This represents a hierarchically organized set of tests that all target a specific class of models (such as sentiment
    analysis models, or translation models). To interact with a test tree you can use either the `__call__` method to
    view and create tests directly in a Jupyter notebook, or you can call the `serve` method to launch a standalone
    webserver. A TestTree object also conforms to most of the standard pandas DataFrame API.
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
            The tests to load as a test tree. If a string is provided, it is assumed to be a path to a CSV file containing
            the tests. If tests is a tuple of two elements, it is assumed to be a dataset of (data, labels) which will be used to build a test tree.
            Otherwise tests is passed to the pandas DataFrame constructor to load the tests as a DataFrame.

        index : list or list-like or None
            Assigns an index to underlying tests frame, or auto generates if not provided.

        kwargs : dict
            Additional keyword arguments are passed to the pandas DataFrame constructor.
        """

        self._tests = tests

    @property
    def name(self):
        return "Tests"

    # NOTE: Can't delegate to df.append as it is deprecated in favor of pd.concat, which we can't use due to type checks
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

        # self.deduplicate()
        # self.compute_embeddings()
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
        - Only the input (prompt) is stored - output is execution data, not test definition
        - Test metadata includes: tree_id (for reference back to original tree row)
        """

        tests = []

        for node in self._tests:
            # Skip topic markers - they're structural, not actual tests
            if node.label == "topic_marker":
                continue

            # Skip suggestions unless explicitly included
            if not include_suggestions and "/__suggestions__" in node.topic:
                continue

            # Decode URI-encoded topic (spaces are encoded as %20)
            topic = urllib.parse.unquote(node.topic) if node.topic else ""

            # Build the prompt with input only
            # Output is execution data (goes to TestResult), not test definition
            prompt = Prompt(
                content=node.input,
            )

            # Minimal metadata - just track origin for potential round-trips
            metadata = {
                "tree_id": str(node.id),
            }

            # Create the test
            test = Test(
                topic=topic,
                prompt=prompt,
                metadata=metadata,
                behavior="Adaptive Testing",
                category="Adaptive Testing",
            )
            tests.append(test)

        return TestSet(
            name=self.name,
            tests=tests,
        )

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
        - Output is set to "[no output]" (outputs come from TestResults, not Tests)
        - Tests without prompts are skipped (e.g., multi-turn tests)
        """

        nodes = []

        for test in test_set.tests or []:
            # Handle both dict and Test objects
            if isinstance(test, dict):
                test = Test(**test)

            # Skip tests without prompts (multi-turn tests use test_configuration)
            if not test.prompt or not test.prompt.content:
                continue

            # Get topic - use the full path as stored
            topic = test.topic or ""

            # URI encode topic path (spaces become %20) for internal consistency
            topic = urllib.parse.quote(topic, safe="/")

            # Output is "[no output]" - actual outputs come from TestResults
            # when tests are executed, not from the Test definition
            output = "[no output]"

            nodes.append(
                TestTreeNode(
                    topic=topic,
                    input=test.prompt.content,
                    output=output,
                    label="",  # Will be set after execution/evaluation
                    labeler="imported",
                )
            )

        test_data = TestTreeData(nodes=nodes)
        return test_data

    def topic(self, topic):
        """Return a subset of the test tree containing only tests that match the given topic.

        Parameters
        ----------
        topic : str
            The topic to filter the test tree by.
        """
        ids = [id for id, test in self._tests.iterrows() if is_subtopic(topic, test.topic)]
        return self.loc[ids]

    def topic_has_direct_tests(self, target_topic: str) -> bool:
        """Check if a topic has direct tests."""
        hdt_df = self._tests.apply(
            lambda row: row["topic"] == target_topic and row["label"] != "topic_marker", axis=1
        )
        return hdt_df.any()

    def topic_has_subtopics(self, target_topic: str) -> bool:
        """Check if a topic has subtopics."""
        has_subtopics_df = self._tests.apply(
            lambda row: row["topic"] != target_topic and is_subtopic(target_topic, row["topic"]),
            axis=1,
        )
        return has_subtopics_df.any()

    def adapt(
        self,
        generator: Optional[Any] = None,
        endpoint: Optional[Callable[[List[str]], List[str]]] = None,
        metrics: Optional[Callable[[List[str], List[str]], List[float]]] = None,
        embedder: Optional[BaseEmbedder] = None,
        auto_save: bool = False,
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

        auto_save : bool
            Whether to automatically save the test tree after each edit.

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
            auto_save=auto_save,
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

    def deduplicate(self):
        """Remove duplicate tests from the test tree.

        Note that we give precendence to the first test in a set of duplicates.
        """

        already_seen = {}
        drop_ids = []

        # catch duplicate tests in the same topic
        for id, test in self._tests.iterrows():
            k = test.topic + "|_ADA_JOIN_|" + test.input + "|_ADA_JOIN_|" + test.output
            if k in already_seen:
                drop_ids.append(id)
            else:
                already_seen[k] = True

        # see if any suggestions are duplicates of things already in the their topic
        # (note we do this as a second loop so we know we have already marked all the
        # members of the topic in already_seen)
        for id, test in self._tests.iterrows():
            if test.topic.endswith("/__suggestions__"):
                k = (
                    test.topic[: -len("/__suggestions__")]
                    + "|_ADA_JOIN_|"
                    + test.input
                    + "|_ADA_JOIN_|"
                    + test.output
                )
                if k in already_seen:
                    drop_ids.append(id)
        self._tests.drop(drop_ids, axis=0, inplace=True)

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
        for id in ids:
            test = self._tests.loc[id]
            if test.label == "topic_marker":
                parts = test.topic.rsplit("/", 1)
                s = parts[1] if len(parts) == 2 else ""
                all_strings.append(s)
            else:
                for s in [test.input, test.output]:
                    all_strings.append(s)

        # cache the embeddings
        if all_strings:
            embed_with_cache(embedder, all_strings)

    # def predict_labels(self, topical_io_pairs):
    #     """ Return the label probabilities for a set of input-output pairs. [NOT USED RIGHT NOW]

    #     Parameters
    #     ----------
    #     io_pairs : list[(str, str)]
    #         A list of input-output pairs to score.

    #     Returns
    #     -------
    #     list[float]
    #         A list of label probabilities.
    #     """

    #     out = np.zeros(len(topical_io_pairs))

    #     to_embed = []
    #     topics = {}
    #     for i,(topic,input,output) in enumerate(topical_io_pairs):
    #         if topic not in topics:
    #             topics[topic] = []
    #         to_embed.append(input)
    #         to_embed.append(output)
    #         topics[topic].append((i, len(to_embed) - 2, len(to_embed) - 1))
    #     embeddings = adaptive_testing.embed(to_embed)
    #     features = [None for i in range(len(topical_io_pairs))]
    #     for topic in topics:
    #         features = []
    #         for i,ind1,ind2 in topics[topic]:
    #             features.append(np.hstack([embeddings[ind1], embeddings[ind2]]))
    #         features = np.vstack(features)

    #         label = np.array([v == "pass" for v in self.topic_model(topic)(features)], dtype=np.float32)
    #         for i, (j,_,_) in enumerate(topics[topic]):
    #             out[j] = label[i]

    #     return np.array(out)

    def drop_topic(self, topic):
        """Remove a topic from the test tree."""
        self._tests = self._tests.loc[self._tests["topic"] != topic]


class TestTreeLocIndexer:
    def __init__(self, test_tree):
        self.test_tree = test_tree

    def __repr__(self):
        return "TestTreeLocIndexer is an intermediate object for operating on TestTrees. Slice this object further to yield useful results."

    def __getitem__(self, key):
        # If all columns haven't changed, it's still a valid test tree
        # If columns have been dropped, return a Pandas object

        subset = self.test_tree._tests.loc[key]
        if (
            hasattr(subset, "columns")
            and len(set(["topic", "input", "output", "label"]) - set(subset.columns)) == 0
        ):
            test_tree_slice = TestTree(subset, index=subset.index, ensure_topic_markers=False)
            test_tree_slice._tests_location = self.test_tree._tests_location
            return test_tree_slice
        else:
            return subset

    def __setitem__(self, key, value):
        self.test_tree._tests.loc[key] = value


class TestTreeILocIndexer:
    def __init__(self, test_tree):
        self.test_tree = test_tree

    def __repr__(self):
        return "TestTreeILocIndexer is an intermediate object for operating on TestTrees. Slice this object further to yield useful results."

    def __getitem__(self, key):
        # If all columns haven't changed, it's still a valid test tree
        # If columns have been dropped, return a Pandas object

        subset = self.test_tree._tests.iloc[key]
        if (
            hasattr(subset, "columns")
            and len(set(["topic", "input", "output", "label"]) - set(subset.columns)) == 0
        ):
            test_tree_slice = TestTree(subset, ensure_topic_markers=False)
            test_tree_slice._tests_location = self.test_tree._tests_location
            return test_tree_slice
        else:
            return subset

    def __setitem__(self, key, value):
        self.test_tree._tests.iloc[key] = value
