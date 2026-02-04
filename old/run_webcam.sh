#!/bin/bash

# Script auxiliar para iniciar a webcam Canon T3
# Isso garante que o ambiente seja idêntico ao terminal do usuário.

echo "[Wrapper] Iniciando setup da webcam..."

# 1. Matar processos interferentes
echo "[Wrapper] Matando gvfs-gphoto2-volume-monitor..."
pkill -f gvfs-gphoto2-volume-monitor
gio mount -u gphoto2://* 2>/dev/null

# 2. Drivers
echo "[Wrapper] Recarregando drivers (v4l2loopback)..."
# Usamos o bigsudo do sistema. Se pedir senha, deve aparecer no terminal.
bigsudo bash -c 'modprobe -r v4l2loopback; modprobe v4l2loopback exclusive_caps=1 max_buffer=2'

if [ $? -ne 0 ]; then
    echo "[Wrapper] Erro ao carregar drivers!"
    exit 1
fi

echo "[Wrapper] Aguardando udev (2s)..."
sleep 2

# 3. Verificar Câmera
echo "[Wrapper] Verificando câmera..."
gphoto2 --auto-detect > /tmp/gphoto_check.txt
cat /tmp/gphoto_check.txt

if grep -q "No camera found" /tmp/gphoto_check.txt; then
    echo "[Wrapper] Erro: Câmera não encontrada (gphoto2)."
    exit 1
fi

# Detectar dispositivo de vídeo
DEVICE_VIDEO=$(ls /dev/ | grep video | tail -n1)
if [ -z "$DEVICE_VIDEO" ]; then
    echo "[Wrapper] Erro: Nenhum dispositivo /dev/video* encontrado."
    exit 1
fi

echo "[Wrapper] Dispositivo alvo: /dev/$DEVICE_VIDEO"

# 4. Iniciar Pipeline
echo "[Wrapper] Iniciando stream..."

# Forçar kill novamente por segurança
pkill -f gvfs-gphoto2-volume-monitor
sleep 1 # Wait for things to settle after check/kill

# Ensure log file exists
touch /tmp/canon_webcam_stream.log

# Comando exato fornecido pelo usuário, com log de erro para debug
# Output redirected to log file for persistent monitoring
# Added -stats to force progress reporting even when writing to a file
{ echo "[Wrapper] Starting Pipeline..."; gphoto2 --stdout --capture-movie 2>/tmp/webcam_gphoto.err | ffmpeg -stats -i - -r 30 -vf "format=yuv420p" -pix_fmt yuv420p -c:v rawvideo -f v4l2 /dev/$DEVICE_VIDEO; } > /tmp/canon_webcam_stream.log 2>&1
