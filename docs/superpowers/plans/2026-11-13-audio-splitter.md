# Digital Audio Splitter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Windows window app that copies the system audio mix from the default output device to extra ticked output devices, each with its own live volume, shipped as one `.exe`.

**Architecture:** One capture thread records WASAPI loopback from the default speaker in 10 ms blocks and pushes each block into a per-device `DeviceBuffer`. One playback thread per target device pulls from its buffer. The buffer corrects clock drift by dropping or duplicating a single frame per block, and pads silence on underrun. Then the thread applies volume and plays. A tkinter window drives `Engine` and polls its stats.

**Tech Stack:** Python 3.12, `soundcard` (WASAPI capture/playback), `numpy`, `tkinter` (stdlib), `pytest`, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-11-13-audio-splitter-design.md`

## Global Constraints

- Windows 10/11, WASAPI shared mode. No drivers, no admin rights.
- The default output device is never a target: it already plays, so ticking it would double the audio.
- One independent volume per extra device, live while running. Checkboxes and Refresh are locked while running.
- A failing device is dropped and reported. The other devices keep playing and the app does not crash.
- If the Windows default output changes while running: stop and show the message "Default output device changed — press Start again."
- Each running device shows live underrun and overrun counts.
- Ships as a single `.exe` (`--onefile --windowed`) that runs without Python installed.
- Fixed audio format everywhere: `SAMPLERATE = 48000`, `CHANNELS = 2`, `BLOCK = 480` frames (10 ms), float32. WASAPI shared mode converts to each device's own format.

## Review Focus

1. **Silence or paused music.** WASAPI loopback stops delivering data during silence, so the buffers starve. Expect silence to be output, no crash, and only one underrun counted per starvation episode, not one per block. Tested in Task 2 (`test_starvation_counts_once`).
2. **Sustained clock drift.** A target that plays slightly faster or slower than capture must keep latency bounded, with no growing delay. Tested in Task 2 (`test_drift_fast_consumer_bounded`, `test_drift_slow_consumer_bounded`).
3. **A device unplugged or out of range mid-play.** `play()` raises an exception. That device must be marked dropped and the others must keep playing. Tested in Task 3 (`test_failing_target_dropped_others_continue`).
4. **Start with zero devices ticked.** Start must do nothing and show "Tick at least one device." Tested in Task 4 (manual check step), with the guard in `Engine.__init__` tested in Task 3 (`test_engine_requires_targets`).
5. **Stop pressed while threads are blocked in `record()` or `play()`.** Stop must return within about 1 s, and the app must close cleanly. Tested in Task 3 (`test_stop_returns_promptly`).

---

### Task 1: Project setup and device listing

**Files:**
- Create: `requirements.txt`, `.gitignore`, `splitter/__init__.py`, `splitter/devices.py`, `tests/test_devices.py`

**Interfaces:**
- Produces: `list_outputs() -> list[tuple[str, str, bool]]` (each item is `(device_id, name, is_default)`), in `splitter/devices.py`. Also `default_output_id() -> str`.

- [ ] **Step 1:** `git init`. `.gitignore`: `.venv/`, `build/`, `dist/`, `*.spec`, `__pycache__/`. `requirements.txt`: `soundcard`, `numpy`, `pytest`, `pyinstaller`.
- [ ] **Step 2:** `python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt`. Expected: installs without errors.
- [ ] **Step 3: Write the test.** `test_list_outputs_marks_exactly_one_default`: call `list_outputs()` on the real machine and assert `sum(d[2] for d in result) == 1`, and that `default_output_id()` equals the id of that entry. Skip with `pytest.skip` if `list_outputs()` returns an empty list.
- [ ] **Step 4:** Run `.venv/Scripts/python -m pytest tests/test_devices.py -v`. Expected: FAIL (module missing).
- [ ] **Step 5:** Implement both functions with `soundcard.all_speakers()` and `soundcard.default_speaker()`, comparing by `.id`.
- [ ] **Step 6:** Run the test again. Expected: PASS.
- [ ] **Step 7: Loopback smoke check.** Run a throwaway snippet in the shell, not in the repo: `soundcard.get_microphone(default_output_id(), include_loopback=True).recorder(48000, 2, 480)` records 1 s while something plays. Assert that `abs(data).max() > 0`. Also open `.player(48000, 2, 480)` on every non-default output and play 0.2 s of silence, to confirm that WASAPI accepts the fixed format on each device. Report the result. If it fails, stop and report: the stack choice depends on it.
- [ ] **Step 8:** Commit: `feat: project setup and output device listing`.

### Task 2: DeviceBuffer (drift, underrun, overrun)

**Files:**
- Create: `splitter/buffer.py`, `tests/test_buffer.py`

**Interfaces:**
- Produces: `class DeviceBuffer(target=1920, tolerance=480, capacity=9600, channels=2)`, all sizes in frames. Methods:
  - `push(block: np.ndarray) -> None` (shape `(n, channels)`, float32). Appends the block. If the fill level would exceed `capacity`, it drops the oldest frames and increments `overruns` once per push.
  - `pull(n: int) -> np.ndarray` always returns shape `(n, channels)`:
    - Not primed (fill has not yet reached `target` since creation or since the last starvation): returns zeros and consumes nothing.
    - Primed, and fill < n: returns the available frames padded with zeros, increments `underruns` **once**, and becomes unprimed.
    - fill > target + tolerance: consumes `n+1` frames and deletes one frame from the middle.
    - fill < target − tolerance: consumes `n−1` frames and duplicates the last frame.
    - Otherwise: consumes exactly `n` frames.
  - Attributes: `underruns: int`, `overruns: int`, `fill: int` (property).
- Thread safety: one `threading.Lock` around `push` and `pull`.

- [ ] **Step 1: Write the tests.**
  - `test_not_primed_returns_silence`: push 1000 frames, then `pull(480)` returns all zeros and `fill == 1000`.
  - `test_primed_passthrough`: push 1920 frames of ramp data, then `pull(480)` equals the first 480 frames and `fill == 1440`.
  - `test_starvation_counts_once`: prime, then pull until starved, then pull 5 more times. `underruns == 1`, and every result has shape `(480, 2)`.
  - `test_overrun_drops_oldest`: push 9600 frames, then 480 more. `fill == 9600`, `overruns == 1`, and the oldest 480 frames are gone (check the first pulled sample value).
  - `test_drift_fast_consumer_bounded`: loop 10,000 times, pushing 480 and pulling 481 each time (re-push after a starvation). Assert `fill <= 9600` throughout.
  - `test_drift_slow_consumer_bounded`: loop 10,000 times, pushing 481 and pulling 480 each time. Assert `fill <= target + tolerance + 481` after the first 200 iterations, and `overruns == 0`.
- [ ] **Step 2:** Run `.venv/Scripts/python -m pytest tests/test_buffer.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `DeviceBuffer` in `splitter/buffer.py`. A preallocated numpy array or a `collections.deque` of blocks are both fine.
- [ ] **Step 4:** Run the tests. Expected: all PASS.
- [ ] **Step 5:** Commit: `feat: drift-correcting device buffer`.

