import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from smart_price.core.common_utils import safe_json_parse


def test_safe_json_parse_ellipsis():
    assert safe_json_parse("...") is None

