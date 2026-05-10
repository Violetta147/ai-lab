imagine your working for a traffic surveillance company, you sit in front of many screens
screen 1: if you use the script on screen 1 you are the god of cameras, using this script, you can enable, create or edit any cameras you can available out there in the streets
screen 2: after you done configure cameras, you need to let the backend knows that too by using cameras tabs and add exactly the cameras and their identities exactly like you typed in screen1
after that the backend will know how to drain/pull frames stream from these cameras if heartbeat check (seperate process) succeeded means when you click Grid View you will see all cameras running
is the current code satisfy this scenario? i don't think so, i think there are some redundant code and 
you must follow:
No overengineering. * Clean, readable code. * Minimal, meaningful comments only. * Focus on the core logic, not defensive edge-case bloat.  


ffmpeg -re -stream_loop -1 -i D:\datas\Final.yolov8\density\test_video.mp4 -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp rtsp://localhost:8554/camera_parking