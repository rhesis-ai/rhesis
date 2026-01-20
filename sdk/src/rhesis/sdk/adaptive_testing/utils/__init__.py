import io
import re
import urllib

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


_images_cache = {}


def get_image(url):
    if url not in _images_cache:
        try:
            _images_cache[url] = _download_image(url)
        except urllib.error.URLError:
            _images_cache[url] = get_image(
                "https://upload.wikimedia.org/wikipedia/commons/d/d1/Image_not_available.png"
            )

    return _images_cache[url]


def _download_image(url):
    import PIL

    urllib_request = urllib.request.Request(
        url,
        data=None,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0"
        },
    )
    with urllib.request.urlopen(urllib_request, timeout=10) as r:
        img_stream = io.BytesIO(r.read())
    return PIL.Image.open(img_stream)


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
