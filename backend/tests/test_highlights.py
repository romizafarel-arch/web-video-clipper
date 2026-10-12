import json
import unittest
from unittest.mock import MagicMock

from shorts_generator.highlights import (
    chunk_transcript,
    get_highlights,
    dedupe_highlights,
    _sanitize_highlights,
)


class TestHighlightsChunking(unittest.TestCase):
    def test_chunk_transcript_creates_relative_timestamps(self):
        # Create a synthetic transcript of 2500 seconds
        segments = []
        for t in range(0, 2500, 10):
            segments.append({
                "start": float(t),
                "end": float(t + 8),
                "text": f"Segment speaking at second {t}",
            })
        transcript = {"duration": 2500.0, "segments": segments}

        chunks = chunk_transcript(transcript)
        self.assertGreater(len(chunks), 1, "Should split 2500s video into multiple chunks")

        # Check Chunk 1
        chunk1 = chunks[0]
        self.assertEqual(chunk1["_offset"], 0.0)
        self.assertAlmostEqual(chunk1["segments"][0]["start"], 0.0)

        # Check Chunk 2
        chunk2 = chunks[1]
        self.assertGreater(chunk2["_offset"], 0.0)
        # All segment starts in chunk2 MUST be relative (>= 0 and < duration)
        first_seg_start = chunk2["segments"][0]["start"]
        self.assertGreaterEqual(first_seg_start, 0.0)
        self.assertLess(first_seg_start, 60.0)  # Near 0 due to overlap

        # Verify that relative segment times can be mapped back to absolute times
        for seg in chunk2["segments"]:
            abs_start = seg["start"] + chunk2["_offset"]
            self.assertGreaterEqual(abs_start, 1100.0)

    def test_get_highlights_long_video_offset_applied_once(self):
        # Video of 2500 seconds
        segments = []
        for t in range(0, 2500, 10):
            segments.append({
                "start": float(t),
                "end": float(t + 8),
                "text": f"Speaker content at {t} seconds",
            })
        transcript = {"duration": 2500.0, "segments": segments}

        # Mock LLM that returns a highlight in each chunk
        def mock_llm(prompt: str) -> str:
            if "content_type" in prompt:
                return json.dumps({"content_type": "podcast", "density": "high"})
            # Return highlight between 100s and 150s within the chunk
            return json.dumps({
                "highlights": [
                    {
                        "title": "Viral Moment",
                        "start_time": 100.0,
                        "end_time": 150.0,
                        "score": 92,
                        "hook_sentence": "Amazing hook line",
                        "virality_reason": "High retention peak",
                    }
                ]
            })

        result = get_highlights(transcript, num_clips=5, llm_fn=mock_llm)
        highlights = result["highlights"]
        self.assertTrue(len(highlights) >= 2, "Should have highlights from multiple chunks")

        # Chunk 1 highlight should be around 100.0 - 150.0
        # Chunk 2 highlight should be offset by 1140 (100 + 1140 = 1240.0)
        # Neither should be clamped to 1200 or double-offset!
        start_times = [h["start_time"] for h in highlights]
        self.assertIn(100.0, start_times)
        self.assertIn(1240.0, start_times)


if __name__ == "__main__":
    unittest.main()
