import soundcard as sc


def default_output_id() -> str:
    return sc.default_speaker().id


def list_outputs() -> list[tuple[str, str, bool]]:
    default = default_output_id()
    return [(s.id, s.name, s.id == default) for s in sc.all_speakers()]
