"""
Live monitoring pipeline composition.

`wire_live_pipeline()` constructs every runtime + infrastructure object
needed for the live RTSP -> Kafka -> Analytics -> WebSocket flow,
wires them together, and returns a `LivePipelineHandle` exposing
`start()` / `stop()` / `add_stream()` / `remove_stream()`.

Other pipelines (replay, playground) are intentionally not implemented yet.
"""

import logging
from dataclasses import dataclass

from app.analytics.registry import AnalyticsRegistry
from app.core.config import settings
from app.infrastructure.database.camera_repository import CameraRepository
from app.infrastructure.database.zone_repository import ZoneRepository
from app.infrastructure.kafka.consumer import KafkaConsumerService
from app.infrastructure.models.registry import ModelRegistry
from app.infrastructure.video.rtsp_reader import RtspVideoReader
from app.runtime.analytics_dispatcher import AnalyticsDispatcher
from app.runtime.pipeline_manager import PipelineManager
from app.runtime.stream_manager import StreamManager
from app.runtime.sync_engine import SyncEngine
from app.ws.streamer import WsStreamer

logger = logging.getLogger(__name__)


@dataclass
class LivePipelineHandle:
    """Bundle of every component constructed for the live pipeline."""

    stream_manager: StreamManager
    pipeline_manager: PipelineManager
    analytics_dispatcher: AnalyticsDispatcher
    sync_engine: SyncEngine
    video_reader: RtspVideoReader
    kafka_consumer: KafkaConsumerService
    model_registry: ModelRegistry
    ws_streamer: WsStreamer
    camera_repo: CameraRepository
    zone_repo: ZoneRepository

    async def start(self) -> None:
        """Bring every subsystem up and replay enabled cameras from the DB."""
        self.video_reader.start()

        try:
            await self.kafka_consumer.start()
        except Exception:
            logger.warning(
                "Metadata source failed to start — running without detection sync"
            )

        self.pipeline_manager.start()

        cameras = self.camera_repo.list_cameras()
        logger.info("Live pipeline replaying %d cameras from DB", len(cameras))
        for cam in cameras:
            if not cam.get("enabled", True):
                continue
            self.add_stream(cam["stream_id"], cam["rtsp_url"])

    async def stop(self) -> None:
        """Tear every subsystem down in reverse dependency order."""
        await self.pipeline_manager.stop()
        try:
            await self.kafka_consumer.stop()
        except Exception:
            logger.exception("Metadata consumer stop failed")
        self.video_reader.stop()

    def __post_init__(self):
        self._source_counter = 0

    def add_stream(self, stream_id: str, rtsp_url: str) -> bool:
        """Add a stream end-to-end: video reader, stream manager, pipeline task."""
        # Register mapping: DeepStream numeric ID -> backend semantic ID
        self.kafka_consumer.set_stream_mapping(self._source_counter, stream_id)
        self._source_counter += 1

        # Auto-seed zone_repo from stream_profiles.json if empty
        self._seed_zones_from_profile(stream_id)

        added = self.video_reader.add_stream(stream_id, rtsp_url)
        # Even if reader rejects (already exists), we still want stream_manager+pipeline aware.
        self.stream_manager.add_stream(stream_id)
        self.ws_streamer.register_stream(stream_id)
        self.pipeline_manager.start_stream(stream_id)
        return added

    def _seed_zones_from_profile(self, stream_id: str) -> None:
        """If zone_repo is empty for this stream, seed it from stream_profiles.json."""
        from app.core.config import settings
        from app.infrastructure.config.stream_profiles import load_stream_profiles

        existing = self.zone_repo.get(stream_id, {})
        if existing.get("roi_polygon"):
            logger.info("[%s] zone_repo already has ROI — skipping seed", stream_id)
            return

        profiles = load_stream_profiles(settings.STREAM_PROFILES_PATH)
        profile = profiles.get(stream_id)
        if not profile:
            logger.info("[%s] No stream profile found — skipping ROI seed", stream_id)
            return

        zone_data = {}
        if profile.get("roi_polygon"):
            zone_data["roi_polygon"] = profile["roi_polygon"]
            zone_data["roi_config_resolution"] = profile.get("resolution", [1920, 1080])
        if profile.get("entry_line"):
            zone_data["entry_line"] = profile["entry_line"]
        if profile.get("exit_line"):
            zone_data["exit_line"] = profile["exit_line"]

        if zone_data:
            self.zone_repo.set(stream_id, zone_data)
            logger.info(
                "[%s] Seeded zone_repo from stream_profiles: %s",
                stream_id,
                list(zone_data.keys()),
            )

    def remove_stream(self, stream_id: str) -> bool:
        """Tear down a single stream end-to-end."""
        self.pipeline_manager.stop_stream(stream_id)
        self.stream_manager.remove_stream(stream_id)
        self.ws_streamer.unregister_stream(stream_id)
        return self.video_reader.remove_stream(stream_id)


def wire_live_pipeline(
    registry: AnalyticsRegistry,
    ws_streamer: WsStreamer,
    camera_repo: CameraRepository,
    zone_repo: ZoneRepository,
    model_registry: ModelRegistry,
) -> LivePipelineHandle:
    """Construct and connect the full live monitoring pipeline."""
    video_reader = RtspVideoReader()
    if settings.METADATA_SOURCE == "mqtt":
        from app.infrastructure.mqtt.consumer import MqttDetectionConsumerService

        kafka_consumer = MqttDetectionConsumerService()
        logger.info(
            "Metadata source: MQTT (%s:%d topic=%s)",
            settings.MQTT_BROKER,
            settings.MQTT_PORT,
            settings.MQTT_TOPIC,
        )
    else:
        kafka_consumer = KafkaConsumerService()
        logger.info(
            "Metadata source: Kafka (%s topic=%s)",
            settings.KAFKA_BOOTSTRAP,
            settings.KAFKA_TOPIC,
        )
    sync_engine = SyncEngine(video_reader, kafka_consumer)

    dispatcher = AnalyticsDispatcher(registry)
    pipeline_manager = PipelineManager(
        sync_engine=sync_engine,
        dispatcher=dispatcher,
        zone_repo=zone_repo,
        model_registry=model_registry,
    )

    stream_manager = StreamManager()

    # Wire WS transport into pipeline events.
    pipeline_manager.on_frame(ws_streamer.on_frame)
    pipeline_manager.on_stats(ws_streamer.on_stats)

    return LivePipelineHandle(
        stream_manager=stream_manager,
        pipeline_manager=pipeline_manager,
        analytics_dispatcher=dispatcher,
        sync_engine=sync_engine,
        video_reader=video_reader,
        kafka_consumer=kafka_consumer,
        model_registry=model_registry,
        ws_streamer=ws_streamer,
        camera_repo=camera_repo,
        zone_repo=zone_repo,
    )
