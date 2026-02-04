#!/bin/bash

# =============================================================================
# GPhoto2 Webcam Controller - Installer for Arch Linux
# =============================================================================
# This script installs all required dependencies for the GPhoto2 Webcam 
# Controller application to work properly on Arch Linux based systems.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  GPhoto2 Webcam Controller - Installer    ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running as root (we need sudo for pacman)
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}Aviso: Executando como root. Algumas verificações podem não funcionar corretamente.${NC}"
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to check if a package is installed
package_installed() {
    pacman -Qi "$1" &> /dev/null
}

# Detect package manager
detect_package_manager() {
    if command_exists pacman; then
        echo "pacman"
    elif command_exists yay; then
        echo "yay"
    elif command_exists paru; then
        echo "paru"
    else
        echo "unknown"
    fi
}

PKG_MANAGER=$(detect_package_manager)

echo -e "${GREEN}Sistema detectado:${NC} Arch Linux"
echo -e "${GREEN}Gerenciador de pacotes:${NC} $PKG_MANAGER"
echo ""

# =============================================================================
# Required Packages
# =============================================================================

# Core packages from official repos
PACMAN_PACKAGES=(
    "gphoto2"           # Camera control utility
    "libgphoto2"        # Library for camera access
    "ffmpeg"            # Video processing
    "v4l2loopback-dkms" # Virtual video device kernel module (requires DKMS)
    "python"            # Python 3
    "python-gobject"    # Python GObject bindings (PyGObject)
    "gtk4"              # GTK4 toolkit
    "libadwaita"        # Adwaita library for modern GNOME apps
    "linux-headers"     # Kernel headers for DKMS module compilation
)

# Optional packages
OPTIONAL_PACKAGES=(
    "v4l-utils"         # Video4Linux utilities (v4l2-ctl)
)

# =============================================================================
# Dependency Check
# =============================================================================

echo -e "${YELLOW}Verificando dependências...${NC}"
echo ""

MISSING_PACKAGES=()
INSTALLED_PACKAGES=()

for pkg in "${PACMAN_PACKAGES[@]}"; do
    if package_installed "$pkg"; then
        INSTALLED_PACKAGES+=("$pkg")
        echo -e "  ${GREEN}✓${NC} $pkg"
    else
        MISSING_PACKAGES+=("$pkg")
        echo -e "  ${RED}✗${NC} $pkg ${YELLOW}(faltando)${NC}"
    fi
done

echo ""

# Check optional packages
echo -e "${YELLOW}Pacotes opcionais:${NC}"
for pkg in "${OPTIONAL_PACKAGES[@]}"; do
    if package_installed "$pkg"; then
        echo -e "  ${GREEN}✓${NC} $pkg"
    else
        echo -e "  ${YELLOW}○${NC} $pkg (opcional, não instalado)"
    fi
done

echo ""

# =============================================================================
# Python Module Check
# =============================================================================

echo -e "${YELLOW}Verificando módulos Python...${NC}"

python3 -c "import gi" 2>/dev/null && echo -e "  ${GREEN}✓${NC} gi (PyGObject)" || echo -e "  ${RED}✗${NC} gi (PyGObject)"
python3 -c "from gi.repository import Gtk" 2>/dev/null && echo -e "  ${GREEN}✓${NC} Gtk" || echo -e "  ${RED}✗${NC} Gtk"
python3 -c "from gi.repository import Adw" 2>/dev/null && echo -e "  ${GREEN}✓${NC} Adw (libadwaita)" || echo -e "  ${RED}✗${NC} Adw (libadwaita)"
python3 -c "from gi.repository import GLib" 2>/dev/null && echo -e "  ${GREEN}✓${NC} GLib" || echo -e "  ${RED}✗${NC} GLib"

echo ""

# =============================================================================
# Kernel Module Check
# =============================================================================

echo -e "${YELLOW}Verificando módulo do kernel...${NC}"

if lsmod | grep -q "v4l2loopback"; then
    echo -e "  ${GREEN}✓${NC} v4l2loopback (carregado)"
