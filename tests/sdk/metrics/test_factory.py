"""MetricFactory imports only the provider a metric comes from."""

import subprocess
import sys

_CREATE_NATIVE = """
import sys
from rhesis.sdk.metrics.factory import MetricFactory
try:
    MetricFactory.create("rhesis", "NumericJudge", name="x", evaluation_prompt="p")
except Exception:
    pass  # No model configured; only the imports matter here.
print(sorted(m for m in ("deepeval", "garak") if m in sys.modules))
"""


def test_a_native_metric_does_not_import_deepeval_or_garak():
    # A fresh interpreter: other tests in this process may have imported them already.
    out = subprocess.run(
        [sys.executable, "-c", _CREATE_NATIVE], capture_output=True, text=True, check=True
    )

    assert out.stdout.strip().splitlines()[-1] == "[]"
