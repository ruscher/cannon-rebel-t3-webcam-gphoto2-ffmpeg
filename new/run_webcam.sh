#!/bin/bash
# DEBUG MODE
exec 2>&1

echo "[Wrapper] STARTING..."

# 1. Cleanup - AGGRESSIVE
echo "[Wrapper] Cleaning up..."

# Usar kill com verificações mais específicas
echo "[Wrapper] Terminating ffmpeg processes..."
pkill -f "ffmpeg.*v4l2" 2>/dev/null || echo "  No ffmpeg-v4l2 processes found"

echo "[Wrapper] Terminating gphoto2 processes..."
pkill -f "gphoto2 --stdout" 2>/dev/null || echo "  No gphoto2 capture processes found"

# Kill GVFS monitor in a loop until it's gone
count=0
while pgrep -f "gvfs-gphoto2-volume-monitor" >/dev/null; do
    echo "[Wrapper] Killing gvfs monitor (attempt $((count+1)))..."
    pkill -f "gvfs-gphoto2-volume-monitor"
    gio mount -u gphoto2://* 2>/dev/null
    sleep 0.5
    count=$((count+1))
    if [ $count -gt 10 ]; then
        echo "[Wrapper] WARNING: Could not kill gvfs monitor!"
        echo "[Wrapper] Trying more aggressive approach..."
        pkill -9 -f "gvfs-gphoto2-volume-monitor"
        break
    fi
done

# Additional cleanup for any process using video devices
echo "[Wrapper] Checking for processes using video devices..."
for dev in /dev/video*; do
    if [ -e "$dev" ]; then
        if fuser "$dev" 2>/dev/null; then
            echo "[Wrapper] Killing processes using $dev..."
            fuser -k "$dev" 2>/dev/null
        fi
    fi
done

# Extra wait for system to settle
sleep 1

# Try to release USB device if locked
# (Requires usbreset specific to device, harder to automate without ID)

# 2. Check Driver
if lsmod | grep -q v4l2loopback; then
    echo "[Wrapper] Driver loaded."
else
    echo "[Wrapper] Driver NOT loaded. Trying to load..."
    bigsudo modprobe v4l2loopback exclusive_caps=1 max_buffers=2 card_label="Canon Webcam" || echo "[Wrapper] Modprobe failed!"
fi

# 3. Device check
DEVICE_VIDEO=$(ls -v /dev/video* 2>/dev/null | tail -n1)
echo "[Wrapper] Device: $DEVICE_VIDEO"
if [ -z "$DEVICE_VIDEO" ]; then
    echo "[Wrapper] ERROR: No video device."
    exit 1
fi

# 4. GPhoto check
echo "[Wrapper] Checking camera..."
# Capture output just to verify command runs
GPHOTO_OUT=$(gphoto2 --auto-detect 2>&1)
echo "$GPHOTO_OUT"

if echo "$GPHOTO_OUT" | grep -q "No camera found"; then
    echo "[Wrapper] ERROR: No camera."
    exit 1
fi

if [ -z "$GPHOTO_OUT" ]; then
    echo "[Wrapper] WARNING: gphoto2 returned nothing?"
fi

# 5. Pipeline
echo "[Wrapper] Starting Pipeline..."
LOG_FILE="/tmp/canon_webcam_stream.log"

nohup gphoto2 --stdout --capture-movie 2>/tmp/gphoto_err.log | \
ffmpeg -y -hide_banner -loglevel warning -stats \
    -i - \
    -vf "format=yuv420p" \
    -f v4l2 "$DEVICE_VIDEO" > "$LOG_FILE" 2>&1 &

PID=$!
echo "[Wrapper] PID: $PID"
disown

# 6. Wait (Short check)
sleep 2
if kill -0 $PID 2>/dev/null; then
    echo "[Wrapper] Process is running."
    
    # Check caps just once for debug
    v4l2-ctl -d "$DEVICE_VIDEO" --all | grep Caps
    
    echo "[Wrapper] SUCCESS? (Assume yes for now)"
    exit 0
else
    echo "[Wrapper] ERROR: Process died immediately."
    cat "$LOG_FILE"
    cat /tmp/gphoto_err.log
    exit 1
fi
