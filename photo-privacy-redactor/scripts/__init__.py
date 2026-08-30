"""Programmatic interface for photo privacy redaction."""

from .photo_privacy_redactor import detect_face_candidates, redact_photo

__all__ = ["detect_face_candidates", "redact_photo"]

