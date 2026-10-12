import math
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from shorts_generator.local.clipper import _cut_subclip, crop_clip_local


class TestRenderProfilingAndOptimization(unittest.TestCase):
    def test_cut_subclip_uses_fast_input_seeking(self):
        """Verify that _cut_subclip places -ss and -t before -i to enable O(1) demuxer seek."""
        executed_cmds = []

        def mock_run_ffmpeg(cmd, job_ctx=None):
            executed_cmds.append(list(cmd))

        with patch("shorts_generator.local.clipper._run_ffmpeg_cmd", side_effect=mock_run_ffmpeg):
            out = _cut_subclip(
                source_path="source.mp4",
                start=2290.0,
                end=2305.0,
                out_path="cut.mp4",
            )
            self.assertEqual(out, "cut.mp4")
            self.assertEqual(len(executed_cmds), 2)
            cmd = executed_cmds[0]

            # Find positions of flags
            ss_idx = cmd.index("-ss")
            t_idx = cmd.index("-t")
            i_idx = cmd.index("-i")

            # Crucial requirement: -ss and -t MUST appear before -i for fast demuxer input seeking
            self.assertLess(ss_idx, i_idx, "Expected -ss to appear before -i for fast input seeking")
            self.assertLess(t_idx, i_idx, "Expected -t to appear before -i")
            self.assertEqual(cmd[ss_idx + 1], "2290.000")
            self.assertEqual(cmd[t_idx + 1], "15.000")
            self.assertIn("-avoid_negative_ts", cmd)
            self.assertEqual(cmd[cmd.index("-avoid_negative_ts") + 1], "make_zero")

    def test_crop_clip_local_emits_timing_metrics(self):
        """Verify that crop_clip_local logs stage timing metrics via job_ctx."""
        mock_job_ctx = MagicMock()
        mock_job_ctx.emit_log = MagicMock()

        # Mock out internal heavy subprocesses for fast unit test
        with patch("shorts_generator.local.clipper._probe_media_duration", return_value=100.0), \
             patch("shorts_generator.local.clipper._cut_subclip", return_value="out.cut.mp4"), \
             patch("shorts_generator.local.clipper._reframe_vertical", return_value="out.mp4"):

            crop_clip_local(
                source_path="mock_source.mp4",
                start_time=10.0,
                end_time=20.0,
                aspect_ratio="9:16",
                out_path="out.mp4",
                segments=[{"start": 10.0, "end": 15.0, "text": "TEST SEGMENT"}],
                burn_subtitles=True,
                job_ctx=mock_job_ctx,
            )

        # Verify that emit_log was called with stage timing information
        log_calls = [c[0][0] for c in mock_job_ctx.emit_log.call_args_list]
        timing_logs = [m for m in log_calls if "[clip/local] Stage timing:" in m]
        self.assertTrue(len(timing_logs) > 0, f"Expected Stage timing log, found: {log_calls}")
        metric_str = timing_logs[0]
        self.assertIn("sub=", metric_str)
        self.assertIn("cut=", metric_str)
        self.assertIn("reframe=", metric_str)
        self.assertIn("total=", metric_str)


if __name__ == "__main__":
    unittest.main()
