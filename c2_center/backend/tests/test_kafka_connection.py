import pytest
import asyncio
from aiokafka import AIOKafkaConsumer
from app.core.config import settings

@pytest.mark.asyncio
async def test_kafka_docker_connection():
    """
    Test that Kafka is running inside Docker Desktop and accessible.
    This test attempts to connect to the Kafka bootstrap server and fetch metadata.
    """
    consumer = AIOKafkaConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP,
        request_timeout_ms=5000,
        connections_max_idle_ms=5000
    )
    try:
        # Start consumer connection which connects to the bootstrap server
        await consumer.start()
        # Fetch topics to ensure it's responding
        topics = await consumer.topics()
        assert topics is not None
        assert isinstance(topics, set)
    finally:
        await consumer.stop()
