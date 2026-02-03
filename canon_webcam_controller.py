#!/usr/bin/env python3
import sys
import subprocess
import os
import signal
import gi
import re
import glob

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

class WebcamApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.ruscher.WebcamCanonT3',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.process = None
        self.log("Aplicação iniciada.")
        
        # Setup Dark Mode
        manager = Adw.StyleManager.get_default()
        manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_title("Canon Rebel T3 Controller")
        self.win.set_default_size(500, 450)

        # Create ToastOverlay
        self.toast_overlay = Adw.ToastOverlay()
        self.win.set_content(self.toast_overlay)

        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Main Content Box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_margin_top(32)
        content_box.set_margin_bottom(32)
        content_box.set_margin_start(32)
        content_box.set_margin_end(32)
        content_box.set_valign(Gtk.Align.CENTER)
        
        toolbar_view.set_content(content_box)

        # Title
        title_label = Gtk.Label(label="Canon Rebel T3")
        title_label.set_css_classes(["title-2"])
        content_box.append(title_label)

        # Status Label
        self.status_label = Gtk.Label(label="Pronto")
        self.status_label.set_css_classes(["title-4", "dim-label"])
        content_box.append(self.status_label)

        # Buttons Box
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.append(btn_box)
        
        self.btn_photo = Gtk.Button(label="Tirar Foto")
        self.btn_photo.set_css_classes(["pill", "suggested-action"])
        self.btn_photo.set_size_request(-1, 55)
        self.btn_photo.connect("clicked", self.on_photo_clicked)
        btn_box.append(self.btn_photo)

        self.btn_video = Gtk.Button(label="Iniciar Modo Webcam")
        self.btn_video.set_css_classes(["pill", "suggested-action"])
        self.btn_video.set_size_request(-1, 55)
        self.btn_video.connect("clicked", self.on_video_clicked)
        btn_box.append(self.btn_video)

        self.btn_stop = Gtk.Button(label="Parar Webcam")
        self.btn_stop.set_css_classes(["pill", "destructive-action"])
        self.btn_stop.set_size_request(-1, 55)
        self.btn_stop.connect("clicked", self.on_stop_clicked)
        self.btn_stop.set_visible(False)
        btn_box.append(self.btn_stop)

        # Instructions Label
        # Log View (TextView in ScrolledWindow)
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.set_cursor_visible(False)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.log_view)
        scrolled.set_min_content_height(140)
        scrolled.set_vexpand(True)
        
        # Frame/border style
        scrolled.set_has_frame(True)
        
        content_box.append(scrolled)
        
        self.log("Pronto. Aguardando comando...")

        self.win.present()
        
        # Check for background session
        self.check_existing_session()

    def check_existing_session(self):
        try:
            # Check if run_webcam.sh is running
            res = subprocess.run(["pgrep", "-f", "run_webcam.sh"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                pids = res.stdout.strip().replace('\n', ' ')
                self.log(f"Sessão anterior detectada (PIDs: {pids}).")
                self.log("Logs em tempo real não podem ser recuperados, mas o controle foi restaurado.")
                
                # Restore UI state: Hide start, disable photo, show stop
                self.btn_video.set_visible(False)
                self.btn_photo.set_sensitive(False)
                self.btn_stop.set_visible(True)
                
                self.status_label.set_label("Webcam em execução (fundo)")
                
                # Start watching the log file
                self.start_log_watcher()
        except Exception as e:
            self.log(f"Erro ao verificar sessão: {e}")

    def start_log_watcher(self):
        try:
            # Kill previous watcher if exists (not the webcam process, just the tail)
            if hasattr(self, 'log_process') and self.log_process:
                self.log_process.kill()
        except:
            pass

        try:
             # Use tail -F to watch the log file (retry/follow name to handle truncation)
             self.log_process = subprocess.Popen(
                 ["tail", "-F", "-n", "50", "/tmp/canon_webcam_stream.log"],
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 bufsize=0
             )
             
             GLib.io_add_watch(
                self.log_process.stdout.fileno(),
                GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                self.on_process_output
            )
        except Exception as e:
             self.log(f"Erro ao iniciar watcher de log: {e}")

    def on_photo_clicked(self, btn):
        self.show_confirmation(
            "Modo Foto",
            "ATENÇÃO: Coloque a câmera na posição de fotografia.",
            self.do_wait_and_take_photo
        )

    def do_wait_and_take_photo(self):
        if self.ensure_camera_ready():
            self.do_take_photo()

    def ensure_camera_ready(self):
        """Checks connections and kills interfering processes."""
        self.log("Liberando recursos da câmera...")
        
        # 1. Kill gvfs-gphoto2-volume-monitor
        try:
             # Using pkill to ensure we catch all instances
             self.log("Matando gvfs-gphoto2-volume-monitor...")
             subprocess.run(["pkill", "-f", "gvfs-gphoto2-volume-monitor"], check=False)
             
             # Also try to unmount if any gphoto2 mounts exist (generic attempt)
             subprocess.run("gio mount -u gphoto2://* 2>/dev/null", shell=True, check=False)
        except Exception as e:
             self.log(f"Erro ao tentar limpar processos: {e}")
        
        # Give it a moment to release
        import time
        time.sleep(2)

        # 2. Check if camera is detected
        try:
            self.log("Listando dispositivos USB (lsusb):")
            lsusb_out = subprocess.getoutput("lsusb")
            self.log(lsusb_out)

            self.log("Verificando câmera (auto-detect)...")
            output = subprocess.check_output(["gphoto2", "--auto-detect"], text=True)
            self.log(f"Saída gphoto2:\n{output.strip()}")
            
            # Match strictness of bash script: Only fail if "No camera found" is explicitly stated.
            # The bash script uses `grep -q "No camera found"` on stdout. If it's an empty list, it proceeds.
            if "No camera found" in output:
                self.log("Erro explícito: Câmera não encontrada.")
                self.show_error("Nenhuma câmera detectada.\nVerifique a conexão USB e se a câmera está ligada.")
                self.status_label.set_label("Câmera não encontrada.")
                return False
            
            lines = output.strip().split('\n')
            if len(lines) < 3:
                self.log("Avis: Lista de câmeras vazia, mas prosseguindo conforme script original...")
            
            return True

        except FileNotFoundError:
            self.show_error("gphoto2 não está instalado.")
            return False
        except subprocess.CalledProcessError:
            # If auto-detect fails, connection is really bad
            self.show_error("Erro ao comunicar com a câmera via gphoto2.")
            return False
        
        return True

    def get_next_filename(self):
        # find the next available file index
        files = glob.glob("capt*.jpg")
        max_idx = 0
        for f in files:
            # extract number from filename "capt0001.jpg"
            try:
                # remove prefix 'capt' and suffix '.jpg'
                num_part = f[4:-4]
                idx = int(num_part)
                if idx > max_idx:
                    max_idx = idx
            except:
                pass
        
        return f"capt{max_idx+1:04d}.jpg"

    def do_take_photo(self):
        try:
            self.status_label.set_label("Capturando foto...")
            
            # Force kill interfering processes immediately before capture
            self.log("Forçando liberação de USB antes da captura...")
            subprocess.run(["pkill", "-f", "gvfs-gphoto2-volume-monitor"], check=False)
            
            # Give it time to die and release USB
            time.sleep(2)
            
            target_filename = self.get_next_filename()
            self.log(f"Nome do arquivo alvo: {target_filename}")
            
            self.log("Chamando gphoto2 (timeout 20s)...")
            
            # Use explicit filename to ensure sequence
            result = subprocess.run(
                ["gphoto2", "--capture-image-and-download", "--filename", target_filename, "--force-overwrite"], 
                check=True, 
                capture_output=True, 
                text=True,
                timeout=20
            )
            output = result.stdout
            
            self.log(f"[DEBUG] Raw Output:\n{output}")
            
            # Parse filename (Portuguese or English)
            # Output example: "Salvando arquivo como capt0000.jpg"
            filename = None
            
            # Regex explanation:
            # (?:...) -> Non-capturing group for the prefix
            # \s+    -> One or more spaces
            # ([^\s\r\n]+) -> Capture group 1: One or more characters that are NOT whitespace or newlines
            match = re.search(r"(?:Salvando arquivo como|Saving file as)\s+([^\s\r\n]+)", output)

            if match:
                raw_filename = match.group(1).strip()
                # Remove trailing dots or weird chars if any
                raw_filename = raw_filename.rstrip(".")
                
                # Check extension
                if not raw_filename.lower().endswith((".jpg", ".jpeg")):
                    filename = f"{raw_filename}.jpg"
                else:
                    filename = raw_filename
                self.log(f"[DEBUG] Filename matched: '{filename}'")
            else:
                 # If regex fails, we trust our target_filename if it exists
                 if os.path.exists(target_filename):
                     self.log(f"[DEBUG] Usando nome de arquivo alvo: {target_filename}")
                     filename = target_filename
                 else:
                     self.log("[DEBUG] Regex falhou e arquivo alvo não encontrado. Tentando fallback glob...")
                     try:
                         # Fallback specific to our forced pattern
                         list_of_files = glob.glob('capt*.jpg')
                         if list_of_files:
                             latest_file = max(list_of_files, key=os.path.getctime)
                             self.log(f"[DEBUG] Fallback encontrou: {latest_file}")
                             filename = latest_file
                     except Exception as e:
                         self.log(f"[DEBUG] Fallback erro: {e}")
            
            self.status_label.set_label("Foto salva na pasta atual.")
            self.show_toast("Foto capturada com sucesso!")
            
            if filename:
                 self.ask_open_photo(filename)
                 
        except subprocess.TimeoutExpired:
            self.log("Timeout! gphoto2 demorou demais.")
            self.status_label.set_label("Timeout na captura.")
            self.show_error("Timeout: A câmera demorou demais para responder.\nTente desligar e ligar a câmera novamente.")
                 
        except subprocess.CalledProcessError as e:
            self.status_label.set_label("Erro na captura.")
            error_details = e.stderr if e.stderr else str(e)
            self.log(f"Erro gphoto2 stderr: {error_details}")
            self.show_error(f"Erro ao capturar foto.\n\nDetalhes:\n{error_details}")
        except FileNotFoundError:
             self.show_error("Erro: 'gphoto2' não encontrado no sistema.")

    def on_video_clicked(self, btn):
        self.show_confirmation(
            "Modo Vídeo",
            "ATENÇÃO: Coloque a câmera na posição de filmagem.\n\nIsso carregará os drivers necessários via 'bigsudo' (pode pedir senha).",
            self.do_start_video
        )

    def do_start_video(self):
        self.status_label.set_label("Iniciando via script...")
        self.log("=== Iniciando via run_webcam.sh ===")
        
        # Determine path to script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_webcam.sh")
        
        try:
            # Run the wrapper script
            # setsid ensures we can kill the whole group (script + ffmpeg + gphoto2) later
            # We capture stdout/stderr to show ffmpeg stats. 
            # bufsize=0 ensures we get updates immediately (essential for \r updates from ffmpeg)
            self.process = subprocess.Popen(
                [script_path], 
                shell=False, 
                preexec_fn=os.setsid
                # stdout/stderr are now handled by the script -> file
            )
            self.log(f"Script iniciado. PID: {self.process.pid}")
            
            # Start watching the file
            self.start_log_watcher()
            
            self.btn_video.set_visible(False)
            self.btn_photo.set_sensitive(False)
            self.btn_stop.set_visible(True)
            self.show_toast("Webcam Iniciada!")
            
        except Exception as e:
            self.log(f"Erro ao lançar script: {e}")
            self.show_error(f"Erro ao iniciar script: {e}")
            self.status_label.set_label("Erro.")

    def on_process_output(self, fd, condition):
        if condition & GLib.IO_IN:
            try:
                # Read available data
                chunk = os.read(fd, 1024)
                if not chunk:
                    return False # EOF
                
                text = chunk.decode('utf-8', errors='replace')
                
                # Replace carriage returns with newlines so they appear in the log
                # instead of being invisible or weird
                text = text.replace('\r', '\n')
                
                # Rename Model for user preference
                text = text.replace("EOS 1100D", "Rebel T3")
                
                end_iter = self.log_buffer.get_end_iter()
                self.log_buffer.insert(end_iter, text)
                self.scroll_log_to_bottom()
                        
            except Exception as e:
                pass
            return True
        return False

    def on_stop_clicked(self, btn):
        self.log("Parando webcam...")
        
        # 1. Kill explicit child process if we have it
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process = None
            except ProcessLookupError:
                pass
            except Exception as e:
                self.log(f"Erro ao matar processo filho: {e}")

        # 2. General cleanup to catch background/dangling sessions
        try:
            subprocess.run(["pkill", "-f", "run_webcam.sh"], check=False)
            # Kill the ffmpeg pipeline explicitly just in case
            subprocess.run(["pkill", "-f", "ffmpeg -i - -r 30"], check=False)
             # And gphoto2
            subprocess.run(["pkill", "-f", "gphoto2 --stdout"], check=False)
        except Exception as e:
             self.log(f"Erro limpeza geral: {e}")
        
        self.status_label.set_label("Webcam Parada")
        self.log("Webcam Parada.")
        self.btn_video.set_visible(True)
        self.btn_photo.set_sensitive(True)
        self.btn_stop.set_visible(False)
        self.show_toast("Webcam Parada.")

    def show_confirmation(self, title, body, callback):
        # Adw.MessageDialog is deprecated, using Adw.AlertDialog
        dialog = Adw.AlertDialog(
            heading=title,
            body=body
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("confirm", "Continuar")
        dialog.set_default_response("confirm")
        dialog.set_close_response("cancel")
        
        def on_response(dialog, result):
            try:
                response = dialog.choose_finish(result)
                self.log(f"Dialog response: {response}")
                if response == "confirm":
                    self.log("Confirmado. Executando callback...")
                    GLib.timeout_add(200, callback)
            except Exception as e:
                self.log(f"Erro no diálogo: {e}")
        
        dialog.choose(self.win, None, on_response)

    def ask_open_photo(self, filename):
        def on_response(dialog, result):
            try:
                response = dialog.choose_finish(result)
                if response == "open":
                    self.log(f"Abrindo arquivo: {filename}")
                    subprocess.run(["xdg-open", filename])
            except Exception as e:
                self.log(f"Erro ao abrir dialogo foto: {e}")

        dialog = Adw.AlertDialog(
            heading="Foto Capturada",
            body=f"A foto '{filename}' foi salva.\nDeseja abri-la agora?"
        )
        dialog.add_response("cancel", "Não")
        dialog.add_response("open", "Sim")
        dialog.set_default_response("open")
        dialog.set_close_response("cancel")
        dialog.choose(self.win, None, on_response)

    def show_error(self, message):
        self.log(f"Mostrando erro: {message}")
        dialog = Adw.AlertDialog(
            heading="Erro",
            body=message
        )
        dialog.add_response("close", "Fechar")
        dialog.choose(self.win, None, None)

    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)
        
    def log(self, msg):
        print(f"[WebcamController] {msg}", file=sys.stderr)
        
        # Also append to UI log
        if hasattr(self, 'log_buffer'):
            try:
                end_iter = self.log_buffer.get_end_iter()
                self.log_buffer.insert(end_iter, f"{msg}\n")
                self.scroll_log_to_bottom()
            except Exception:
                pass

    def scroll_log_to_bottom(self):
        # Auto-scroll
        if hasattr(self, 'log_view'):
             adj = self.log_view.get_vadjustment()
             if adj:
                 adj.set_value(adj.get_upper() - adj.get_page_size())

if __name__ == '__main__':
    import time # Import locally to avoid top-level issues if any
    app = WebcamApp()
    app.run(sys.argv)
