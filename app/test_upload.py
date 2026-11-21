"""Run with python -m unittest app.test_upload (app requirements plus httpx)."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app import server


class PhoneUploadTest(unittest.TestCase):
    def test_preview_and_pipeline_share_display_coordinates(self):
        # Bright patch at raw top-left. Mirroring and rotation move it to known corners.
        raw = Image.new("RGB", (64, 32))
        raw.paste("white", (0, 0, 16, 16))
        expected_corners = ["TL", "TR", "BR", "BL", "TL", "TR", "BR", "BL"]
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, "UPLOADS", Path(tmp)), \
                patch.object(server, "IMAGES", {}), patch.object(server, "LIVE", False), \
                patch.object(server, "REPLAY", False), TestClient(server.app) as client:
            for tag, corner in enumerate(expected_corners, 1):
                with self.subTest(orientation=tag):
                    exif = Image.Exif()
                    exif[274] = tag
                    jpeg = io.BytesIO()
                    raw.save(jpeg, format="JPEG", exif=exif)
                    response = client.post("/api/images", files={"file": ("photo.jpg", jpeg.getvalue())})
                    response.raise_for_status()
                    meta = response.json()
                    size = raw.size if tag < 5 else raw.size[::-1]
                    self.assertEqual((meta["width"], meta["height"]), size)
                    preview = client.get(meta["url"])
                    preview.raise_for_status()
                    with Image.open(io.BytesIO(preview.content)) as im:
                        self.assertIn(im.getexif().get(274), (1, None))
                        self.assertEqual(im.size, size)
                        for y, vertical in [(4, "T"), (im.height - 5, "B")]:
                            for x, horizontal in [(4, "L"), (im.width - 5, "R")]:
                                self.assertEqual(im.getpixel((x, y))[0] > 128, vertical + horizontal == corner)
                        with patch.object(server.pipeline, "answer", return_value={"answer": "ok"}) as answer:
                            client.post("/api/ask", json={"image_id": meta["image_id"], "question": "Where?"}).raise_for_status()
                            seen = answer.call_args.args[0]
                            self.assertEqual(seen.size, im.size)
                            self.assertEqual(seen.tobytes(), im.convert("RGB").tobytes())
