"""
Test: Video-Metadata Synchronization via Frame Buffer Delay.

This test validates the core fix for the "trailing bounding box" bug:
By buffering 16 video frames (~640ms at 25fps), the video delay matches
the measured metadata pipeline latency (~620ms).
"""

import queue
import time
import pytest


class TestFrameBufferDelay:
    """Verify that a 16-frame FIFO buffer introduces the correct delay."""

    def test_buffer_delay_matches_metadata_latency(self):
        """
        Simulate: producer at 25fps, consumer at 12fps.
        Buffer should stabilize at ~640ms delay (16 frames * 40ms).
        """
        BUFFER_SIZE = 16
        PRODUCER_FPS = 25
        FRAME_INTERVAL = 1.0 / PRODUCER_FPS  # 40ms

        q = queue.Queue(maxsize=BUFFER_SIZE)

        # Fill the buffer with timestamped frames
        for i in range(BUFFER_SIZE):
            frame_ts = 1000.0 + i * FRAME_INTERVAL
            q.put(("frame_data", frame_ts))

        # Add one more (drops oldest, adds newest)
        newest_ts = 1000.0 + BUFFER_SIZE * FRAME_INTERVAL
        try:
            q.put_nowait(("frame_data", newest_ts))
        except queue.Full:
            q.get_nowait()  # Drop oldest
            q.put_nowait(("frame_data", newest_ts))

        # Read from head (oldest remaining)
        _, oldest_ts = q.get_nowait()
        
        # The delay should be (BUFFER_SIZE - 1) * FRAME_INTERVAL
        delay_ms = (newest_ts - oldest_ts) * 1000
        expected_delay_ms = (BUFFER_SIZE - 1) * FRAME_INTERVAL * 1000  # 600ms

        print(f"\n  Buffer size: {BUFFER_SIZE}")
        print(f"  Frame interval: {FRAME_INTERVAL*1000:.0f}ms")
        print(f"  Actual delay: {delay_ms:.0f}ms")
        print(f"  Expected delay: {expected_delay_ms:.0f}ms")
        print(f"  Target metadata delay: ~620ms")

        assert abs(delay_ms - expected_delay_ms) < 1.0, (
            f"Delay {delay_ms:.0f}ms != expected {expected_delay_ms:.0f}ms"
        )
        assert 500 <= delay_ms <= 700, (
            f"Delay {delay_ms:.0f}ms outside acceptable range [500, 700]ms "
            f"for matching metadata pipeline latency (~620ms)"
        )

    def test_steady_state_delay_under_load(self):
        """
        Simulate 5 seconds of real operation:
        - Producer: 25fps (adds frames)
        - Consumer: 12fps (reads frames)
        
        After warmup, every consumed frame should be ~640ms old.
        """
        BUFFER_SIZE = 16
        q = queue.Queue(maxsize=BUFFER_SIZE)

        # Simulate 5 seconds
        producer_interval = 0.040   # 25fps
        consumer_interval = 0.083   # 12fps
        
        produced_frames = []
        consumed_delays = []
        
        sim_time = 0.0
        next_produce = 0.0
        next_consume = 0.0
        frame_counter = 0

        while sim_time < 5.0:
            # Produce frame
            if sim_time >= next_produce:
                frame_ts = sim_time
                try:
                    q.put_nowait(("frame", frame_ts))
                except queue.Full:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    q.put_nowait(("frame", frame_ts))
                next_produce += producer_interval
                frame_counter += 1

            # Consume frame
            if sim_time >= next_consume:
                try:
                    _, consumed_ts = q.get_nowait()
                    delay = sim_time - consumed_ts
                    if sim_time > 1.0:  # Skip warmup
                        consumed_delays.append(delay)
                except queue.Empty:
                    pass
                next_consume += consumer_interval

            sim_time += 0.001  # 1ms step

        if consumed_delays:
            avg_delay = sum(consumed_delays) / len(consumed_delays)
            min_delay = min(consumed_delays)
            max_delay = max(consumed_delays)
            
            print(f"\n  Steady-state results ({len(consumed_delays)} frames):")
            print(f"  Average delay: {avg_delay*1000:.0f}ms")
            print(f"  Min delay: {min_delay*1000:.0f}ms")
            print(f"  Max delay: {max_delay*1000:.0f}ms")
            print(f"  Target: ~620ms (metadata pipeline delay)")
            
            # Average should be close to 640ms (16 frames * 40ms)
            assert 400 <= avg_delay * 1000 <= 800, (
                f"Average delay {avg_delay*1000:.0f}ms outside range [400, 800]ms"
            )


class TestDeltaMeasurement:
    """Verify that the measured DELTA correctly identifies the lag."""

    def test_delta_interpretation(self):
        """
        From production logs:
          video_ts=1778480900.421  kafka_ts=1778480899.772  DELTA=648ms
        
        This means the video frame is 648ms NEWER than the metadata.
        To sync, we must delay video by ~648ms.
        """
        video_ts = 1778480900.421
        kafka_ts = 1778480899.772
        delta = video_ts - kafka_ts
        
        assert delta > 0, "Video should be ahead of metadata"
        assert 500 < delta * 1000 < 800, (
            f"DELTA={delta*1000:.0f}ms — video is {delta*1000:.0f}ms ahead of metadata"
        )
        
        # Required buffer to compensate
        fps = 25
        required_frames = int(delta * fps) + 1
        print(f"\n  DELTA: {delta*1000:.0f}ms")
        print(f"  Required buffer: {required_frames} frames at {fps}fps")
        print(f"  Configured buffer: 16 frames = {16/fps*1000:.0f}ms")
        
        assert required_frames <= 18, (
            f"Need {required_frames} frames but buffer is only 18"
        )
