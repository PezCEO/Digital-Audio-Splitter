import numpy as np

from splitter.buffer import DeviceBuffer


def ramp(n, start=0):
    return np.repeat(np.arange(start, start + n, dtype=np.float32)[:, None], 2, axis=1)


def test_not_primed_returns_silence():
    b = DeviceBuffer()
    b.push(ramp(1000))
    out = b.pull(480)
    assert out.shape == (480, 2) and not out.any()
    assert b.fill == 1000


def test_primed_passthrough():
    b = DeviceBuffer()
    b.push(ramp(1920))
    out = b.pull(480)
    assert np.array_equal(out, ramp(480))
    assert b.fill == 1440


def test_starvation_counts_once():
    b = DeviceBuffer()
    b.push(ramp(1920))
    while b.underruns == 0:
        b.pull(480)
    for _ in range(5):
        assert b.pull(480).shape == (480, 2)
    assert b.underruns == 1


def test_overrun_drops_oldest():
    b = DeviceBuffer()
    b.push(ramp(9600))
    b.push(ramp(480, 9600))
    assert b.fill == 9600 and b.overruns == 1
    assert b.pull(480)[0, 0] == 480


def test_drift_fast_consumer_bounded():
    b = DeviceBuffer()
    for _ in range(10000):
        b.push(ramp(480))
        assert b.pull(481).shape == (481, 2)
        assert b.fill <= 9600


def test_drift_slow_consumer_bounded():
    b = DeviceBuffer()
    for i in range(10000):
        b.push(ramp(481))
        assert b.pull(480).shape == (480, 2)
        if i >= 200:
            assert b.fill <= 1920 + 480 + 481
    assert b.overruns == 0
