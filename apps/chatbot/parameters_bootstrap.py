import logging
import os
import sys

from rhesis.sdk import Parameters
from rhesis.sdk.entities import Experiment
from rhesis.sdk.models.parameters import (
    ParameterField,
    ParameterSchema,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CHATBOT_PROJECT = os.getenv("RHESIS_CHATBOT_PROJECT", "chatbot-demo")


def bootstrap_chatbot_parameters():
    """
    Bootstrap the chatbot project's parameter schema and initial baseline experiment.
    """
    logger.info(f"Bootstrapping parameter management for project '{CHATBOT_PROJECT}'...")

    # 1. Define and push the schema (bare defaults thanks to Option A coercion)
    schema = ParameterSchema(
        fields=[
            ParameterField(
                name="system_prompt",
                type="text",
                description="Override the system prompt (blank = use markdown file)",
            ),
            ParameterField(
                name="use_case",
                type="enum",
                default="travel",
                options=["travel", "insurance", "medical", "echo"],
                description="Persona / context to adopt",
            ),
            ParameterField(
                name="model",
                type="string",
                description="LLM provider string (e.g. vertex_ai/gemini-2.0-flash)",
            ),
            ParameterField(
                name="temperature",
                type="number",
                default=0.7,
            ),
            ParameterField(
                name="max_tokens",
                type="integer",
                default=1024,
            ),
            ParameterField(
                name="output_mode",
                type="enum",
                default="text",
                options=["text", "json"],
            ),
            ParameterField(
                name="context_strategy",
                type="enum",
                default="heuristic",
                options=["heuristic", "rag", "none"],
            ),
        ]
    )

    try:
        Parameters.put_schema(CHATBOT_PROJECT, schema)
        logger.info("Schema defined successfully.")
    except Exception as e:
        logger.error(f"Failed to define schema: {e}")
        sys.exit(1)

    # 2. Seed an initial 'baseline' shared experiment (bare values thanks to Option A)
    try:
        Experiment.publish(
            name="baseline",
            project_id=CHATBOT_PROJECT,
            description="Baseline default configuration",
            values={
                "system_prompt": "",
                "use_case": "travel",
                "temperature": 0.7,
                "max_tokens": 1024,
                "output_mode": "text",
                "context_strategy": "heuristic",
            },
            message="Initial baseline commit",
            environment="default",
        )
        logger.info("Baseline experiment created, shared, and promoted to 'default'.")
    except Exception as e:
        logger.error(f"Failed to create baseline experiment: {e}")
        sys.exit(1)

    logger.info("Bootstrap complete!")

if __name__ == "__main__":
    bootstrap_chatbot_parameters()
