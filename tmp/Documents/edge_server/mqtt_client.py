from __future__ import annotations

from paho.mqtt import client as mqtt_client

from .config import MQTT_BROKER, MQTT_PORT
from .logger import log


def on_mqtt_connect(
    client: mqtt_client.Client,
    userdata: object,
    flags: dict[str, object],
    rc: int,
) -> None:
    if rc == 0:
        log("MQTT connected successfully.")
        return
    raise ConnectionError(f"MQTT connection failed with rc={rc}")


def create_mqtt_client(camera_id: str) -> mqtt_client.Client:
    log("Connecting to MQTT broker...")
    client = mqtt_client.Client(client_id=f"edge_{camera_id}")
    client.on_connect = on_mqtt_connect
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()
    return client

