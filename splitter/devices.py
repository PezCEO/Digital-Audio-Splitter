import warnings

import soundcard as sc


def default_output_id() -> str:
    return sc.default_speaker().id


def list_outputs() -> list[tuple[str, str, bool]]:
    default = default_output_id()
    return [(s.id, s.name, s.id == default) for s in sc.all_speakers()]


def make_source():
    # Loopback emits benign "data discontinuity" warnings; filter is process-wide (catch_warnings isn't thread-safe).
    warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)
    return sc.get_microphone(default_output_id(), include_loopback=True)


def make_target(device_id: str):
    return sc.get_speaker(device_id)
