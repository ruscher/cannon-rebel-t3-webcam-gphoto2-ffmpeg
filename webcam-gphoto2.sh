#!/usr/bin/env bash
#
# ========================================================================================
#
# Autores:       Rafael Ruscher     - rruscher@gmail.com
#                Barnabe Di Kartola - BigLinux Team
#                Fernando Souza     - https://github.com/tuxslack/webcam-gphoto2 / https://www.youtube.com/@fernandosuporte
# Data:          27/09/2025
# Versão:        0.2
# Script:        
# Licença:       MIT
# Descrição:     
# 
# Lista de cameras suportadas: http://gphoto.org/proj/libgphoto2/support.php 
#  
# Instalação: sudo mv -i webcam-gphoto2.sh /usr/local/bin/              
#
# Uso: webcam-gphoto2.sh        
#                
#
#
# Requisitos:   bash, git, base-devel, dkms, linux-headers, gphoto2, ffmpeg, yad
# 
#
# ========================================================================================

# DroidCam Webcam (Classic)

# https://play.google.com/store/apps/details?id=com.dev47apps.droidcam


clear

# Definir o caminho do log

log="/tmp/webcam.log"

rm "$log" 2>/dev/null



# Verifica se é root
if [ "$(id -u)" -ne 0 ]; then

    echo -e "\nEste script precisa ser executado como root. Use sudo! \n"

    exit 1
fi


# Verifica se o usuário está no grupo 'video'

# $SUDO_USER é uma variável de ambiente definida pelo sudo.
# Ela contém o nome do usuário original que invocou o comando sudo.

if ! id "$SUDO_USER" | grep -q '\bvideo\b'; then

    yad --center --warning  --text="O usuário '$SUDO_USER' não pertence ao grupo 'video'.\n\nIsso pode impedir que a câmera funcione corretamente como webcam.\n\nPara corrigir, execute:\n\nsudo usermod -aG video $SUDO_USER\n\ne reinicie a sessão (logout/login)."

fi


CAMERA_DEV=$(v4l2-ctl --list-devices 2>/dev/null | grep -A1 -E 'Camera|Webcam' | tail -n1 | awk '{print $1}')

RESOLUTION=$(v4l2-ctl --device="$CAMERA_DEV" --list-formats-ext 2>/dev/null | \
    grep 'Size: Discrete' | awk '{print $3}' | sort -uV | tail -n1)

# Configuração da Câmera

camera_config=$(yad --center --form \
    --title="Configuração da Câmera" \
    --width=400 \
    --height=300 \
    --field="Nome do dispositivo:" "Canon_T3_Webcam" \
    --field="Resolução (ex: 1280x720):" "$RESOLUTION" \
    --field="FPS:" "30" \
    --field="Número do /dev/video (ex: 0):" "$CAMERA_DEV")

# Verifica se o usuário cancelou
if [ $? -ne 0 ]; then

    echo "Configuração cancelada."

    exit 1
fi

# Divide os valores do formulário em variáveis
IFS="|" read -r NAME_DEVICE RESOLUTION FPS VIDEO_NUM <<< "$camera_config"
VIDEO_DEVICE="$CAMERA_DEV"




# Detecta a distribuição
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

DISTRO=$(detect_distro)

# Função para instalar pacotes
install_package() {
    PKG=$1

    case "$DISTRO" in
        arch|manjaro)
            if ! pacman -Qs "$PKG" >/dev/null; then
                echo "Instalando $PKG..."
                sudo pacman -Sy --noconfirm "$PKG"
            fi
            ;;
        debian|ubuntu)
            if ! dpkg -s "$PKG" >/dev/null 2>&1; then
                echo "Instalando $PKG..."
                sudo apt update && apt install -y "$PKG"
            fi
            ;;
        void)
            if ! xbps-query -p pkgver "$PKG" >/dev/null 2>&1; then
                echo "Instalando $PKG..."
                sudo xbps-install -Sy "$PKG"
            fi
            ;;
        *)
            echo -e "\nDistribuição não suportada automaticamente. Instale manualmente o pacote: $PKG \n"
            ;;
    esac
}

# Pacotes comuns
echo "Instalando dependências..."
for pkg in git base-devel dkms linux-headers gphoto2 ffmpeg yad; do
    install_package "$pkg"
done

