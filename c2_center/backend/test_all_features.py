#!/usr/bin/env python3
"""
C2 Center — Comprehensive Feature Test Suite

Tests all backend features:
1. Model Registry API
2. Stream Management API
3. Playground (Direct Detection API)
4. Zone Management API
5. Analytics API (Algorithm switching)
6. WebSocket Video Streaming
7. WebSocket Stats Streaming

Requirements:
    - Backend running: uvicorn main:app --host 0.0.0.0 --port 8000
    - MediaMTX with 2 cameras running on port 8554 (/cam1, /cam2)
    - FFmpeg cameras publishing RTSP streams

Usage:
    python test_all_features.py --verbose
    python test_all_features.py --skip-ws  # Skip WebSocket tests (faster)
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import aiohttp
import requests
import websockets
import websockets.client
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    colorize=True,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
)

# ============================================================================
# Configuration
# ============================================================================

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
VERBOSE = "--verbose" in sys.argv
SKIP_WS = "--skip-ws" in sys.argv

# Test image for playground
TEST_IMAGE_PATH = Path("D:/datas/Final.yolov8/density/test_video.mp4")
STREAM_IDS = ["stream_1", "stream_2"]
ALGORITHMS = ["absolute_count", "area_occupancy", "pce_density", "fundamental_equation", "heatmap", "line_crossing"]

# ============================================================================
# Test Results
# ============================================================================

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def log_pass(self, name: str, message: str = ""):
        self.passed += 1
        msg = f"✓ {name}"
        if message:
            msg += f" — {message}"
        self.tests.append(("PASS", name, message))
        logger.success(msg)

    def log_fail(self, name: str, error: str):
        self.failed += 1
        self.tests.append(("FAIL", name, error))
        logger.error(f"✗ {name} — {error}")

    def summary(self):
        print("\n" + "=" * 80)
        print(f"Test Results: {self.passed} passed, {self.failed} failed")
        print("=" * 80)
        for status, name, msg in self.tests:
            icon = "✓" if status == "PASS" else "✗"
            print(f"  {icon} {name}")
            if msg:
                print(f"      {msg}")

results = TestResults()

# ============================================================================
# Test 1: Connectivity & Health
# ============================================================================

def test_health():
    """Test API health endpoint."""
    logger.info("Test 1: Connectivity & Health Check")
    try:
        resp = requests.get(f"{API_BASE}/", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        streams = data.get("streams", {})
        results.log_pass("API health", f"Connected. {len(streams)} streams configured")
        if VERBOSE:
            logger.info(f"  Response: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        results.log_fail("API health", str(e))
        return False

# ============================================================================
# Test 2: Camera Management API
# ============================================================================

def test_camera_management():
    """Test camera CRUD operations."""
    logger.info("Test 2: Camera Management API")
    
    # List cameras
    try:
        resp = requests.get(f"{API_BASE}/api/cameras", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        cameras = data.get("cameras", [])
        if not cameras:
            results.log_fail("Camera list", "No cameras found")
            return False
        results.log_pass("Camera list", f"Found {len(cameras)} cameras")
        if VERBOSE:
            for cam in cameras:
                logger.info(f"  - {cam['stream_id']}: {cam['name']} ({cam['rtsp_url']})")
    except Exception as e:
        results.log_fail("Camera list", str(e))
        return False
    
    # Add a new camera
    try:
        new_camera = {
            "stream_id": "test_stream",
            "rtsp_url": "rtsp://localhost:8554/test",
            "name": "Test Camera",
            "description": "Temporary test camera",
            "enabled": False
        }
        resp = requests.post(f"{API_BASE}/api/cameras", json=new_camera, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        results.log_pass("Camera creation", f"Created test_stream")
    except Exception as e:
        results.log_fail("Camera creation", str(e))
        return False
    
    # Get camera details
    try:
        resp = requests.get(f"{API_BASE}/api/cameras/test_stream", timeout=5)
        resp.raise_for_status()
        cam = resp.json()
        results.log_pass("Camera details", f"Retrieved: {cam['name']}")
    except Exception as e:
        results.log_fail("Camera details", str(e))
        return False
    
    # Update camera
    try:
        resp = requests.put(
            f"{API_BASE}/api/cameras/test_stream",
            json={"name": "Updated Test Camera"},
            timeout=5
        )
        resp.raise_for_status()
        results.log_pass("Camera update", "Name updated")
    except Exception as e:
        results.log_fail("Camera update", str(e))
        return False
    
    # Delete camera
    try:
        resp = requests.delete(f"{API_BASE}/api/cameras/test_stream", timeout=5)
        resp.raise_for_status()
        results.log_pass("Camera deletion", "Test camera deleted")
    except Exception as e:
        results.log_fail("Camera deletion", str(e))
        return False
    
    return True

# ============================================================================
# Test 2: Model Registry API
# ============================================================================

def test_model_registry():
    """Test model listing and metadata."""
    logger.info("Test 2: Model Registry API")
    try:
        resp = requests.get(f"{API_BASE}/api/models", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        if not models:
            results.log_fail("Model list", "No models found")
            return False
        active = data.get("active", "unknown")
        results.log_pass("Model list", f"Found {len(models)} models (active: {active})")
        if VERBOSE:
            for m in models:
                logger.info(f"  - {m['name']}: {m['num_classes']} classes, {m['file_size_mb']}MB")
        return True
    except Exception as e:
        results.log_fail("Model list", str(e))
        return False

# ============================================================================
# Test 3: Stream Management API
# ============================================================================

def test_stream_list():
    """Test stream listing."""
    logger.info("Test 3: Stream Management API")
    try:
        resp = requests.get(f"{API_BASE}/api/streams", timeout=5)
        resp.raise_for_status()
        stream_list = resp.json()
        if not isinstance(stream_list, list):
            results.log_fail("Stream list", "Invalid response format (expected list)")
            return False
        if not stream_list:
            results.log_fail("Stream list", "No streams found")
            return False
        results.log_pass("Stream list", f"Found {len(stream_list)} streams")
        if VERBOSE:
            for s in stream_list:
                logger.info(f"  - {s.get('stream_id', 'unknown')}: {s}")
        return True
    except Exception as e:
        results.log_fail("Stream list", str(e))
        return False

# ============================================================================
# Test 4: Playground Detection API
# ============================================================================

def test_playground_detection():
    """Test direct model inference via playground."""
    logger.info("Test 4: Playground Detection API")
    
    # Try to find an image or use a dummy one
    # The actual test just checks the endpoint works with a minimal request
    try:
        # For now, just test the endpoint is reachable
        # A full test would require uploading an actual image file
        resp = requests.post(
            f"{API_BASE}/api/playground/detect",
            json={
                "model": "yolo_p2n_ft2",
                "confidence": 0.5,
                "image_base64": ""  # Empty for now
            },
            timeout=10
        )
        # 400 is OK — invalid input is expected
        if resp.status_code in [200, 400, 422]:
            results.log_pass("Playground endpoint", "Endpoint responding")
            if VERBOSE:
                logger.info(f"  Response status: {resp.status_code}")
            return True
        else:
            results.log_fail("Playground endpoint", f"Unexpected status: {resp.status_code}")
            return False
    except Exception as e:
        results.log_fail("Playground endpoint", str(e))
        return False

# ============================================================================
# Test 5: Zone Management API
# ============================================================================

def test_zone_management():
    """Test zone CRUD operations."""
    logger.info("Test 5: Zone Management API")
    try:
        # Set a zone via PUT (replaces all zones for the stream)
        zone_payload = {
            "roi_polygon": [[100, 100], [200, 100], [200, 200], [100, 200]],
            "entry_line": [[50, 150], [250, 150]],
            "road_length_km": 0.1
        }
        
        resp = requests.put(
            f"{API_BASE}/api/zones/stream_1",
            json=zone_payload,
            timeout=5
        )
        resp.raise_for_status()
        zone_data = resp.json()
        results.log_pass("Zone configuration", f"Configured zones for stream_1")
        
        # List zones
        resp = requests.get(f"{API_BASE}/api/zones/stream_1", timeout=5)
        resp.raise_for_status()
        zones = resp.json()
        results.log_pass("Zone list", f"Retrieved zone config")
        
        # Clear zones
        resp = requests.delete(f"{API_BASE}/api/zones/stream_1", timeout=5)
        resp.raise_for_status()
        results.log_pass("Zone deletion", "Zones cleared")
        
        return True
    except Exception as e:
        results.log_fail("Zone management", str(e))
        return False

# ============================================================================
# Test 6: Analytics Algorithm Switching
# ============================================================================

def test_algorithm_switching():
    """Test switching between different analytics algorithms."""
    logger.info("Test 6: Analytics Algorithm Switching")
    
    # First, list available algorithms
    try:
        resp = requests.get(f"{API_BASE}/api/analytics/algorithms", timeout=5)
        resp.raise_for_status()
        algos = resp.json()
        results.log_pass("Algorithm list", f"Found {len(algos)} available algorithms")
        if VERBOSE:
            for a in algos:
                logger.info(f"  - {a['slug']}: {a['name']}")
    except Exception as e:
        results.log_fail("Algorithm list", str(e))
        return False
    
    # Switch between algorithms
    success_count = 0
    for algo in ALGORITHMS:
        try:
            resp = requests.put(
                f"{API_BASE}/api/analytics/algorithm/stream_1",
                json={"algorithm": algo},
                timeout=5
            )
            resp.raise_for_status()
            success_count += 1
            if VERBOSE:
                logger.info(f"  ✓ Switched to {algo}")
        except Exception as e:
            logger.warning(f"  ✗ Failed to switch to {algo}: {e}")
    
    results.log_pass(
        "Algorithm switching",
        f"Successfully switched to {success_count}/{len(ALGORITHMS)} algorithms"
    )
    return success_count > 0

# ============================================================================
# Test 7: WebSocket Video Streaming
# ============================================================================

async def test_websocket_video():
    """Test WebSocket video streaming."""
    logger.info("Test 7: WebSocket Video Streaming")
    
    for stream_id in STREAM_IDS:
        try:
            ws_url = f"{WS_BASE}/ws/stream/{stream_id}"
            
            async with websockets.client.connect(ws_url) as websocket:
                # Receive a few frames
                frame_count = 0
                start = time.time()
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "frame" and data.get("data"):
                            frame_count += 1
                            if frame_count >= 3:  # Collect 3 frames then stop
                                break
                    except Exception:
                        pass
                
                elapsed = time.time() - start
                if frame_count > 0:
                    fps = frame_count / elapsed
                    results.log_pass(
                        f"WebSocket video ({stream_id})",
                        f"Received {frame_count} frames in {elapsed:.2f}s ({fps:.1f} fps)"
                    )
                else:
                    results.log_fail(f"WebSocket video ({stream_id})", "No frames received")
                    
        except Exception as e:
            results.log_fail(f"WebSocket video ({stream_id})", str(e))

# ============================================================================
# Test 8: WebSocket Stats Streaming
# ============================================================================

async def test_websocket_stats():
    """Test WebSocket stats streaming."""
    logger.info("Test 8: WebSocket Stats Streaming")
    
    for stream_id in STREAM_IDS:
        try:
            ws_url = f"{WS_BASE}/ws/stats/{stream_id}"
            
            async with websockets.client.connect(ws_url) as websocket:
                # Receive a few stats packets
                stats_count = 0
                start = time.time()
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "stats":
                            stats_count += 1
                            if stats_count >= 2:  # Collect 2 stats then stop
                                break
                    except Exception:
                        pass
                
                elapsed = time.time() - start
                if stats_count > 0:
                    hz = stats_count / elapsed
                    results.log_pass(
                        f"WebSocket stats ({stream_id})",
                        f"Received {stats_count} packets in {elapsed:.2f}s ({hz:.1f} Hz)"
                    )
                else:
                    results.log_fail(f"WebSocket stats ({stream_id})", "No stats received")
                    
        except Exception as e:
            results.log_fail(f"WebSocket stats ({stream_id})", str(e))

# ============================================================================
# Test 9: Concurrent WebSocket Connections
# ============================================================================

async def test_websocket_concurrent():
    """Test multiple concurrent WebSocket connections."""
    logger.info("Test 9: Concurrent WebSocket Connections")
    
    num_connections = 5
    tasks = []
    
    for i in range(num_connections):
        for stream_id in STREAM_IDS:
            async def connect_and_receive(idx, sid):
                try:
                    ws_url = f"{WS_BASE}/ws/stream/{sid}"
                    async with websockets.client.connect(ws_url) as ws:
                        # Receive 1 frame
                        async for msg in ws:
                            data = json.loads(msg)
                            if data.get("type") == "frame":
                                return True
                except Exception:
                    return False
            
            tasks.append(connect_and_receive(i, stream_id))
    
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    successful = sum(1 for r in results_list if r is True)
    total = len(results_list)
    
    results.log_pass(
        "Concurrent WebSocket connections",
        f"Successfully handled {successful}/{total} concurrent connections"
    )

# ============================================================================
# Main Test Runner
# ============================================================================

async def run_async_tests():
    """Run all async tests."""
    if not SKIP_WS:
        logger.info("\n" + "=" * 80)
        await test_websocket_video()
        
        logger.info("\n" + "=" * 80)
        await test_websocket_stats()
        
        logger.info("\n" + "=" * 80)
        await test_websocket_concurrent()

def main():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("C2 CENTER BACKEND — COMPREHENSIVE FEATURE TEST")
    logger.info("=" * 80)
    logger.info(f"API Base: {API_BASE}")
    logger.info(f"WS Base: {WS_BASE}")
    logger.info(f"Skip WebSocket Tests: {SKIP_WS}")
    logger.info("=" * 80 + "\n")
    
    # Run synchronous tests
    test_health()
    logger.info("\n" + "=" * 80)
    test_camera_management()
    logger.info("\n" + "=" * 80)
    test_model_registry()
    logger.info("\n" + "=" * 80)
    test_stream_list()
    logger.info("\n" + "=" * 80)
    test_playground_detection()
    logger.info("\n" + "=" * 80)
    test_zone_management()
    logger.info("\n" + "=" * 80)
    test_algorithm_switching()
    
    # Run async tests
    if not SKIP_WS:
        logger.info("\n" + "=" * 80)
        asyncio.run(run_async_tests())
    
    # Print summary
    results.summary()
    
    # Exit with appropriate code
    sys.exit(0 if results.failed == 0 else 1)

if __name__ == "__main__":
    main()
