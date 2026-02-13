import re

import numpy as np


def parse_test_type(test_type):
    part_names = ["text1", "value1", "text2", "value2", "text3", "value3", "text4"]
    parts = re.split(r"(\{\}|\[\])", test_type)
    part_values = ["" for _ in range(7)]
    for i, part in enumerate(parts):
        part_values[i] = part
    return {name: value for name, value in zip(part_names, part_values)}


# https://codereview.stackexchange.com/questions/253198/improved-isinstance-for-ipython
def isinstance_ipython(obj, ref_class):
    def _class_name(obj):
        name = getattr(obj, "__qualname__", getattr(obj, "__name__", ""))
        return (getattr(obj, "__module__", "") + "." + name).lstrip(".")

    return isinstance(obj, ref_class) or _class_name(type(obj)) == _class_name(ref_class)


def is_subtopic(topic, candidate):
    # Returns true if candidate is a subtopic of topic
    # Both arguments are strings, which look like UNIX paths
    # Return is boolean
    # return True if re.search(r"^%s(/|$)" % re.escape(topic), candidate) else False
    if len(topic) == len(candidate):
        return topic == candidate
    else:
        return candidate.startswith(topic) and candidate[len(topic)] == "/"


def convert_float(s):
    try:
        f = float(s)
    except ValueError:
        f = np.nan
    return f
