import unittest

from pipeline.ocr import locate


class PolicyNumberTest(unittest.TestCase):
    def test_uncertain_suffix_prevents_partial_answer(self):
        spans = [
            dict(text="Vehicle A", box=[.05, .1, .14, .13], confidence=1),
            dict(text="Vehicle B", box=[.55, .1, .64, .13], confidence=1),
            dict(text="Policy no.:", box=[.05, .2, .14, .23], confidence=1),
            dict(text="HM-7731", box=[.18, .2, .27, .23], confidence=.99),
        ]
        self.assertEqual(locate(spans, "policy", "a"), spans[-1])
        spans.append(dict(text="-0042", box=[.28, .2, .33, .23], confidence=.65))
        self.assertIsNone(locate(spans, "policy", "a"))

    def test_slanted_rows_keep_original_evidence(self):
        for slope in (-.09, .09):
            with self.subTest(slope=slope):
                def span(text, x, y, width):
                    shift = slope * (x + width / 2)
                    return dict(text=text, box=[x, y + shift, x + width, y + shift + .012], confidence=1)
                expected = span("AB-1234", .24, .20, .09)
                spans = [span("Vehicle A", .05, .1, .1), span("Vehicle B", .55, .1, .1),
                         span("Policy no.", .05, .20, .08), expected,
                         span("unrelated", .24, .22, .09)]
                self.assertIs(locate(spans, "policy", "a"), expected)
