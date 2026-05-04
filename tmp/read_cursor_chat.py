import sqlite3
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = r'C:\Users\violet\AppData\Roaming\Cursor\User\globalStorage\state.vscdb'
output_dir = r'd:\datas\Final.yolov8\tmp\cursor_history'
os.makedirs(output_dir, exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

conv_id = '2d54b365-1c20-4cba-81ad-51d4b4575b29'

# Get ALL bubbles for this conversation 
cursor.execute(f"SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:{conv_id}%'")
bubbles = cursor.fetchall()
print(f"Total bubbles: {len(bubbles)}")

# Filter for deepstream/rtsp related
keywords = ['deepstream', 'rtsp', 'mediamtx', 'ffmpeg', 'jetson', 'rtp', 'bitrate', 
            'udp-port', 'rtsp-port', 'pipeline', 'sink0', 'sink1', 'filesink',
            'setup_deepstream', 'onnx', 'nvstreammux', 'perf:', 'terminal',
            'rtp packets', 'pps', 'fu-a', 'network', 'udp', 'tcp',
            'docker run', 'nvcr.io', 'deepstream-l4t']

relevant_messages = []
for key, val in bubbles:
    if val is None:
        continue
    bubble = json.loads(val)
    msg_type = bubble.get('type', '?')
    text = bubble.get('text', '') or bubble.get('rawText', '') or ''
    
    if any(kw in text.lower() for kw in keywords):
        bubble_id = key.split(':')[-1]
        relevant_messages.append({
            'id': bubble_id,
            'type': msg_type,
            'text': text
        })

print(f"Relevant messages: {len(relevant_messages)}")

# Save to markdown file
with open(os.path.join(output_dir, 'deepstream_rtsp_conversation.md'), 'w', encoding='utf-8') as f:
    f.write(f"# DeepStream/RTSP Conversation from Cursor\n")
    f.write(f"# Conversation ID: {conv_id}\n")
    f.write(f"# Total bubbles: {len(bubbles)}, Relevant: {len(relevant_messages)}\n\n")
    
    for msg in relevant_messages:
        role = "USER" if msg['type'] in [1, '1'] else "AI" if msg['type'] in [2, '2'] else f"TYPE-{msg['type']}"
        f.write(f"## [{role}]\n")
        f.write(f"{msg['text']}\n\n")
        f.write("---\n\n")

print(f"Saved to deepstream_rtsp_conversation.md")

# Now show user messages about terminal/rtsp/deepstream
print("\n=== USER messages about DeepStream/RTSP ===")
user_msgs = [m for m in relevant_messages if m['type'] in [1, '1']]
for msg in user_msgs:
    preview = msg['text'][:400]
    print(f"\n[USER #{msg['id'][:8]}]")
    print(preview)
    print("---")

# Also get terminal history
cursor.execute("SELECT value FROM ItemTable WHERE key = 'terminal.history.entries.commands'")
row = cursor.fetchone()
if row:
    cmds = json.loads(row[0])
    print(f"\n=== Terminal History ({len(cmds)} entries) ===")
    # Filter for relevant commands
    for cmd in cmds:
        cmd_str = str(cmd)
        if any(kw in cmd_str.lower() for kw in ['deepstream', 'rtsp', 'mediamtx', 'ffmpeg', 'docker', 'jetson', 'ssh']):
            print(f"  {cmd_str[:200]}")

conn.close()
