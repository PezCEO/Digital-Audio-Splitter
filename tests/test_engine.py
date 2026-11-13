import threading
import time
from contextlib import contextmanager

import numpy as np
import pytest

from splitter.engine import Engine, volume_to_gain


class FakeSource:
    @contextmanager
    def recorder(self, samplerate, channels, blocksize):
        class R:
            def record(self, n):
                time.sleep(0.01)
                return np.ones((n, 2), dtype=np.float32)
        yield R()


class FakeTarget:
    def __init__(self, fail_after=None):
        self.blocks = []
        self.fail_after = fail_after

    @contextmanager
    def player(self, samplerate, channels, blocksize):
        outer = self

        class P:
            def play(self, data):
                if outer.fail_after is not None and len(outer.blocks) >= outer.fail_after:
                    raise RuntimeError("boom")
                outer.blocks.append(data.copy())
                time.sleep(0.01)
        yield P()


def test_volume_to_gain():
    assert volume_to_gain(0) == 0.0
    assert volume_to_gain(50) == 0.25
    assert volume_to_gain(100) == 1.0


def test_engine_requires_targets():
    with pytest.raises(ValueError):
        Engine(FakeSource(), {})


def test_audio_reaches_all_targets_with_volume():
    a, b = FakeTarget(), FakeTarget()
    e = Engine(FakeSource(), {"a": a, "b": b})
    e.set_volume("b", 50)
    e.start()
    time.sleep(0.3)
    e.stop()
    peaks = [max(blk.max() for blk in t.blocks) for t in (a, b)]
    assert peaks[0] == pytest.approx(1.0) and peaks[1] == pytest.approx(0.25)


def test_failing_target_dropped_others_continue():
    bad, good = FakeTarget(fail_after=3), FakeTarget()
    drops = []
    e = Engine(FakeSource(), {"bad": bad, "good": good}, on_drop=lambda i, m: drops.append(i))
    e.start()
    time.sleep(0.3)
    n = len(good.blocks)
    time.sleep(0.1)
    e.stop()
    assert e.stats()["bad"][2] is True
    assert drops == ["bad"]
    assert len(good.blocks) > n


def test_stop_returns_promptly():
    e = Engine(FakeSource(), {"a": FakeTarget()})
    e.start()
    t0 = time.time()
    e.stop()
    assert time.time() - t0 < 1.5
    assert not any(t.is_alive() for t in e._threads)
