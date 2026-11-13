import threading

import numpy as np


class DeviceBuffer:
    """FIFO of audio frames with drift correction by +/-1 frame per pull."""

    def __init__(self, target=1920, tolerance=480, capacity=9600, channels=2):
        self.target, self.tolerance, self.capacity, self.channels = target, tolerance, capacity, channels
        self._data = np.zeros((0, channels), np.float32)
        self._primed = False
        self._lock = threading.Lock()
        self.underruns = 0
        self.overruns = 0

    @property
    def fill(self):
        return len(self._data)

    def push(self, block):
        with self._lock:
            self._data = np.concatenate((self._data, block))
            if self.fill > self.capacity:
                self._data = self._data[-self.capacity:]
                self.overruns += 1
            if self.fill >= self.target:
                self._primed = True

    def pull(self, n):
        with self._lock:
            out = np.zeros((n, self.channels), np.float32)
            if not self._primed:
                return out
            fill = self.fill
            if fill < n:
                out[:fill] = self._data
                self._data = self._data[:0]
                self.underruns += 1
                self._primed = False
                return out
            if fill > self.target + self.tolerance and fill > n:
                take = self._data[:n + 1]
                h = n // 2
                out[:h], out[h:] = take[:h], take[h + 1:]  # drop one middle frame
                used = n + 1
            elif fill < self.target - self.tolerance and n > 1:
                out[:n - 1] = self._data[:n - 1]
                out[n - 1] = out[n - 2]  # repeat last frame
                used = n - 1
            else:
                out[:] = self._data[:n]
                used = n
            self._data = self._data[used:]
            return out
