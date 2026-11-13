# Digital Audio Splitter

Copies whatever your PC plays on its default output device to extra output devices at the same time, for example a USB headset and a Bluetooth headset. Each extra device has its own volume slider and its own live counts of audio glitches (underruns and overruns).

## How to use

1. Run `DigitalAudioSplitter.exe` (or `python main.py`).
2. Your default Windows output device keeps playing as normal. Its volume stays on Windows' own volume control.
3. Tick the extra devices you want, then press Start.
4. Use each device's slider to set its volume.

## Known limitation

Bluetooth devices play a little later than wired or default devices. Syncing them is not handled in this version.

## Build from source

Needs Windows and Python. Create the `.venv` with the requirements and PyInstaller installed, then run `build.bat`. The program appears at `dist\DigitalAudioSplitter.exe`.

## Listening checklist

1. Play music on the default device. Tick the USB headset and the Bluetooth headset. Press Start. All three play.
2. Move each slider: only that headset changes volume.
3. Leave it running for 30+ minutes. Afterwards, there is no growing delay, and the overrun/underrun counts stay low. Pausing the music adds about 1 underrun per pause, which is expected.
4. Turn off one headset mid-play: its row shows "dropped" and the other keeps playing.
5. Change the Windows default output device: the app stops with the message.
