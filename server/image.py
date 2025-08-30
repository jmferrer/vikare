#!/usr/bin/python
# Loop to get image camera with the time as filename
import cv2
import os
import time
from datetime import datetime, timedelta, timezone
from glob import glob

#CAMERA_URL="rtsp://thingino:thingino@192.168.132.22:554/ch0"
#CAMERA_URL="rtsp://thingino:thingino@192.168.65.22:554/ch0"
#CAMERA_URL="rtsp://thingino:thingino@192.168.21.132:554/ch0"
CAMERA_URL="rtsp://thingino:thingino@192.168.43.113:554/ch0"
print( "try: " + CAMERA_URL )
OUTPUT_DIR = "/usr/local/src/data/images"
MAX_IMAGES = 500
#CAPTURE_INTERVAL_SEC = 0.5  # 100 ms = 10 FPS
CAPTURE_INTERVAL_SEC = 1  # 100 ms = 10 FPS

# Create output directory if not exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Open connection to camera using tcp. udp does not work in kubernetes
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
cap = cv2.VideoCapture(CAMERA_URL)

# First timestamp
next_capture_time = datetime.now(timezone.utc)

while True:
    while datetime.now(timezone.utc) < next_capture_time:
        time.sleep(0.01)

    # get actual date
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]

    # mpv --profile=fast rtsp://thingino:thingino@192.168.200.22:554/ch0
    # Capture image
    ret, frame = cap.read()
    if not ret:
        print(f"[{timestamp_str}] ❌ Error getting the image", flush=True)
        cap.release()
        cap = cv2.VideoCapture(CAMERA_URL)
    else:
        filepath = os.path.join(OUTPUT_DIR, f"{timestamp_str}.jpg")
        cv2.imwrite(filepath, frame)
        print(f"[{timestamp_str}] ✅ Image saved", flush=True)

    # Rotate image files maintaining only most recent MAX_IMAGES
    images = sorted(glob(os.path.join(OUTPUT_DIR, "*.jpg")))
    if len(images) > MAX_IMAGES:
        for old_image in images[:len(images) - MAX_IMAGES]:
            os.remove(old_image)

    # Calculate next timestamp
    next_capture_time += timedelta(seconds=CAPTURE_INTERVAL_SEC)
