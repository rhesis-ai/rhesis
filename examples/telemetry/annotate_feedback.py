"""
End-User Feedback as Annotations

An instrumented app answers a question and hands the OTEL trace id back with the
answer. When the user later gives a thumbs-down, the app records it as an
annotation on that trace. A fail annotation overrides the trace's automated
verdict and shows up in the Rhesis UI wherever annotations do.

No LLM SDK is needed; the answer is simulated.

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY and RHESIS_PROJECT_ID

Run with:
    cd examples/telemetry
    uv run annotate_feedback.py

The annotated trace appears in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

import time
from pathlib import Path

from dotenv import load_dotenv
from opentelemetry import trace
from rhesis.telemetry.schemas import AIOperationType

from rhesis.sdk import RhesisAPIError, RhesisClient, observe
from rhesis.sdk.telemetry import annotate_trace

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RhesisClient.from_environment()

# Spans are exported in batches and ingested asynchronously, so a trace can take
# a few seconds to become annotatable.
RETRY_ATTEMPTS = 6
RETRY_DELAY_SECONDS = 5


@observe(span_name=AIOperationType.AGENT_INVOKE)
def answer_question(question: str) -> tuple[str, str]:
    """Answer a question and return the answer with the trace id that recorded it."""
    trace_id = format(trace.get_current_span().get_span_context().trace_id, "032x")
    time.sleep(0.2)
    answer = "Refunds are available within 90 days of purchase."
    return answer, trace_id


def record_feedback(trace_id: str, thumbs_up: bool, comment: str) -> None:
    """Turn a thumbs-up or thumbs-down into an annotation on the trace."""
    verdict = "pass" if thumbs_up else "fail"
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            annotation = annotate_trace(trace_id, verdict, comment)
            print(f"📝 Recorded '{verdict}' as annotation {annotation.id}")
            return
        except RhesisAPIError as error:
            if error.status_code != 404 or attempt == RETRY_ATTEMPTS:
                raise
            print(f"⏳ Trace not ingested yet, retrying in {RETRY_DELAY_SECONDS}s...")
            time.sleep(RETRY_DELAY_SECONDS)


def main() -> None:
    question = "How long do I have to return a product?"
    answer, trace_id = answer_question(question)
    print(f"❓ {question}\n💬 {answer}\n🔗 Trace id: {trace_id}")

    # In a real app this arrives later, from the user, carrying the trace id the
    # app sent along with the answer.
    record_feedback(trace_id, thumbs_up=False, comment="The policy is 30 days, not 90.")

    print("📊 View the trace and its annotation: http://localhost:3000/traces")


if __name__ == "__main__":
    main()
