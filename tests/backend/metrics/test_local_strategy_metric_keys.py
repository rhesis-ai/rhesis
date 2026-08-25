"""_generate_unique_metric_keys assigns suffixes in a stable order (name,
class_name, id) rather than the caller's iteration order, so the same
metric gets the same key across runs -- see the verdict matrix's cell
alignment in app/services/test_run.py, which depends on this.
"""

from rhesis.backend.metrics.strategies.local import LocalStrategy
from rhesis.sdk.metrics import MetricConfig


def _config(name: str, class_name: str, metric_id: str) -> MetricConfig:
    return MetricConfig(name=name, class_name=class_name, id=metric_id)


def _tasks(configs):
    # (class_name, metric, metric_config, backend) -- only metric_config is
    # read by _generate_unique_metric_keys.
    return [(c.class_name, None, c, "rhesis") for c in configs]


class TestUniqueMetricKeyDeterminism:
    def test_duplicate_names_get_the_same_suffix_regardless_of_input_order(self):
        strategy = LocalStrategy()
        a = _config("Accuracy", "AccuracyMetric", "11111111-1111-1111-1111-111111111111")
        b = _config("Accuracy", "AccuracyMetric", "22222222-2222-2222-2222-222222222222")

        keys_forward, _ = strategy._generate_unique_metric_keys(_tasks([a, b]))
        keys_reversed, _ = strategy._generate_unique_metric_keys(_tasks([b, a]))

        # The lower id ("111...") always gets the bare key, the higher id
        # always gets the suffix -- independent of which came first in the
        # input list.
        assert dict(zip([a.id, b.id], keys_forward)) == {a.id: "Accuracy", b.id: "Accuracy_1"}
        assert dict(zip([b.id, a.id], keys_reversed)) == {a.id: "Accuracy", b.id: "Accuracy_1"}

    def test_keys_align_positionally_with_input_tasks(self):
        strategy = LocalStrategy()
        a = _config("Accuracy", "AccuracyMetric", "1")
        b = _config("Toxicity", "ToxicityMetric", "2")
        c = _config("Accuracy", "AccuracyMetric", "3")

        keys, results = strategy._generate_unique_metric_keys(_tasks([a, b, c]))

        assert len(keys) == 3
        assert keys[1] == "Toxicity"
        assert {keys[0], keys[2]} == {"Accuracy", "Accuracy_1"}
        assert set(results.keys()) == set(keys)

    def test_falls_back_to_class_name_when_no_metric_name(self):
        strategy = LocalStrategy()
        a = MetricConfig(name=None, class_name="CustomMetric", id="1")

        keys, _ = strategy._generate_unique_metric_keys(_tasks([a]))

        assert keys == ["CustomMetric"]
