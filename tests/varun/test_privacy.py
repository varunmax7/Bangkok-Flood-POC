"""Tests for cctv/archiver/privacy.py (face/plate blur). See docs/VARUN_IMPLEMENTATION.md §6 T20."""
import numpy as np
from PIL import Image

from cctv.archiver import privacy


class _FakeDetector:
    """Stand-in for cv2.CascadeClassifier: its detectMultiScale is a C-level
    attribute on the real object (read-only), so tests swap the whole
    module-level _face/_plate reference for one of these instead of trying
    to monkeypatch an attribute onto the real cv2 object."""

    def __init__(self, boxes=()):
        self._boxes = list(boxes)

    def detectMultiScale(self, *args, **kwargs):
        return self._boxes


def test_blur_sensitive_preserves_size_and_mode():
    img = Image.new("RGB", (200, 150), (120, 80, 40))
    out = privacy.blur_sensitive(img)
    assert out.size == img.size
    assert out.mode == "RGB"


def test_blur_sensitive_no_detections_leaves_pixels_untouched(monkeypatch):
    img = Image.new("RGB", (100, 100), (30, 60, 90))
    monkeypatch.setattr(privacy, "_face", _FakeDetector([]))
    monkeypatch.setattr(privacy, "_plate", _FakeDetector([]))
    out = np.asarray(privacy.blur_sensitive(img))
    assert np.array_equal(out, np.asarray(img))


def test_blur_sensitive_blurs_only_the_detected_region(monkeypatch):
    arr = np.full((150, 200, 3), 10, dtype=np.uint8)
    arr[50:90, 50:90] = 0
    arr[60:80, 60:80] = 255  # a sharp-edged "face" patch to blur
    img = Image.fromarray(arr)

    # force exactly one detection at that patch, none from the plate detector
    monkeypatch.setattr(privacy, "_face", _FakeDetector([(50, 50, 40, 40)]))
    monkeypatch.setattr(privacy, "_plate", _FakeDetector([]))

    out = np.asarray(privacy.blur_sensitive(img))

    # inside the detected box: blurred away the sharp edge (lower variance than before)
    before_std = arr[50:90, 50:90].std()
    after_std = out[50:90, 50:90].std()
    assert after_std < before_std

    # outside the box: untouched
    assert np.array_equal(out[0:20, 0:20], arr[0:20, 0:20])


def test_blur_sensitive_applies_both_face_and_plate_detections(monkeypatch):
    arr = np.full((150, 200, 3), 10, dtype=np.uint8)
    # sharp-edged patches (not flat fills) so blurring is actually detectable via std
    arr[10:30, 10:30] = 0
    arr[15:25, 15:25] = 255  # "face"
    arr[100:120, 150:170] = 0
    arr[105:115, 155:165] = 255  # "plate"
    img = Image.fromarray(arr)

    monkeypatch.setattr(privacy, "_face", _FakeDetector([(10, 10, 20, 20)]))
    monkeypatch.setattr(privacy, "_plate", _FakeDetector([(150, 100, 20, 20)]))

    out = np.asarray(privacy.blur_sensitive(img))
    assert out[10:30, 10:30].std() < arr[10:30, 10:30].std()
    assert out[100:120, 150:170].std() < arr[100:120, 150:170].std()
