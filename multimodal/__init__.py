"""Multimodal roots: documents, free text and voice -> Profile (see multimodal/README.md)."""


def extract(*args, **kwargs):
    from .extract.profile import extract as _extract
    return _extract(*args, **kwargs)
