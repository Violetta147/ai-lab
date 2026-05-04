# BUG 1 it worked but here's why:
For standard image inference—which is what your Playground API uses (model.predict(image))—Ultralytics YOLO does not leak state between requests. The prediction engine processes the image independently and returns the results.

The only time YOLO maintains state is if you are explicitly using its Tracker (model.track()) on a continuous video stream, where it needs to remember previous frames to assign tracking IDs. For single-image API endpoints, reusing the model object is 100% safe.

While it is technically true that creating a brand new YOLO("model.pt") object for every single API request guarantees a blank slate, it is a terrible idea for performance.

Loading weights from your disk into CPU RAM, and then transferring them to the GPU (VRAM), takes significant time (often hundreds of milliseconds to several seconds).

Doing this per request would cause your API latency to spike massively and could lead to memory fragmentation or out-of-memory crashes under heavy load.

# BUG 2

overlap still not working, i saw no changes in number of detections
add 

# NEW FOUND

[h264 @ 00000181a2bb4700] corrupted macroblock 11 39 (total_coeff=-1)
[h264 @ 00000181a2bb4700] error while decoding MB 11 39

# SUGGESTIONS

Task: Debug Detection Controls in C2 Center Playground

The Detection Controls on our React frontend (Overlap, Confidence, Opacity, and Label Display) do not seem to be affecting the YOLO inference results on the FastAPI backend.

Please investigate the data pipeline between Playground.jsx and backend/api/playground.py and implement fixes based on your findings. Here are the leading hypotheses to check:

1. Investigate the Parameter Data Types & Scaling:

Symptom: The overlap slider shows "59%", but YOLO might be rejecting it.

Check Frontend: Check how overlap, confidence, and opacity are appended to the FormData. Are they being sent as strings with "%", whole numbers (59), or proper normalized floats (0.59)?

Check Backend: Does the POST /api/playground/detect endpoint strictly cast these to float?

Action: Add console.log on the frontend before sending, and print() statements on the backend to verify the exact values and types. Fix the scaling so YOLO receives a float between 0.0 and 1.0.

2. Investigate Opacity Application:

Symptom: Opacity changes on the UI do not change the transparency of the bounding boxes.

Check Backend: The endpoint receives opacity: float = Form(...), but is it actually being applied to the sv.BoxAnnotator or the final image?

Action: If it's missing, implement a blending step (e.g., drawing on an overlay copy and using cv2.addWeighted).

3. Investigate Class Filtering (Label Display):

Symptom: Selecting a specific class like "Car Only" still returns all classes.

Check Backend: Does the endpoint even have a parameter to receive a class filter? Does it pass a classes=[...] argument to model.predict()?

Action: If missing, add a class_filter parameter to the endpoint, map the dropdown selection from the frontend to the correct class ID, and pass it to the model.