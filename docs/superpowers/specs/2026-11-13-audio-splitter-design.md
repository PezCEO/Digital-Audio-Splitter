# Digital Audio Splitter — Design (v1)

## Intent

A small Windows desktop tool that lets several people listen to whatever the PC is playing at the same time, each on their own headphones (Bluetooth or wired). Windows only sends audio to one output device at a time. This tool removes that limit without making anyone install drivers or learn mixing software such as VoiceMeeter.

## How it works

- The user's **default output device keeps playing as normal**. The tool captures the system mix from that device (WASAPI loopback) and plays a copy on every **extra** device the user has ticked.
- Each extra device has its **own volume slider** in the app. The default device's volume stays on the Windows volume control (accepted trade-off: no virtual audio driver is needed).

## Goals (v1)

- A plain window, opened when needed and closed when done.
- Lists all active output devices. Each one has a checkbox and a volume slider (0–100%). The current default device is marked and cannot be ticked, because it already plays.
- A Start/Stop button. While running, the user can move a volume slider and the change takes effect live.
- If a device disappears mid-session (for example a Bluetooth headset goes out of range), the app drops it, shows that it was dropped, and the other devices keep playing.
- A Refresh button re-reads the device list (devices that were plugged in or paired later).
- Ships as a single `.exe` that runs on Windows 10/11 without Python installed.

## Non-goals (v1)

- Keeping devices in sync, or a delay setting per device. The user explicitly deferred this. Bluetooth will lag the wired jack by roughly 150–250 ms.
- System tray, start with Windows, or remembering the selection between runs.
- Built-in music player, per-app capture, microphone input, or effects/EQ.
- Installer, auto-update, or code signing.

## Anti-goals (a failure even if it technically works)

- Audio on the extra devices gets more and more delayed, or crackles regularly, during a long session. Each device runs on its own clock, so the builder **must** handle drift and buffer under/overrun (for example: keep a small bounded buffer per device and drop or pad samples to stay within it).
- One device failing stops audio on the others, or crashes the app.
- The default device gets a doubled or echoed copy of the audio.
- Requires installing a driver or admin rights.

## Constraints

- Windows 10/11, WASAPI shared mode.
- Devices can differ in sample rate and channel count. Resample/convert so that each device plays correctly.
- Python 3.12 is on the dev machine and .NET is not. Builder's call (below): Python.

## Decided

- Source = system audio loopback from the default output device; targets = the other ticked devices.
- One independent volume per extra device.
- Plain window, no tray.

## Left to the builder (Claude's calls, overridable)

- **Stack:** Python 3.12 + `tkinter` (stdlib) for the UI. Pick an audio library that supports WASAPI loopback capture and playback to a named device, such as `soundcard` or `PyAudioWPatch`. Package with PyInstaller (`--onefile --windowed`).
- **Threading:** one capture thread fans out to one playback thread per device, each with its own bounded queue. The UI never blocks on audio.
- **If the Windows default device changes while the app is running:** stop and show a message asking the user to press Start again. This is acceptable for v1.
- **While running, checkboxes and Refresh are locked;** only volume is live. To add or remove a device, press Stop, change the selection, then press Start.
- **Diagnostics:** next to each running device, show a small live count of underruns and overruns (or dropped/padded samples). Agents can't hear audio, so this count is how the user, and the builder, can objectively confirm "no growing delay or crackles".
- **Hardware testing is done by the user.** The plan ends with a short listening checklist for them to run.
- Layout and styling: functional and readable, nothing fancy.
- Tests: a unit test for the pure logic (volume scaling, drift buffer policy, format conversion). The audio I/O itself is verified by hand on real devices.

## Target hardware

The main setup: a USB headset with its own USB Bluetooth dongle (it shows up in Windows as a USB audio device), plus a Bluetooth headset on a separate generic Bluetooth adapter. Each wireless link has its own radio, so Bluetooth bandwidth isn't a concern for the software. The user handles hardware limits, so no feasibility spike is needed.

## Done looks like

On the user's PC: Spotify plays on the default device, two other headsets are ticked, Start is pressed, all three play, each extra headset's slider changes only that headset, and after 30+ minutes there are no growing delay or crackles.