else
    echo -e "  ${YELLOW}○${NC} v4l2loopback (não carregado - será carregado quando necessário)"
fi

echo ""

# =============================================================================
# Installation
# =============================================================================

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo -e "${GREEN}Todas as dependências estão instaladas!${NC}"
else
    echo -e "${YELLOW}Pacotes faltando: ${MISSING_PACKAGES[*]}${NC}"
    echo ""
    
    read -p "Deseja instalar os pacotes faltando? [S/n] " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Ss]$ ]] || [[ -z $REPLY ]]; then
        echo -e "${BLUE}Instalando pacotes...${NC}"
        
        if [ "$PKG_MANAGER" == "pacman" ]; then
            sudo pacman -S --needed "${MISSING_PACKAGES[@]}"
        elif [ "$PKG_MANAGER" == "yay" ]; then
            yay -S --needed "${MISSING_PACKAGES[@]}"
        elif [ "$PKG_MANAGER" == "paru" ]; then
            paru -S --needed "${MISSING_PACKAGES[@]}"
        else
            echo -e "${RED}Gerenciador de pacotes não suportado. Instale manualmente:${NC}"
            echo "  ${MISSING_PACKAGES[*]}"
            exit 1
        fi
        
        echo ""
        echo -e "${GREEN}Instalação concluída!${NC}"
    else
        echo -e "${YELLOW}Instalação cancelada.${NC}"
        exit 0
    fi
fi

# =============================================================================
# Post-Installation Setup
# =============================================================================

echo ""
echo -e "${BLUE}Configuração pós-instalação...${NC}"

# Check if user is in video group
if groups | grep -q "video"; then
    echo -e "  ${GREEN}✓${NC} Usuário está no grupo 'video'"
else
    echo -e "  ${YELLOW}!${NC} Adicionando usuário ao grupo 'video'..."
    sudo usermod -aG video "$USER"
    echo -e "  ${YELLOW}!${NC} Você precisa fazer logout e login novamente para aplicar."
fi

# Create udev rule for camera access (if not exists)
UDEV_RULE="/etc/udev/rules.d/90-libgphoto2.rules"
if [ -f "$UDEV_RULE" ]; then
    echo -e "  ${GREEN}✓${NC} Regra udev para libgphoto2 já existe"
else
    echo -e "  ${YELLOW}!${NC} Criando regra udev para acesso à câmera..."
    # This is usually handled by libgphoto2 package, but just in case
    sudo /usr/lib/libgphoto2/print-camera-list udev-rules version 201 > /tmp/90-libgphoto2.rules 2>/dev/null || true
    if [ -s /tmp/90-libgphoto2.rules ]; then
        sudo mv /tmp/90-libgphoto2.rules "$UDEV_RULE"
        sudo udevadm control --reload-rules
        echo -e "  ${GREEN}✓${NC} Regra udev criada"
    else
        echo -e "  ${YELLOW}○${NC} Regra udev não criada (geralmente não é necessário)"
    fi
fi

# =============================================================================
# Final Status
# =============================================================================

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}Instalação finalizada!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Para executar o aplicativo:"
echo -e "  ${GREEN}python3 canon_webcam_controller.py${NC}"
echo ""
echo -e "Notas importantes:"
echo -e "  • Conecte sua câmera via USB antes de iniciar"
echo -e "  • A câmera deve estar ligada"
echo -e "  • O módulo v4l2loopback será carregado automaticamente"
echo -e "  • Pode ser necessário reiniciar após a primeira instalação"
echo ""

# Check if camera is connected right now
echo -e "${YELLOW}Verificando câmera conectada...${NC}"
if command_exists gphoto2; then
    CAMERA=$(gphoto2 --auto-detect 2>/dev/null | tail -n +3 | head -1)
    if [ -n "$CAMERA" ]; then
        echo -e "  ${GREEN}✓${NC} Câmera detectada: $CAMERA"
    else
        echo -e "  ${YELLOW}○${NC} Nenhuma câmera detectada no momento"
    fi
else
    echo -e "  ${RED}✗${NC} gphoto2 não está instalado"
fi

echo ""
