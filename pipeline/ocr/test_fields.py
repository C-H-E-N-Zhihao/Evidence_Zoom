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
