import logging
import urllib.parse

import numpy as np

from .embedders import cos_sim
from .utils import is_subtopic

log = logging.getLogger(__name__)


class PromptBuilder:
    """A class to build prompts for the model."""

    def __init__(
        self,
        prompt_size=7,
        slot_randomization=0.25,
        score_randomization=0.05,
        skip_randomization=0.25,
        prompt_diversity=True,
        subtopic_diversity=True,
    ):
        """Initialize the prompt builder.

        Parameters
        ----------
        prompt_size : int
            The number of test slots to include in the prompt.

        slot_randomization : float
            The proportion of slots to make fully random (within the current topic).

        score_randomization : float
            The standard deviation of an additive Gaussian randomization factor for the scores.

        skip_randomization : float
            The proportion of times we skip over top ranking tests when building the prompt.

        prompt_diversity : bool
            Whether to include a diversity term when selecting tests for the prompt.
            This diversity term is based on the embeddings of each test.

        subtopic_diversity : bool
            If true, we will try and pick tests from a diverse set of subtopics
            of the current topic (if we are using subtopic tests and not direct
            child tests).
        """

        assert skip_randomization < 0.99, (
            "skip_randomization must be less than 1, otherwise everything will always be skipped!"
        )

        self.prompt_size = prompt_size
        self.slot_randomization = slot_randomization
        # TODO: make this scale according to the stddev of the top 7 entries?
        self.score_randomization = score_randomization
        self.skip_randomization = skip_randomization
        self.prompt_diversity = prompt_diversity
        self.subtopic_diversity = subtopic_diversity

    def __call__(
        self,
        test_tree,
        topic,
        score_column,
        repetitions=1,
        filter="",
        suggest_topics=False,
        working_set_size=100,
        embeddings=None,
        embed_fn=None,
    ):
        """This builds a prompt for GPT3 that elicits useful input examples.

        Parameters
        ----------
        test_tree : adaptive_testing.TestTree
            The test tree to generate prompts from.

        topic : str
            The topic to build a prompt for.

        score_column : str
            The column to use for scoring the tests.

        repetitions : int
            The number of times to repeat the prompt generation process.
            This is how many prompts we will return.

        filter : str
            A filter to apply to the test set before selecting tests to build the prompt.

        suggest_topics : bool
            If true, we will create a prompt filled with topic names instead of a list of tests.

        working_set_size : int
            How many top tests to consider when doing the full iterative scoring
            process. Larger values may take longer. Note that this has no effect
            as long as we never go more than working_set_size tests deep during
            the prompt item selection process.

        embeddings : dict
            A dictionary of embeddings to use for the prompt.
            This is used to compute the prompt_diversity.
        """

        ids = np.array([node.id for node in test_tree])

        # return early for an empty test tree
        if len(ids) == 0:
            return [[] for _ in range(repetitions)]

        # we compute each test's distance from current topic, where distance is measured
        # by the length of the topic prefix shared between the test and the current topic
        topic_scaling = np.ones(len(test_tree))
        topic_parts = topic.split("/")
        for i in range(1, len(topic_parts)):
            prefix = "/".join(topic_parts[: i + 1])
            if suggest_topics:
                prefix += "/"
            topic_scaling *= 1 + 99 * np.array(
                [node.topic.startswith(prefix) for node in test_tree]
            )

        # promote direct children over subtopic descendants and filter for topics vs tests
        if suggest_topics:
            topic_scaling *= 1 + 99 * np.array(
                [node.topic.rsplit("/", 1)[0] == topic for node in test_tree]
            )
            topic_scaling *= np.array([node.label == "topic_marker" for node in test_tree])
        else:
            topic_scaling *= 1 + 99 * np.array([node.topic == topic for node in test_tree])
            topic_scaling *= np.array([node.label != "topic_marker" for node in test_tree])
        topic_scaling *= np.array(["__suggestions__" not in node.topic for node in test_tree])

        # return early if we have nothing to build a prompt with
        if np.sum(topic_scaling) == 0:
            return [[] for _ in range(repetitions)]

        topic_scaling /= np.max(topic_scaling)

        # filter down to a single test type (chosen to match the top scoring test)
        if suggest_topics:
            # scores currently do not influence topic suggestions
            # TODO: can we score topics and topic suggestions?
            scores = np.ones(len(ids))
        else:
            # compute a positive single value score for each test
            scores = np.array(
                [score_max(test_tree[k].model_score, test_tree[k].label) for k in ids]
            )

        # filter down to just top rows we will use during the iterative scoring process
        rank_vals = scores * topic_scaling
        top_inds = np.argsort(-rank_vals)[:working_set_size]
        ids = ids[top_inds]
        topic_scaling = topic_scaling[top_inds]
        scores = scores[top_inds] * 1.0

        # build a list of randomized prompts
        prompts = []
        for _ in range(repetitions):
            # store tmp versions of things we update during the iteration
            scores_curr = scores.copy()
            topic_scaling_curr = topic_scaling.copy()

            # score randomization
            scores_curr += self.score_randomization * np.random.rand(len(ids))

            # sim_avoidance is a vector that marks which items (and items related
            # through similarities) should be avoided (ranked lower for prompt selection)
            if self.prompt_diversity and embed_fn is not None:
                sim_avoidance = np.zeros(len(ids))
                if suggest_topics:
                    embeddings_arr = np.vstack(
                        embed_fn(
                            [urllib.parse.unquote(test_tree[id].topic.split("/")[-1]) for id in ids]
                        )
                    )
                else:
                    embeddings_arr = np.hstack(
                        [
                            np.vstack(embed_fn([test_tree[id].input for id in ids])),
                            np.vstack(embed_fn([test_tree[id].output for id in ids])),
                        ]
                    )
                similarities = cos_sim(embeddings_arr, embeddings_arr)
            elif self.prompt_diversity:
                sim_avoidance = np.zeros(len(ids))
                similarities = np.eye(len(ids))  # No embedder, skip similarity
            hard_avoidance = np.zeros(len(ids))
            diversity = np.ones(len(ids))

            # compute how many greedy and how many random positions we will have
            num_random = max(
                0,
                min(
                    np.random.binomial(self.prompt_size, self.slot_randomization),
                    len(ids) - self.prompt_size,
                ),
            )
            num_greedy = max(0, min(self.prompt_size - num_random, len(ids) - num_random))

            # iteratively select prompt items
            prompt_ids = []
            outside_topics_used = np.ones(len(ids))
            while len(prompt_ids) < num_greedy + num_random:
                # once we get to the random part of the process we scramble the scores
                if len(prompt_ids) == num_greedy:
                    scores_curr = 1 + np.random.rand(len(ids)) * 0.1

                # find the next bext index
                if self.prompt_diversity:
                    diversity = 1 - (similarities * sim_avoidance).max(1)
                rank_vals = (
                    scores_curr
                    * topic_scaling_curr
                    * diversity
                    * (1 - hard_avoidance)
                    * outside_topics_used
                )

                if (
                    np.nanmax(rank_vals) <= 0 and len(prompt_ids) > 0
                ):  # stop if we have run out of the current subtree
                    break

                new_ind = np.nanargmax(rank_vals)
                skip_rand = np.random.rand()

                # make it unlikely we will choose the same outside topic twice
                new_ind_topic = test_tree[ids[new_ind]].topic
                if not is_subtopic(topic, new_ind_topic):
                    outside_topics_used *= 1 - 0.9 * np.array(
                        [test_tree[id].topic == new_ind_topic for id in ids]
                    )

                # add or skip this item
                if skip_rand >= self.skip_randomization:
                    prompt_ids.append(ids[new_ind])
                    avoidance_level = 1
                else:
                    avoidance_level = 1 - 0.1

                # avoid this IO pair as we select the next pairs
                hard_avoidance[new_ind] = avoidance_level
                if self.prompt_diversity:
                    sim_avoidance[new_ind] = avoidance_level

                # lower the weight of the subtopic we just picked from
                if self.subtopic_diversity:
                    new_topic = test_tree[ids[new_ind]].topic
                    if topic != new_topic and is_subtopic(topic, new_topic):
                        subtopic = topic + "/" + new_topic[(len(topic) + 1) :].split("/")[0]
                        subtopic_scaling = np.array(
                            [0.001 if is_subtopic(subtopic, test_tree[k].topic) else 1 for k in ids]
                        )
                        topic_scaling_curr *= subtopic_scaling

            # create the prompt as a list of tuples
            prompt = []
            for k in reversed(prompt_ids):
                node = test_tree[k]
                if suggest_topics:
                    if node.topic == "":
                        continue  # we can't use the root to help suggest topic names
                    parents, child = node.topic.rsplit("/", 1)
                    prompt.append((k, parents, urllib.parse.unquote(child)))
                else:
                    prompt.append((k, node.topic, node.input))
            prompts.append(prompt)

        return prompts


def score_max(s, label):
    if s == "" or s is None:
        return 1 if label == "fail" else 0
    elif isinstance(s, str):
        return np.max([convert_float(v) for v in s.split("|")])
    elif np.isnan(s):
        return 1 if label == "fail" else 0
    else:
        return np.max(s)


def convert_float(s):
    try:
        f = float(s)
    except ValueError:
        f = np.nan
    return f
