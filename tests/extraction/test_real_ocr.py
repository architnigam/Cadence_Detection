"""Opt-in real engine smoke tests; no client data or network involved."""
from pathlib import Path
import os
import sys
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"src"))
from cadence_detection.extraction.ocr import default_ocr
from cadence_detection.extraction.images import open_image
from PIL import Image, ImageDraw, ImageFont


@unittest.skipUnless(os.environ.get("CADENCE_TEST_REAL_OCR") == "1", "Set CADENCE_TEST_REAL_OCR=1 with a local engine/model")
class RealOCRTests(unittest.TestCase):
    def test_real_local_engine_reads_synthetic_text(self):
        engine = default_ocr(); self.assertIsNotNone(engine)
        image = Image.new("RGB", (1100, 220), "white")
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 42) if os.name == "nt" else ImageFont.truetype("DejaVuSans.ttf", 42)
        ImageDraw.Draw(image).text((25, 50), "Synthetic Contact 12345", fill="black", font=font)
        try:
            lines = engine.recognize(image)
            self.assertIn("Synthetic Contact 12345", " ".join(line.text for line in lines))
            self.assertTrue(all(0 <= line.confidence <= 100 for line in lines))
            # Reuse the same worker, exercising sparse OCR and request isolation.
            second = engine.recognize(image, sparse=True)
            self.assertIn("12345", " ".join(line.text for line in second))
        finally:
            engine.close()

    def test_local_svg_converter(self):
        image = open_image(b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="white"/><text x="5" y="30">Test</text></svg>', ".svg", 40_000_000)
        self.assertAlmostEqual(image.width/image.height, 2, delta=0.05)

    @unittest.skipUnless(os.name == "nt", "Windows metafile renderer required")
    def test_supplied_metafiles_local_conversion(self):
        source = Path(__file__).resolve().parents[2]/"data/source/Cadence_TPRM_Training.docx"
        if not source.exists():
            self.skipTest("Local supporting material not present")
        with zipfile.ZipFile(source) as package:
            names = [n for n in package.namelist() if n.endswith(".emf")]
            self.assertEqual(len(names), 5)
            for name in names:
                with self.subTest(asset=name):
                    image = open_image(package.read(name), ".emf", 40_000_000)
                    self.assertGreater(image.width, 0); self.assertGreater(image.height, 0)


if __name__ == "__main__":
    unittest.main()
