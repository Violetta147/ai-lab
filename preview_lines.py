import cv2
import numpy as np
import argparse
import sys

# =============================================================================
# DeepStream Line Preview - simulates what nvdsanalytics + OSD will render
# Controls: SPACE = pause/play | LEFT/RIGHT = step frame | Q/ESC = quit
# =============================================================================

VIDEO_PATH = r"D:\datas\Final.yolov8\datasets\VID_20260404_160133.mp4"
TARGET_W, TARGET_H = 640, 640   # Must match STREAMMUX_WIDTH/HEIGHT

# --- Line definitions: (name, color_BGR, coords_string) ---
# Format: x1;y1;x2;y2;dir_x1;dir_y1;dir_x2;dir_y2
# Mapping: "exit road 1, entry road 2, exit road 2, entry road 1"
LINES = [
    ("Exit_1",  (0,   60,  220), "1;568;160;587;84;560;80;603"),       # orange
    ("Entry_2", (0,   200, 0  ), "242;591;505;596;396;608;388;550"),   # green
    ("Exit_2",  (0,   60,  220), "363;356;433;357;396;364;396;333"),   # orange
    ("Entry_1", (0,   200, 0  ), "311;353;353;353;332;341;331;359"),   # green
]

# Color legend: Entry=green, Exit=orange
ENTRY_COLOR = (0, 200, 0)
EXIT_COLOR  = (0, 140, 255)
ARROW_COLOR = (255, 80, 80)    # blue arrow = direction
TEXT_BG     = (20, 20, 20)

def parse(coord_str):
    v = list(map(int, coord_str.split(";")))
    line_pt1  = (v[0], v[1])
    line_pt2  = (v[2], v[3])
    arrow_pt1 = (v[4], v[5])
    arrow_pt2 = (v[6], v[7])
    return line_pt1, line_pt2, arrow_pt1, arrow_pt2

def draw_label(img, text, pt, color):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thick = 0.5, 1
    (tw, th), bl = cv2.getTextSize(text, font, scale, thick)
    x, y = pt
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 4, y + bl), TEXT_BG, -1)
    cv2.putText(img, text, (x + 2, y), font, scale, color, thick, cv2.LINE_AA)

def draw_all_lines(frame):
    img = frame.copy()
    for name, _, coord_str in LINES:
        is_entry = name.startswith("Entry")
        line_color  = ENTRY_COLOR if is_entry else EXIT_COLOR
        lp1, lp2, ap1, ap2 = parse(coord_str)

        # Draw crossing line (thick)
        cv2.line(img, lp1, lp2, line_color, 3, cv2.LINE_AA)
        # Draw endpoint dots
        cv2.circle(img, lp1, 4, line_color, -1)
        cv2.circle(img, lp2, 4, line_color, -1)
        # Draw direction arrow
        cv2.arrowedLine(img, ap1, ap2, ARROW_COLOR, 2,
                        cv2.LINE_AA, tipLength=0.35)

        # Label near midpoint of line
        mid_x = (lp1[0] + lp2[0]) // 2
        mid_y = (lp1[1] + lp2[1]) // 2 - 10
        draw_label(img, name, (mid_x, mid_y), line_color)

    # Legend
    cv2.rectangle(img, (4, 4), (160, 52), (20, 20, 20), -1)
    cv2.putText(img, "Entry (green)",  (8, 20), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, ENTRY_COLOR, 1, cv2.LINE_AA)
    cv2.putText(img, "Exit  (orange)", (8, 40), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, EXIT_COLOR,  1, cv2.LINE_AA)
    cv2.putText(img, "Arrow = direction", (8, 60), cv2.FONT_HERSHEY_SIMPLEX,
                0.38, ARROW_COLOR, 1, cv2.LINE_AA)

    return img

# --- Args ---
parser = argparse.ArgumentParser(description="DeepStream line preview")
parser.add_argument("--frame", "-f", type=int, default=0,
                    help="Start from this frame number (default: 0)")
parser.add_argument("--time", "-t", type=float, default=None,
                    help="Start from this timestamp in seconds (overrides --frame)")
args = parser.parse_args()

# --- Main ---
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"[ERROR] Cannot open: {VIDEO_PATH}")
    sys.exit(1)

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps          = cap.get(cv2.CAP_PROP_FPS) or 30
print(f"[INFO] Video: {int(cap.get(3))}x{int(cap.get(4))}  {fps:.1f}fps  {total_frames} frames")
print("[INFO] Rendering at 640x640 -- matching DeepStream streammux output")
print("[INFO] Controls: SPACE=pause/play | A/D=step 1 | W/S=jump 30 | Q/ESC=quit")

# Seek to start position
start_frame = args.frame
if args.time is not None:
    start_frame = int(args.time * fps)
start_frame = max(0, min(start_frame, total_frames - 1))
if start_frame > 0:
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    print(f"[INFO] Starting at frame {start_frame} ({start_frame/fps:.1f}s)")

cv2.namedWindow("DeepStream Line Preview", cv2.WINDOW_NORMAL)
cv2.resizeWindow("DeepStream Line Preview", TARGET_W, TARGET_H)

paused = False
delay  = max(1, int(1000 / fps))

while True:
    if not paused:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop
            ok, frame = cap.read()

    frame_resized = cv2.resize(frame, (TARGET_W, TARGET_H))
    preview       = draw_all_lines(frame_resized)

    # Frame counter + timestamp
    pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
    ts  = pos / fps
    cv2.putText(preview, f"F{pos}/{total_frames}  {ts:.1f}s",
                (TARGET_W - 150, TARGET_H - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

    cv2.imshow("DeepStream Line Preview", preview)
    key = cv2.waitKey(0 if paused else delay) & 0xFF

    def seek(target_pos):
        p = max(0, min(target_pos, total_frames - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, p)
        ok, fr = cap.read()
        return ok, fr

    if key in (ord('q'), 27):            # Q / ESC
        break
    elif key == ord(' '):                # SPACE = pause/play
        paused = not paused
    elif key == 83 or key == ord('d'):   # D / RIGHT = +1 frame
        ok, frame = seek(pos + 1)
        paused = True
    elif key == 81 or key == ord('a'):   # A / LEFT  = -1 frame
        ok, frame = seek(pos - 2)
        paused = True
    elif key == ord('w'):                # W = jump +30 frames
        ok, frame = seek(pos + 30)
        paused = True
    elif key == ord('s'):                # S = jump -30 frames
        ok, frame = seek(pos - 31)
        paused = True

cap.release()
cv2.destroyAllWindows()
