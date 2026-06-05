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
        client.subscribe("traffic/system/ota_update", qos=1)
        log("Subscribed to OTA update topic.")
        return
    raise ConnectionError(f"MQTT connection failed with rc={rc}")

def on_message(client, userdata, msg):
    import json
    import threading
    from .ota_updater import ota_manager
    from .logger import log
    
    if msg.topic == "traffic/system/ota_update":
        try:
            data = json.loads(msg.payload.decode())
            if data.get("action") == "UPDATE_MODEL" and "model_name" in data:
                model_name = data["model_name"]
                log(f"Received OTA update command for model: {model_name}")
                # Chạy tải file trong luồng phụ để không block MQTT
                threading.Thread(target=ota_manager.handle_update, args=(model_name,), daemon=True).start()
        except Exception as e:
            log(f"Error processing OTA message: {e}")

def create_mqtt_client(camera_id: str) -> mqtt_client.Client:
    log("Connecting to MQTT broker...")
    client = mqtt_client.Client(client_id=f"edge_{camera_id}")
    client.on_connect = on_mqtt_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()
    return client

