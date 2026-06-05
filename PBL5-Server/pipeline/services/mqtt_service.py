import sys
import os
import time
import signal

# Add the project root to sys.path so we can import 'pipeline'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pipeline.utils.mqtt_handler import MQTTHandler
from pipeline.utils.db_handler import DBHandler
from pipeline.config import DB_RETRY_MAX_ATTEMPTS


def main():
    print("🚀 Starting MQTT Listener Service...")

    # Khởi tạo DB với retry (chờ DB sẵn sàng khi boot cùng docker-compose)
    db = DBHandler()
    for attempt in range(DB_RETRY_MAX_ATTEMPTS):
        try:
            db.connect()
            break
        except Exception as e:
            wait = 2 * (attempt + 1)
            print(f"⏳ [MQTT Service] Waiting for DB... attempt {attempt + 1}/{DB_RETRY_MAX_ATTEMPTS} ({e})")
            time.sleep(wait)
    else:
        print("❌ [MQTT Service] Could not connect to DB after all retries. Exiting.")
        sys.exit(1)

    mqtt = MQTTHandler(db)

    # Graceful shutdown handler
    def shutdown_handler(signum, frame):
        print(f"\n🛑 [MQTT Service] Received signal {signum}. Shutting down gracefully...")
        mqtt.client.disconnect()
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        mqtt.run()
    except KeyboardInterrupt:
        print("🛑 Stopping MQTT Listener...")
    except Exception as e:
        print(f"❌ [MQTT Service] Critical error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