### Task 3: Engine (capture and playback threads)

**Files:**
- Create: `splitter/engine.py`, `tests/test_engine.py`

**Interfaces:**
- Consumes: `DeviceBuffer` (Task 2).
- Produces: `class Engine(source, targets: dict[str, object], on_drop: Callable[[str, str], None] = lambda id, err: None)`.
  - `source` has `.recorder(samplerate, channels, blocksize)`, a context manager whose `.record(numframes)` returns an `(n, 2)` array, matching the `soundcard` microphone API.
  - Each target has `.player(samplerate, channels, blocksize)`, a context manager with `.play(data)`, matching the `soundcard` speaker API.
  - The constructor raises `ValueError("Tick at least one device.")` if `targets` is empty.
  - Methods: `start()`, `stop()` (sets an Event, joins all threads with `timeout=1.0`), `set_volume(device_id: str, percent: int)`, and `stats() -> dict[str, tuple[int, int, bool]]` (`(underruns, overruns, dropped)`).
  - Gain: `gain = (percent / 100) ** 2`. This mapping is a pure function `volume_to_gain(percent: int) -> float`, also exported. Default volume is 100.
  - If an exception occurs in a target's thread, the engine marks that device dropped, calls `on_drop(id, str(err))`, and that thread exits. If an exception occurs in the capture thread, it calls `on_drop("__source__", str(err))` and stops everything.
  - All threads are daemon threads.
  - Build the real objects for the app in `splitter/devices.py`: `make_source() -> soundcard microphone (loopback of default)` and `make_target(device_id) -> soundcard speaker`. Add both to Task 1's module.

