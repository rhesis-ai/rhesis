"""A set of generators for Adaptive Testing."""

import urllib
from typing import Optional

import numpy as np
from profanity import profanity

from rhesis.sdk import adaptive_testing
from rhesis.sdk.models import get_model

from .embedders import cos_sim


class Generator:
    """Abstract class for generators."""

    def __init__(self, source):
        """Create a new generator from a given source."""
        self.source = source

    def __call__(self, prompts, topic, topic_description, mode, num_samples, max_length):
        """Generate a set of prompts for a given topic."""
        raise NotImplementedError()

    def _validate_prompts(self, prompts):
        """Ensure the passed prompts are a list of prompt lists."""
        if len(prompts[0]) > 0 and isinstance(prompts[0][0], str):
            prompts = [prompts]

        # Split apart prompt IDs and prompts
        prompt_ids, trimmed_prompts = [], []
        for prompt in prompts:
            prompt_without_id = []
            for entry in prompt:
                prompt_ids.append(entry[0])
                prompt_without_id.append(entry[1:])
            trimmed_prompts.append(prompt_without_id)

        return trimmed_prompts, prompt_ids


class TextCompletionGenerator(Generator):
    """Abstract class for generators."""

    def __init__(self, source, sep, subsep, quote, filter):
        """Create a new generator with the given separators and max length."""
        super().__init__(source)
        self.sep = sep
        self.subsep = subsep
        self.quote = quote
        self.filter = filter

    def __call__(self, prompts, topic, topic_description, max_length=None):
        """This should be overridden by concrete subclasses.

        Parameters:
        -----------
        prompts: list of tuples, or list of lists of tuples
        """
        pass

    def _varying_values(self, prompts, topic):
        """Marks which values vary in the set of prompts."""
        show_topics = False
        for prompt in prompts:
            topics, inputs = zip(*prompt)
            show_topics = show_topics or len(set(list(topics) + [topic])) > 1
        return show_topics

    def _create_prompt_strings(self, prompts, topic, content_type):
        """Convert prompts that are lists of tuples into strings for the LM to complete."""

        assert content_type in ["tests", "topics"], "Invalid mode: {}".format(content_type)

        show_topics = self._varying_values(prompts, topic) or content_type == "topic"

        prompt_strings = []
        for prompt in prompts:
            prompt_string = ""
            for p_topic, input in prompt:
                if show_topics:
                    if content_type == "tests":
                        prompt_string += self.sep + p_topic + ":" + self.sep + self.quote
                    elif content_type == "topics":
                        prompt_string += (
                            "A subtopic of "
                            + self.quote
                            + p_topic
                            + self.quote
                            + " is "
                            + self.quote
                        )

                prompt_string += input
                prompt_string += self.sep
            if show_topics:
                if content_type == "tests":
                    prompt_strings.append(
                        prompt_string + self.sep + topic + ":" + self.sep + self.quote
                    )
                elif content_type == "topics":
                    prompt_strings.append(
                        prompt_string
                        + "A subtopic of "
                        + self.quote
                        + topic
                        + self.quote
                        + " is "
                        + self.quote
                    )
            else:
                prompt_strings.append(prompt_string + self.quote)
        return prompt_strings

    def _parse_suggestion_texts(self, suggestion_texts, prompts):
        """Parse the suggestion texts into a list of unique suggestions."""
        assert len(suggestion_texts) % len(prompts) == 0, "Missing prompt completions!"

        samples = []
        for suggestion_text in suggestion_texts:
            if callable(self.filter):
                suggestion_text = self.filter(suggestion_text)
            samples.append(suggestion_text)
        return list(set(samples))


