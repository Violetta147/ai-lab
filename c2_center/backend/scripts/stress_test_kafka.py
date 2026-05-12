"""
STRESS TEST: Kafka Jitter and Drop Simulation.
This script injects metadata into Kafka with artificial delays and bursts
to see if the backend can maintain sync without trailing or ghosting.
"""
import time
import json
import random
from kafka import KafkaProducer

def run_stress_test(broker="localhost:9092", topic="c2_metadata", stream_id="muahe"):
    producer = KafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    print(f"Starting Stress Test on {topic} for {stream_id}...")
    frame_num = 0
    
    try:
        while True:
            # 1. Normal burst (25fps)
            for _ in range(50):
                ts = time.time()
                payload = {
                    "message_type": "c2_event",
                    "stream_id": "0", # source 0 -> muahe
                    "timestamp": ts,
                    "frame_num": frame_num,
                    "objects": [
                        {
                            "tracking_id": 1,
                            "class_id": 0,
                            "bbox": [100 + frame_num % 100, 200, 150 + frame_num % 100, 250]
                        }
                    ]
                }
                producer.send(topic, payload)
                frame_num += 1
                time.sleep(0.04) # 25fps
            
            print(f"  Sent 50 frames. Simulating NETWORK JITTER...")
            
            # 2. Network Jitter (Delay 500ms then burst)
            time.sleep(0.5)
            for _ in range(10):
                ts = time.time()
                payload = {
                    "message_type": "c2_event",
                    "stream_id": "0",
                    "timestamp": ts,
                    "frame_num": frame_num,
                    "objects": [{"tracking_id": 1, "class_id": 0, "bbox": [100 + frame_num % 100, 200, 150 + frame_num % 100, 250]}]
                }
                producer.send(topic, payload)
                frame_num += 1
                time.sleep(0.005) # Super fast burst
                
            print(f"  Sent burst. Simulating PACKET LOSS (gap of 1s)...")
            time.sleep(1.0)
            frame_num += 25 # Skip some frames
            
    except KeyboardInterrupt:
        print("Stress test stopped.")

if __name__ == "__main__":
    run_stress_test()