- [ ] **Step 1: Write the tests** with fakes. `FakeSource.record` returns ones and sleeps 10 ms. `FakeTarget.play` appends to a list, and can be told to raise after k calls.
  - `test_volume_to_gain`: `0 -> 0.0`, `50 -> 0.25`, `100 -> 1.0`.
  - `test_engine_requires_targets`: `Engine(FakeSource(), {})` raises `ValueError`.
  - `test_audio_reaches_all_targets_with_volume`: two targets, one with `set_volume(id, 50)`. Run for 0.3 s. Each target has received nonzero blocks, and the max sample is ≈1.0 on one target and ≈0.25 on the other.
  - `test_failing_target_dropped_others_continue`: one target raises after 3 plays. After 0.3 s, `stats()[bad][2] is True`, `on_drop` was called once for it, and the good target's play count keeps rising.
  - `test_stop_returns_promptly`: `start()`, then `stop()` completes in under 1.5 s, and no engine thread is still alive.
- [ ] **Step 2:** Run `.venv/Scripts/python -m pytest tests/test_engine.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `Engine` and `volume_to_gain` in `splitter/engine.py`, plus `make_source`/`make_target` in `splitter/devices.py`.
- [ ] **Step 4:** Run the full test suite: `.venv/Scripts/python -m pytest -v`. Expected: all PASS.
- [ ] **Step 5:** Commit: `feat: capture/playback engine`.

### Task 4: Window (tkinter)

**Files:**
- Create: `splitter/app.py`, `main.py` (calls `splitter.app.run()`)

**Interfaces:**
- Consumes: `list_outputs`, `default_output_id`, `make_source`, `make_target` (Task 1/3), and `Engine` (Task 3).
- Produces: `run() -> None`.

Layout: one row per output device: checkbox, name, a 0–100 slider (default 100), and a status label. The default device's row shows "(default — plays normally)" with its checkbox and slider disabled. Below the rows: Refresh and Start/Stop buttons. Window title: "Digital Audio Splitter".

Behaviour:
- Start: build `Engine(make_source(), {id: make_target(id) for ticked})`. A `ValueError` shows its message in a `messagebox`. While running, disable the checkboxes and Refresh, and label the button "Stop".
- Refresh (only while stopped): re-run `list_outputs()` and rebuild the rows, keeping the ticks and volumes of devices that are still present.
- A slider move calls `engine.set_volume` live.
- Every 500 ms (`after`), while running, set each status label to `"underruns {u} · overruns {o}"`, or `"dropped"`. Also check `default_output_id()`: if it differs from the one captured at Start, stop and show "Default output device changed — press Start again."
- `on_drop` comes from a worker thread, so it only stores the event. The UI picks it up on the 500 ms tick.
- Closing the window calls `engine.stop()` first.

- [ ] **Step 1:** Implement `splitter/app.py` and `main.py`.
- [ ] **Step 2:** Run `.venv/Scripts/python main.py`. Expected: the window lists the outputs and the default row is disabled. Press Start with nothing ticked: you get the "Tick at least one device." dialog. Tick one device and press Start: the button reads "Stop", the checkboxes are disabled, and the status labels update. Press Stop: the controls re-enable. Close the window: the process exits. Report what was observed. The implementer can check UI state but cannot hear audio.
- [ ] **Step 3:** Run the full test suite. Expected: all PASS.
- [ ] **Step 4:** Commit: `feat: main window`.

### Task 5: Packaging and user checklist

**Files:**
- Create: `build.bat`, `README.md`

- [ ] **Step 1:** In `build.bat`: `.venv\Scripts\pyinstaller --onefile --windowed --name DigitalAudioSplitter main.py`.
- [ ] **Step 2:** Run it. Expected: `dist/DigitalAudioSplitter.exe` exists. Launch it from a plain shell, with the venv not activated. The window opens and lists the devices (checks the `soundcard` cffi bundling). If it fails to import, add `--collect-all soundcard` and rebuild.
- [ ] **Step 3:** `README.md` covers what the tool does, how to build it, and this **listening checklist** for the user:
  1. Play music on the default device. Tick the USB headset and the Bluetooth headset. Press Start. All three play.
  2. Move each slider: only that headset changes volume.
  3. Leave it running for 30+ minutes. Afterwards, there is no growing delay, and the overrun/underrun counts stay low. Pausing the music adds about 1 underrun per pause, which is expected.
  4. Turn off one headset mid-play: its row shows "dropped" and the other keeps playing.
  5. Change the Windows default output device: the app stops with the message.
- [ ] **Step 4:** Commit: `chore: packaging and README`.
