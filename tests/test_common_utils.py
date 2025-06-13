import sys

from smart_price.core.common_utils import safe_json_parse


def test_safe_json_parse_ellipsis():
    assert safe_json_parse("...") is None