class OpenAI(TextCompletionGenerator):
    """Backend wrapper for the OpenAI API that exposes GPT-3."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        sep: str = "\n",
        subsep: str = " ",
        quote: str = '"',
        temperature: float = 2.0,
        top_p: float = 0.95,
        filter=profanity.censor,
    ):
        super().__init__(model, sep, subsep, quote, filter)
        self.gen_type = "model"
        self.api_key = api_key
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        # Initialize the model using get_model
        self._model = get_model("openai", model_name=model, api_key=api_key)

    def __call__(self, prompts, topic, topic_description, mode, num_samples=1, max_length=100):
        if len(prompts[0]) == 0:
            raise ValueError(
                "ValueError: Unable to generate suggestions from completely empty "
                "TestTree. Consider writing a few manual tests before generating suggestions."
            )

        prompts, prompt_ids = self._validate_prompts(prompts)

        # create prompts to generate the model input parameters of the tests
        prompt_strings = self._create_prompt_strings(prompts, topic, mode)

        # Use different instructions based on whether we're generating tests or topics
        if mode == "topics":
            chat_instruction_beginning = "You are given examples of subtopics for a parent topic:\n"
            chat_instruction_end = """
Generate exactly ONE new subtopic name. Return only the subtopic name with no other text.
Do not put the subtopic in quotes. Do not include explanations or multiple options.
Just output a single short subtopic name.
"""
        else:
            chat_instruction_beginning = "You are given examples of test inputs for a topic:\n"
            chat_instruction_end = """
Generate exactly ONE new test input that fits this topic. Output only the test input text itself.
Do not include quotes, topic names, prefixes, or any other formatting - just the raw test input.
"""
        # Remove trailing quote that was meant for completion API
        prompt_strings = [
            chat_instruction_beginning + prompt_string.rstrip(self.quote) + chat_instruction_end
            for prompt_string in prompt_strings
        ]

        # Use model.generate_batch to get suggestions
        suggestion_texts = self._model.generate_batch(
            prompts=prompt_strings,
            n=num_samples,
            temperature=self.temperature,
            top_p=self.top_p,
        )

        return self._parse_suggestion_texts(suggestion_texts, prompts)


class TestTreeSource(Generator):
    def __init__(self, test_tree, assistant_generator=None):
        # TODO: initialize with test tree
        super().__init__(test_tree)
        self.gen_type = "test_tree"
        self.assistant_generator = assistant_generator

    def __call__(
        self,
        prompts,
        topic,
        topic_description,
        test_type=None,
        num_samples=1,
        max_length=100,
    ):
        if len(prompts) == 0:
            # Randomly return instances without any prompts to go off of. TODO: Consider better alternatives like max-failure?
            return self.source.iloc[
                np.random.choice(
                    self.source.shape[0], size=min(50, self.source.shape[0]), replace=False
                )
            ]

        prompts, prompt_ids = self._validate_prompts(prompts)

        # TODO: Currently only returns valid subtopics. Update to include similar topics based on embedding distance?
        if test_type == "topics":
            proposals = []
            for id, test in self.source.iterrows():
                # check if requested topic is *direct* parent of test topic
                if (
                    test.label == "topic_marker"
                    and topic == test.topic[0 : test.topic.rfind("/")]
                    and test.topic != ""
                ):
                    proposals.append(urllib.parse.unquote(test.topic.rsplit("/", 2)[1]))
            return proposals

        # Find tests closest to the proposals in the embedding space
        # TODO: Hallicunate extra samples if len(prompts) is insufficient for good embedding calculations.
        # TODO: Handle case when suggestion_threads>1 better than just selecting the first set of prompts as we do here
        topic_embeddings = np.vstack(
            [adaptive_testing._embedding_cache[input] for topic, input in prompts[0]]
        )
        data_embeddings = np.vstack(
            [adaptive_testing._embedding_cache[input] for input in self.source["input"]]
        )

        max_suggestions = min(num_samples * len(prompts), len(data_embeddings))
        method = "distance_to_avg"
        if method == "avg_distance":
            dist = cos_sim(topic_embeddings, data_embeddings)
            closest_indices = np.argpartition(dist.mean(axis=0), -max_suggestions)[
                -max_suggestions:
            ]

        elif method == "distance_to_avg":
            avg_topic_embedding = topic_embeddings.mean(axis=0)

            distance = cos_sim(avg_topic_embedding, data_embeddings)
            closest_indices = np.argpartition(distance, -max_suggestions)[-max_suggestions:]

        output = self.source.iloc[np.array(closest_indices).squeeze()].copy()
        output["topic"] = topic
        return output
