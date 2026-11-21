import json
import os
import subprocess
import unittest
from unittest.mock import patch

from PIL import Image
from pipeline.ocr import recognize_page


class PageReuseTest(unittest.TestCase):
    def test_changed_pixels_retry_and_cold_mode(self):
        image = Image.new("RGB", (13, 11))
        ok = subprocess.CompletedProcess([], 0, json.dumps([]).encode())
        with patch.dict(os.environ, EVIDENCE_OCR_BIN="test-reuse", EVIDENCE_OCR_CACHE="1"), patch(
            "pipeline.ocr.subprocess.run", side_effect=[OSError("busy"), ok, ok, ok]
        ) as helper:
            with self.assertRaises(OSError):
                recognize_page(image)
            self.assertFalse(recognize_page(image)[1])
            self.assertTrue(recognize_page(image.copy())[1])
            image.putpixel((2, 3), (1, 2, 3))
            self.assertFalse(recognize_page(image)[1])
            with patch.dict(os.environ, EVIDENCE_OCR_CACHE="0"):
                self.assertFalse(recognize_page(image)[1])
            self.assertEqual(helper.call_count, 4)
