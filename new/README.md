# GPhoto2 Webcam Controller

Aplicativo GTK4/Adwaita para controlar câmeras digitais compatíveis com gphoto2 como webcam no Linux.

## Funcionalidades

- **Modo Webcam**: Transmite a visualização ao vivo da câmera como um dispositivo de vídeo virtual
- **Tirar Foto**: Captura fotos diretamente da câmera com nomes sequenciais
- **Detecção Automática**: Detecta automaticamente o modelo da câmera conectada
- **Logs em Tempo Real**: Exibe estatísticas do ffmpeg e status da transmissão
- **Persistência de Sessão**: Reconecta a sessões de webcam em background após reiniciar o app

## Câmeras Suportadas

O aplicativo suporta todas as câmeras compatíveis com libgphoto2 que possuem suporte a LiveView/Webcam, incluindo:

- **Canon**: EOS (1000D, 1100D, 1200D, 1300D, 40D, 450D, 50D, 500D, 550D, 60D, 600D, 650D, 5D, 6D, 7D, 70D, 700D, 750D, 80D, M series, R series), PowerShot (A, G, S, SD, SX series)
- **Nikon**: D series (D40, D50, D60, D70, D80, D90, D200, D300, D700, D800, D3, D4, etc.), Z series, CoolPix
- **Sony**: Alpha series (A7, A6000, A5100, A6300, A6500, A77, etc.), DSC RX series
- **Fuji**: X-T series, X-Pro, X-H, GFX series
- **Olympus**: E-M series, C series
- **Panasonic**: GH5, GX8

Consulte a [lista completa de câmeras suportadas](http://www.gphoto.org/proj/libgphoto2/support.php).

## Requisitos

### Arch Linux / Manjaro / EndeavourOS

Execute o instalador incluído:

```bash
./install-archlinux.sh
```

### Dependências Manuais

| Pacote | Descrição |
|--------|-----------|
| `gphoto2` | Utilitário de linha de comando para controle de câmeras |
| `libgphoto2` | Biblioteca para acesso PTP/MTP |
| `ffmpeg` | Processamento e streaming de vídeo |
| `v4l2loopback-dkms` | Módulo kernel para dispositivo de vídeo virtual |
| `python` | Python 3.x |
| `python-gobject` | Bindings Python para GObject/GTK |
| `gtk4` | Toolkit GTK4 |
| `libadwaita` | Biblioteca Adwaita para apps GNOME modernos |
| `linux-headers` | Headers do kernel para compilação DKMS |

### Pacotes Opcionais

| Pacote | Descrição |
|--------|-----------|
| `v4l-utils` | Utilitários Video4Linux (v4l2-ctl) |

## Uso

1. Conecte sua câmera via USB
2. Ligue a câmera
3. Execute o aplicativo:

```bash
python3 canon_webcam_controller.py
```

### Modo Webcam

1. Clique em **"Iniciar Modo Webcam"**
2. Confirme o aviso para posicionar a câmera
3. Aguarde o carregamento dos drivers (pode pedir senha)
4. A câmera estará disponível como `/dev/videoX`

Use a webcam em outros aplicativos (OBS, Teams, Zoom, etc.) selecionando o dispositivo de vídeo virtual.

### Tirar Foto

1. Clique em **"Tirar Foto"**
2. Confirme a posição da câmera
3. A foto será salva como `captXXXX.jpg` no diretório atual
4. Opção para abrir a foto após captura

## Estrutura de Arquivos

```
.
├── canon_webcam_controller.py  # Aplicativo principal
├── run_webcam.sh               # Script auxiliar para streaming
├── install-archlinux.sh        # Instalador para Arch Linux
└── README.md                   # Este arquivo
```

## Solução de Problemas

### "Não foi possível contactar o dispositivo USB"

O processo `gvfs-gphoto2-volume-monitor` pode estar bloqueando a câmera. O aplicativo tenta matá-lo automaticamente, mas você pode fazer manualmente:

```bash
pkill -f gvfs-gphoto2-volume-monitor
```

### "Câmera não detectada"

1. Verifique se a câmera está ligada
2. Verifique a conexão USB
3. Execute `gphoto2 --auto-detect` para diagnóstico

### Módulo v4l2loopback não carrega

```bash
sudo modprobe v4l2loopback exclusive_caps=1 max_buffer=2
```

Se persistir, verifique se os headers do kernel estão instalados:

```bash
sudo pacman -S linux-headers
```

## Licença

Este projeto é de código aberto sob a licença MIT.

## Créditos

- [gphoto2](http://www.gphoto.org/) - Controle de câmeras
- [libgphoto2](https://github.com/gphoto/libgphoto2) - Biblioteca de suporte
- [v4l2loopback](https://github.com/umlaeute/v4l2loopback) - Dispositivo de vídeo virtual
