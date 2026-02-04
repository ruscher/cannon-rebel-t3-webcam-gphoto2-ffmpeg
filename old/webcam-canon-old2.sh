#!/bin/bash

# Carrega o módulo v4l2loopback com parâmetros definidos
bigsudo modprobe -r v4l2loopback
bigsudo modprobe v4l2loopback exclusive_caps=1 max_buffer=2

# Variáveis gerais
CAMERA_TITLE="Camera Canon Rebel T3"
DEVICE_VIDEO=$(ls /dev/ | grep video | tail -n1)

# Prompt inicial
kdialog --yesno "Você quer tirar uma foto ou gravar um vídeo?" --yes-label "Foto" --no-label "Vídeo" --title "$CAMERA_TITLE"

if [ "$?" = "0" ]; then
    # Opção Foto
    kdialog --msgbox "ATENÇÃO: Coloque a câmera na posição de fotografia." --title "$CAMERA_TITLE"
    gphoto2 --capture-image-and-download
else
    # Opção Vídeo
    kdialog --msgbox "ATENÇÃO: Coloque a câmera na posição de filmagem." --title "$CAMERA_TITLE"

    # Verifica se a câmera está conectada
    gphoto2 --auto-detect > /tmp/gphoto_check.txt
    if grep -q "No camera found" /tmp/gphoto_check.txt; then
        kdialog --error "A câmera não está ligada ou conectada!" --title "$CAMERA_TITLE"
        exit 1
    fi

    kdialog --msgbox "Modo WebCam ativado!" --title "$CAMERA_TITLE"

    # Captura o stream da câmera e força 60 FPS
    gphoto2 --stdout --capture-movie | ffmpeg -i - -r 30 -vf "format=yuv420p" -pix_fmt yuv420p -c:v rawvideo -f v4l2 /dev/$(ls /dev/ | grep video | tail -n1)
    
    #gphoto2 --stdout --capture-movie | ffmpeg -i - -vf format=yuv420p -preset ultrafast -tune zerolatency -b:v 6M -f v4l2 /dev/$DEVICE_VIDEO
    #gphoto2 --stdout --capture-movie | ffmpeg -i - -r 30 -vf "scale=1280:720,format=yuv420p" -c:v libx264 -preset ultrafast -tune zerolatency -b:v 6M -f v4l2 /dev/$DEVICE_VIDEO
fi
