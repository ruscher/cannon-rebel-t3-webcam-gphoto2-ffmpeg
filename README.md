# Big Digi Cam

Um aplicativo poderoso e elegante para transformar sua câmera digital profissional (DSLR/Mirrorless) em uma webcam de alta qualidade no Linux ou controlá-la para fotografias remotas.

Desenvolvido por **Rafael Ruscher** (BigLinux Team).
Contato: [rruscher@gmail.com](mailto:rruscher@gmail.com)

Projetado e otimizado para **BigLinux**, **Manjaro**, **Arch Linux** e distribuições baseadas.

![License](https://img.shields.io/badge/license-GPL3-blue.svg) ![Platform](https://img.shields.io/badge/platform-Linux-green.svg) ![Python](https://img.shields.io/badge/python-3.10+-yellow.svg)

## 🚀 Funcionalidades

- **Webcam Profissional**: Utilize a qualidade ótica da sua câmera em reuniões (Zoom, Meet, Teams) ou transmissões (OBS Studio).
- **Controle Fotográfico**: Capture fotos diretamente pelo computador com pré-visualização.
- **Detecção Inteligente**: Identifica automaticamente sua câmera e ajusta as melhores configurações.
- **Interface Moderna**: UI baseada em **GTK4 + Libadwaita**, completamente integrada ao tema do sistema (Dark/Light).
- **Tradução**: Suporte a múltiplos idiomas (Internacionalização via `.po` files).
- **Zero Config**: Instalação e configuração automáticas de drivers (`v4l2loopback`) e dependências.

## 📦 Instalação

O instalador automático cuida de tudo para você em sistemas baseados no Arch Linux.

1. Clone o repositório ou baixe o código.
2. Execute o instalador:

```bash
chmod +x script/install-archlinux.sh
./script/install-archlinux.sh
```

**Dependências instaladas automaticamente:**
`gphoto2`, `libgphoto2`, `ffmpeg`, `v4l2loopback-dkms`, `python-gobject`, `gtk4`, `libadwaita`, `linux-headers`.

## 🎮 Uso

Após a instalação, você pode iniciar o aplicativo pelo menu do sistema ou via terminal:

```bash
python3 main.py
```

### Modo Webcam 🎥
1. Conecte sua câmera USB e ligue-a.
2. Aguarde a detecção automática no cabeçalho do app.
3. Clique no botão de Gravação/Webcam.
4. O app criará um dispositivo `/dev/video*` virtual.
5. Abra seu OBS ou Google Meet e selecione a câmera "Canon DSLR Webcam" (ou nome similar).

### Modo Foto 📸
1. Alterne para a aba "Foto".
2. Clique no botão de captura.
3. A foto será baixada e salva automaticamente na pasta do aplicativo e uma miniatura aparecerá para visualização rápida.

## 📷 Dispositivos Compatíveis

O Big Digi Cam utiliza a poderosa biblioteca `libgphoto2` no backend. Atualmente, o projeto é testado e validado principalmente com câmeras **Canon EOS**, mas suporta uma vasta gama de dispositivos que possuam funcionalidade "LiveView".

### Lista Resumida de Compatibilidade

#### Canon (Suporte Excelente)
- **DSLR EOS**: 1000D, 1100D, 1200D, 1300D, 2000D, 4000D
- **Série Rebel**: T3, T3i, T4i, T5, T5i, T6, T6i, T7, T7i, T8i, SL1, SL2, SL3
- **Série Semi-Pro/Pro**: 40D, 50D, 60D, 70D, 77D, 80D, 90D, 7D, 7D Mark II
- **Full Frame**: 5D Mark II/III/IV, 6D, 6D Mark II, 1D X series
- **Mirrorless (EOS M/R)**: M50, M50 MkII, M5, M6, R, RP, R5, R6, R7, R10

#### Nikon (Suporte Muito Bom)
- **Série D**: D3000-D3500, D5000-D5600, D7000-D7500
- **Full Frame**: D600, D610, D750, D780, D800, D810, D850
- **Mirrorless Z**: Z5, Z6, Z7, Z30, Z50, Zfc, Z9

#### Sony (Suporte Bom - Requer Modo "PC Remote" ativado)
- **Alpha**: A7 series (II, III, IV), A7R series, A7S series
- **APS-C**: A6000, A6100, A6300, A6400, A6500, A6600
- **Compactas**: RX100 series (alguns modelos), ZV-1, ZV-E10

#### Fujifilm (Suporte Variável)
- X-T series (X-T1 a X-T5), X-Pro2/3, X-H1/H2, GFX series.

#### Panasonic / Olympus / Outros
- Muitos modelos suportados, verifique a lista completa abaixo.

---
---
🔗 **Lista Oficial e Completa:** Para verificar se seu modelo específico é suportado, consulte: [gphoto2 Supported Cameras](http://www.gphoto.org/proj/libgphoto2/support.php)

## 📁 Estrutura de Arquivos

```
.
├── main.py                     # Aplicativo principal
├── script/                     # Scripts auxiliares
│   ├── run_webcam.sh           # Script auxiliar para streaming
│   └── install-archlinux.sh    # Instalador para Arch Linux
└── README.md                   # Este arquivo
```

## 🛠️ Suporte e Contribuição

Encontrou um bug ou tem uma sugestão?
Abra uma issue no nosso repositório ou entre em contato.

**Autor**: Rafael Ruscher
**E-mail**: rruscher@gmail.com
**Projeto**: BigLinux

## ⚖️ Licença

Distribuído sob a licença GPLv3. Veja o arquivo `LICENSE` para mais informações.
