import pytest
from splitter.devices import default_output_id, list_outputs


def test_list_outputs_marks_exactly_one_default():
    result = list_outputs()
    if not result:
        pytest.skip("no output devices")
    assert sum(d[2] for d in result) == 1
    assert default_output_id() == next(d[0] for d in result if d[2])
