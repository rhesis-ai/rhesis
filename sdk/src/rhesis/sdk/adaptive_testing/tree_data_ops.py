from rhesis.sdk.adaptive_testing.schemas import TestTreeData

nan = float("nan")


def remove_scores(test_tree_data: TestTreeData) -> TestTreeData:
    """Remove all scores from the test tree data."""
    for node in test_tree_data:
        node.model_score = nan
    return test_tree_data


def set_evaluation_status(test_tree_data: TestTreeData, evaluation_status: bool) -> TestTreeData:
    """Set the evaluation status for all nodes in the test tree data."""
    for node in test_tree_data:
        node.to_eval = evaluation_status
    return test_tree_data


def return_eval_ids(test_tree_data: TestTreeData) -> list[str]:
    """Return the ids of the nodes that need to be evaluated."""
    return [node.id for node in test_tree_data if node.to_eval]
