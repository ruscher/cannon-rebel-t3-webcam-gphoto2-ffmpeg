#!/bin/bash
exec 2>&1
pkill -f "ffmpeg.*v4l2" 2>/dev/null
pkill -f "gphoto2 --stdout" 2>/dev/null
count=0
while pgrep -f "gvfs-gphoto2-volume-monitor" >/dev/null; do
  pkill -f "gvfs-gphoto2-volume-monitor"
  gio mount -u gphoto2://* 2>/dev/null; sleep 0.5; count=$((count+1))
  [ $count -gt 10 ] && pkill -9 -f "gvfs-gphoto2-volume-monitor" && break
done
for dev in /dev/video*; do [ -e "$dev" ] && fuser -k "$dev" 2>/dev/null; done
sleep 1
if ! lsmod | grep -q v4l2loopback; then
  bigsudo modprobe v4l2loopback devices=1 exclusive_caps=0 max_buffers=4 card_label="Canon DSLR Webcam"
else
  [ "$(cat /sys/module/v4l2loopback/parameters/exclusive_caps 2>/dev/null)" = "1" ] && bigsudo modprobe -r v4l2loopback 2>/dev/null && sleep 1 && bigsudo modprobe v4l2loopback devices=1 exclusive_caps=0 max_buffers=4 card_label="Canon DSLR Webcam"
fi
DEVICE_VIDEO=$(ls -v /dev/video* 2>/dev/null | tail -n1)
[ -z "$DEVICE_VIDEO" ] && echo "ERROR: No video device." && exit 1
! gphoto2 --auto-detect 2>&1 | grep -q "usb:" && echo "ERROR: No camera." && exit 1
LOG="/tmp/canon_webcam_stream.log"
nohup gphoto2 --stdout --capture-movie 2>/tmp/gphoto_err.log | ffmpeg -y -hide_banner -loglevel error -stats -i - -filter_complex "[0:v]format=yuv420p,split=2[v1][v2_pre];[v2_pre]scale=700:480,format=yuv420p[v2]" -map "[v1]" -r 60 -f v4l2 "$DEVICE_VIDEO" -map "[v2]" -f mpegts -r 60 -codec:v mpeg1video -b:v 800k -bf 0 "udp://127.0.0.1:5000?pkt_size=1316" > "$LOG" 2>&1 &
PID=$!; disown; sleep 3
kill -0 $PID 2>/dev/null && exit 0 || cat "$LOG" && exit 1