# Instala v4l2loopback
install_v4l2loopback() {
    case "$DISTRO" in
        arch|manjaro)
            if ! pacman -Qs v4l2loopback-dkms >/dev/null; then
                echo "Instalando v4l2loopback do AUR..."

                if ! command -v yay >/dev/null; then
                    echo "Instalando yay..."
                    sudo -u "$SUDO_USER" bash -c 'git clone https://aur.archlinux.org/yay.git /tmp/yay && cd /tmp/yay && makepkg -si --noconfirm'
                fi

                sudo -u "$SUDO_USER" yay -Sy --noconfirm v4l2loopback-dkms
            fi
            ;;
        debian|ubuntu)
            install_package build-essential
            if ! modinfo v4l2loopback >/dev/null 2>&1; then
                echo "Compilando v4l2loopback manualmente..."
                temp_dir=$(mktemp -d)
                git clone https://github.com/umlaeute/v4l2loopback.git "$temp_dir"
                cd "$temp_dir"
                make && make install
                depmod -a
                cd ..
                rm -rf "$temp_dir"
            fi
            ;;
        void) echo "Void Linux..."

            # install_package v4l2loopback

            # $ sudo modprobe v4l2loopback
            # modprobe: FATAL: Module v4l2loopback not found in directory /lib/modules/6.16.9_1

            cd /tmp
            git clone https://github.com/umlaeute/v4l2loopback.git || exit
            cd v4l2loopback/

            sudo make && mkdir -p /tmp/v4l2loopback-install && sudo make install DESTDIR=/tmp/v4l2loopback-install

            echo "🗃️ Atualizar módulos (se aplicável)"
            sudo depmod -a

           # Descobrir o que foi instalado
           # sudo find /usr/local -type f -newermt "2025-09-27"

            ;;
    esac
}

install_v4l2loopback


# Carrega o módulo
echo "Carregando módulo v4l2loopback..." | tee -a "$log"

sudo modprobe -r v4l2loopback | tee -a "$log"

# sudo modprobe  v4l2loopback | tee -a "$log"

if modprobe v4l2loopback exclusive_caps=1 max_buffers=2 card_label=$NAME_DEVICE video_nr=$VIDEO_NUM; then

    echo "Módulo v4l2loopback carregado com sucesso." | tee -a "$log"

else

    echo "Erro ao carregar o módulo v4l2loopback." | tee -a "$log"

    yad --center --error --text="Erro ao carregar o módulo v4l2loopback. Veja o log em $log"

    exit 1
fi



# Verifica se o módulo foi carregado
if ! lsmod | grep -q v4l2loopback; then

    echo "Falha ao carregar v4l2loopback. Verifique o log $log."

    yad --center --error --text="Falha ao carregar v4l2loopback. Verifique o log $log."

    exit 1
fi

# Veja o que o gphoto2 detecta:



# Verifica se há câmeras compatíveis detectadas
CAMERAS=$(gphoto2 --auto-detect | grep -v -E 'Modelo|Porta|^-{3,}' | sed '/^\s*$/d')

if [[ -z "$CAMERAS" ]]; then

    yad --center \
        --title="Nenhuma Câmera Detectada" \
        --text="📷 <b>Nenhuma câmera compatível foi detectada.</b>\n\nVerifique se a câmera está:\n- Conectada via USB\n- Ligada e em modo correto (foto/filmagem)\n\n⚠️ Apenas câmeras DSLR, mirrorless ou compactas compatíveis com o gPhoto2 são suportadas.\n\n🔗 <a href='https://gphoto.org/proj/libgphoto2/support.php'>Lista de Câmeras Compatíveis</a>" \
        --button=OK:0 \
        --width=400

echo "📦 Câmera não suportada pelo gphoto2

Verifique se sua câmera está na lista de compatibilidade oficial:

👉 https://gphoto.org/proj/libgphoto2/support.php

O gphoto2 só funciona com câmeras digitais que usam o protocolo PTP/MTP, como:

DSLRs (Canon, Nikon, Sony, etc.)

Câmeras mirrorless

Algumas compactas

Ele não funciona com webcams comuns (como Logitech, Razer, webcams integradas em notebooks ou celulares via USB sem apps específicos).
"  | tee -a "$log"

    exit 1
else
    echo "Câmera(s) detectada(s):"
    echo "$CAMERAS"
fi





# Verificar se a webcam foi reconhecida

v4l2-ctl --list-devices



# Menu interativo
choice=$(yad --center --title="Controle da Câmera $NAME_DEVICE" \
    --text="Escolha o modo da câmera:" \
    --button="Modo Fotografia:1" \
    --button="Modo Webcam:2" \
    --button="Sair:3" \
    --width="400" --height="200")

case $choice in
    1)
        yad --center --info --text="Coloque a câmera no modo de fotografia e pressione OK"
        gphoto2 --capture-image-and-download | tee -a "$log"
        ;;
    2)
        yad --center --info --text="Coloque a câmera no modo de filmagem e pressione OK"

        if ! gphoto2 --abilities >/dev/null 2>&1; then
            yad --center --error --text="Câmera não detectada! Verifique a conexão USB e o modo da câmera."
            exit 1
        fi

        yad --notification --text="Webcam ativa em $VIDEO_DEVICE" &

        gphoto2 --stdout --capture-movie | \
        ffmpeg -i - \
               -f mjpeg \
               -vf "format=yuv420p,scale=$RESOLUTION" \
               -r $FPS \
               -f v4l2 \
               -vcodec rawvideo \
               -pix_fmt yuv420p \
               $VIDEO_DEVICE 2>&1 | tee -a "$log"

        if [ $? -ne 0 ]; then
            yad --center --error --text="Erro na transmissão. Tente reiniciar a câmera."
        fi
        ;;
    *)
        exit 1
        ;;
esac

exit 0

