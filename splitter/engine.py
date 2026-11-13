import threading
from typing import Callable

from splitter.buffer import DeviceBuffer

SAMPLERATE = 48000
CHANNELS = 2
BLOCK = 480


def volume_to_gain(percent: int) -> float:
    return (percent / 100) ** 2


class Engine:
    def __init__(self, source, targets: dict, on_drop: Callable[[str, str], None] = lambda id, err: None):
        if not targets:
            raise ValueError("Tick at least one device.")
        self._source = source
        self._targets = targets
        self._on_drop = on_drop
        self._bufs = {i: DeviceBuffer() for i in targets}
        self._gains = {i: 1.0 for i in targets}
        self._dropped = {i: False for i in targets}
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self):
        self._threads = [threading.Thread(target=self._capture, daemon=True)]
        self._threads += [
            threading.Thread(target=self._play, args=(i,), daemon=True) for i in self._targets
        ]
        for t in self._threads:
            t.start()

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)

    def set_volume(self, device_id: str, percent: int):
        self._gains[device_id] = volume_to_gain(percent)

    def stats(self) -> dict[str, tuple[int, int, bool]]:
        return {
            i: (b.underruns, b.overruns, self._dropped[i]) for i, b in self._bufs.items()
        }

    def _capture(self):
        try:
            with self._source.recorder(SAMPLERATE, CHANNELS, BLOCK * 8) as rec:
                while not self._stop.is_set():
                    data = rec.record(BLOCK)
                    for i, buf in self._bufs.items():
                        if not self._dropped[i]:
                            buf.push(data)
        except Exception as err:
            self._stop.set()
            self._on_drop("__source__", str(err))

    def _play(self, device_id: str):
        buf = self._bufs[device_id]
        try:
            with self._targets[device_id].player(SAMPLERATE, CHANNELS, BLOCK * 8) as player:
                while not self._stop.is_set():
                    player.play(buf.pull(BLOCK) * self._gains[device_id])
        except Exception as err:
            self._dropped[device_id] = True
            self._on_drop(device_id, str(err))
