import cv2

# CONFIGURATION
video_path = r"D:\datas\Final.yolov8\datasets\VID_20260404_160133.mp4"
# MUST match the STREAMMUX_WIDTH/HEIGHT in your setup script
target_width = 640
target_height = 640

# State variables
points = []

def click_event(event, x, y, flags, params):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        cv2.circle(img, (x, y), 3, (0, 0, 255), -1)

        if len(points) == 2:  # Drawn the line
            cv2.line(img, points[0], points[1], (0, 255, 0), 2)
        elif len(points) == 4:  # Drawn the direction arrow
            cv2.arrowedLine(img, points[2], points[3], (255, 0, 0), 2)

            # FORMAT: x1;y1;x2;y2;dir_x1;dir_y1;dir_x2;dir_y2
            ds_string = (
                f"{points[0][0]};{points[0][1]};"
                f"{points[1][0]};{points[1][1]};"
                f"{points[2][0]};{points[2][1]};"
                f"{points[3][0]};{points[3][1]}"
            )
            print("\n--- COPY THIS INTO YOUR SCRIPT ---")
            print(ds_string)
            print("----------------------------------")
            points.clear()

        cv2.imshow('Coordinate Grabber', img)

# Load video and get first frame
cap = cv2.VideoCapture(video_path)
success, frame = cap.read()
if not success:
    print("Error: Could not read video.")
    exit()

img = cv2.resize(frame, (target_width, target_height))

# cv2.imshow with WINDOW_AUTOSIZE (default) already shows at original size.
# The window here is exactly target_width × target_height = DeepStream output size.
# If lines look smaller in VLC, set VLC to 1:1 zoom (Video → Zoom → 1:1).
cv2.imshow('Coordinate Grabber', img)

print(f"[INFO] Window size = {target_width}x{target_height} — matches DeepStream streammux output.")
print("INSTRUCTIONS:")
print("1. Click TWICE to define the LEFT and RIGHT ends of your counting line.")
print("2. Click TWICE more to define the START and END of the direction arrow.")
print("   (e.g., Click 'above' then 'below' the line for Entry/Downwards).")
print("3. The DeepStream coordinate string is printed automatically.")
print("4. Repeat for each line. Press ESC to quit.")

cv2.setMouseCallback('Coordinate Grabber', click_event)
cv2.waitKey(0)
cv2.destroyAllWindows()
cap.release()