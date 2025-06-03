#!/bin/bash
# Lista de cameras suportadas: http://gphoto.org/proj/libgphoto2/support.php
# Criado por: Rafael Ruscher - rruscher@gmail.com
#             Barnabe Di Kartola - BigLinux Team


# Configuração para Sua Camera
NAME_DEVICE="Canon_T3_Webcam"
RESOLUTION="1280x720"
FPS=30
VIDEO_DEVICE="/dev/video20"

# Verifica se é root
if [ "$(id -u)" -ne 0 ]; then
    echo "Este script precisa ser executado como root. Use sudo!"
    exit 1
fi

# Função para instalar pacotes
install_package() {
    if ! pacman -Qs "$1" >/dev/null; then
        echo "Instalando $1..."
        pacman -Sy --noconfirm "$1" || {
            echo "Falha ao instalar $1"
            exit 1
        }
    fi
}

# Instala dependências essenciais
echo "Instalando dependências básicas..."
install_package "base-devel"
install_package "git"
install_package "linux-headers"
install_package "dkms"
install_package "gphoto2"
install_package "ffmpeg"
install_package "kdialog"

# Instala v4l2loopback a partir do AUR
if ! pacman -Qs v4l2loopback-dkms >/dev/null; then
    echo "Instalando v4l2loopback do AUR..."

    # Instala yay se não existir
    if ! command -v yay >/dev/null; then
        echo "Instalando yay..."
        sudo -u "$SUDO_USER" bash -c 'git clone https://aur.archlinux.org/yay.git /tmp/yay && cd /tmp/yay && makepkg -si --noconfirm'
    fi

    # Instala v4l2loopback via yay
    sudo -u "$SUDO_USER" yay -Sy --noconfirm v4l2loopback-dkms
fi

# Compila manualmente se necessário
if ! modinfo v4l2loopback >/dev/null 2>&1; then
    echo "Compilando v4l2loopback manualmente..."
    temp_dir=$(mktemp -d)
    git clone https://github.com/umlaeute/v4l2loopback.git "$temp_dir"
    cd "$temp_dir"

    # Desativa assinatura de módulo para evitar erros
    export KBUILD_SIGN_PIN=""

    make
    make install
    depmod -a
    cd ..
    rm -rf "$temp_dir"
fi

# Carrega o módulo
echo "Configurando módulo v4l2loopback..."
modprobe -r v4l2loopback 2>/dev/null
modprobe v4l2loopback \
    exclusive_caps=1 \
    max_buffers=2 \
    card_label=$NAME_DEVICE \
    video_nr=20

# Verifica se o módulo foi carregado
if ! lsmod | grep -q v4l2loopback; then
    kdialog --error "Falha ao carregar v4l2loopback. Verifique os logs."
    exit 1
fi



# Menu interativo
choice=$(kdialog --menu "Controle da Câmera $NAME_DEVICE" \
    "1" "Modo Fotografia" \
    "2" "Modo Webcam" \
    "3" "Sair")

case $choice in
    1)
        kdialog --msgbox "Coloque a câmera no modo de fotografia e pressione OK"
        gphoto2 --capture-image-and-download
        ;;
    2)
        kdialog --msgbox "Coloque a câmera no modo de filmagem e pressione OK"

        # Verifica conexão com a câmera
        if ! gphoto2 --abilities >/dev/null 2>&1; then
            kdialog --error "Câmera não detectada! Verifique a conexão USB e o modo da câmera."
            exit 1
        fi

        # Inicia a webcam em segundo plano
        kdialog --passivepopup "Webcam ativa em $VIDEO_DEVICE" 5 &

        # Parâmetros otimizados para Camera
        gphoto2 --stdout --capture-movie | \
        ffmpeg -i - \
               -f mjpeg \
               -vf "format=yuv420p,scale=$RESOLUTION" \
               -r $FPS \
               -f v4l2 \
               -vcodec rawvideo \
               -pix_fmt yuv420p \
               $VIDEO_DEVICE

        if [ $? -ne 0 ]; then
            kdialog --error "Erro na transmissão. Tente reiniciar a câmera."
        fi
        ;;
    *)
        exit 0
        ;;
esac
