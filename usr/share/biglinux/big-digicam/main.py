import os
import sys

# Ensure the application directory is in the path for module imports
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

import subprocess
import signal
import gi
import re
import glob
import time

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf, Gst, GstVideo
from utils.i18n import _

# Initialize GStreamer
Gst.init(None)

class WebcamApp(Adw.Application):
    def __init__(self):
        # Unique application_id per instance so multiple windows are truly independent
        instance_id = os.getpid()
        super().__init__(application_id=f'org.biglinux.big_digicam.pid{instance_id}',
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        Gtk.Window.set_default_icon_name("big-digicam")
        self.process = None
        self.log_process = None
        self.camera_name = _("Nenhuma câmera detectada")
        self.camera_detected = False
        self.camera_list = []
        self.udp_port = 5000 + (instance_id % 1000)
        self.current_mode = "photo"  # "photo" or "video"
        self.last_photo = None
        self.my_video_device = None  # The /dev/videoX assigned to THIS instance
        self._hotplug_timer = None
        self.is_capturing = False # True if photo or webcam is starting/running
        self._detecting = False # Lock for detect_camera
        
        # Setup Style Manager correctly
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_default_size(702, 525)
        
        # Load local custom icons
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        base_dir = os.path.dirname(os.path.realpath(__file__))
        icons_dir = os.path.join(base_dir, "icons")
        if os.path.exists(icons_dir):
            icon_theme.add_search_path(icons_dir)
            
        Gtk.Window.set_default_icon_name("big-digicam")
        self.win.set_icon_name("big-digicam")
        
        # Detect camera first (will update UI on finish)
        self.detect_camera(callback=self._update_camera_dropdown)
        self.win.set_title(_("Big DigiCam"))
        
        # Main box
        # Main box with ToastOverlay
        # Main root overlay to allow top-aligned toasts over everything
        self.root_overlay = Gtk.Overlay()
        self.win.set_content(self.root_overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.root_overlay.set_child(main_box)
        
        # No Top Toast in Root Overlay


        
        # Apply CSS
        self.apply_css()
        
        # ===== HEADER BAR =====
        header = Adw.HeaderBar()
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        main_box.append(header)
        
        # InlineViewSwitcher with round style as title widget
        self.view_switcher = Adw.InlineViewSwitcher()
        self.view_switcher.set_display_mode(Adw.InlineViewSwitcherDisplayMode.ICONS)
        self.view_switcher.add_css_class("round")
        header.set_title_widget(self.view_switcher)
        
        # Right side - Menu button with hamburger menu
        menu_btn = self._create_menu_button()
        header.pack_end(menu_btn)
        
        # Left side - Camera Status
        self.camera_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        is_error = not self.camera_detected
        icon_name = "dialog-error-symbolic" if is_error else "emblem-ok-symbolic"
        style_class = "error" if is_error else "success"
        
        self.status_icon = Gtk.Image.new_from_icon_name(icon_name)
        self.status_icon.add_css_class(style_class)
        self.camera_status_box.append(self.status_icon)
        
        self.camera_model = Gtk.StringList()
        if self.camera_detected:
            for cam in self.camera_list:
                self.camera_model.append(cam['name'])
        else:
            self.camera_model.append(self.camera_name)
            
        self.camera_dropdown = Gtk.DropDown(model=self.camera_model)
        self.camera_dropdown.add_css_class(style_class)
        self.camera_dropdown.set_valign(Gtk.Align.CENTER)
        self.camera_status_box.append(self.camera_dropdown)
        self._last_camera_list = list(self.camera_list)
        
        header.pack_start(self.camera_status_box)
        
        # Progress Bar
        self.loading_bar = Gtk.ProgressBar()
        self.loading_bar.add_css_class("thin-progress")
        self.loading_bar.set_visible(False)
        main_box.append(self.loading_bar)
        
        # Toast code moved to overlay

        
        # ===== PREVIEW AREA WITH OVERLAY =====
        overlay = Gtk.Overlay()
        overlay.set_vexpand(True)
        main_box.append(overlay)
        
        # Preview frame (base layer)
        preview_frame = Gtk.Frame()
        preview_frame.set_css_classes(["preview-frame"])
        preview_frame.set_margin_start(12)
        preview_frame.set_margin_end(12)
        preview_frame.set_margin_bottom(12)
        preview_frame.set_margin_top(12)
        overlay.set_child(preview_frame)
        
        # Floating FPS OSD (top-right corner)
        self.fps_label = Gtk.Label(label="")
        self.fps_label.set_css_classes(["osd", "fps-osd"])
        self.fps_label.set_halign(Gtk.Align.END)
        self.fps_label.set_valign(Gtk.Align.START)
        self.fps_label.set_margin_top(20)
        self.fps_label.set_margin_end(20)
        self.fps_label.set_visible(False)
        overlay.add_overlay(self.fps_label)

        # ===== TOP TOAST (OVERLAY) =====
        self.top_toast_revealer = Gtk.Revealer()
        self.top_toast_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.top_toast_revealer.set_halign(Gtk.Align.CENTER)
        self.top_toast_revealer.set_valign(Gtk.Align.START)
        
        self.top_toast_box = Gtk.Box()
        self.top_toast_box.set_halign(Gtk.Align.CENTER)
        self.top_toast_box.set_margin_top(24) # Margin from top of overlay
        self.top_toast_revealer.set_child(self.top_toast_box)
        
        self.top_toast_label = Gtk.Label()
        self.top_toast_label.set_css_classes(["top-toast"])
        self.top_toast_box.append(self.top_toast_label)
        
        overlay.add_overlay(self.top_toast_revealer)
        
        # Floating toolbar (overlay layer)
        floating_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        floating_toolbar.set_css_classes(["floating-toolbar", "osd"])
        floating_toolbar.set_halign(Gtk.Align.CENTER)
        floating_toolbar.set_valign(Gtk.Align.END)
        floating_toolbar.set_margin_bottom(24)
        overlay.add_overlay(floating_toolbar)
        
        # Last photo thumbnail (circular)
        self.photo_thumbnail = Gtk.Button()
        self.photo_thumbnail.set_css_classes(["circular", "thumbnail-button"])
        self.photo_thumbnail.set_size_request(48, 48)
        self.photo_thumbnail.set_tooltip_text(_("Última foto"))
        self.photo_thumbnail.connect("clicked", self.on_thumbnail_clicked)
        
        # Use Adw.Avatar for better circular image handling
        self.thumbnail_avatar = Adw.Avatar(size=48, text="", show_initials=False)
        
        # Force 1:1 aspect ratio to ensure perfect circle
        aspect_frame = Gtk.AspectFrame(xalign=0.5, yalign=0.5, ratio=1.0, obey_child=False)
        aspect_frame.set_child(self.thumbnail_avatar)
        
        self.photo_thumbnail.set_child(aspect_frame)
        
        floating_toolbar.append(self.photo_thumbnail)
        
        # Main action button (Shutter)
        self.btn_action = Gtk.Button()
        self.btn_action.set_css_classes(["circular", "action-button"])
        self.btn_action.set_size_request(48, 48)
        self.btn_action.connect("clicked", self.on_action_clicked)
        floating_toolbar.append(self.btn_action)
        
        # Stop button (only visible during video)
        self.btn_stop = Gtk.Button()
        self.btn_stop.set_icon_name("media-playback-stop-symbolic")
        self.btn_stop.set_css_classes(["circular", "destructive-action"])
        self.btn_stop.set_size_request(52, 48)
        self.btn_stop.set_tooltip_text(_("Parar Webcam"))
        self.btn_stop.set_visible(False)
        self.btn_stop.connect("clicked", self.on_stop_clicked)
        floating_toolbar.append(self.btn_stop)
        
        # Stack for switching between photo preview and video status
        self.preview_stack = Adw.ViewStack()
        preview_frame.set_child(self.preview_stack)
        
        # Photo preview page
        photo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        photo_box.set_valign(Gtk.Align.CENTER)
        photo_box.set_halign(Gtk.Align.CENTER)
        
        self.photo_preview = Gtk.Picture()
        self.photo_preview.set_size_request(400, 300)
        self.photo_preview.set_content_fit(Gtk.ContentFit.CONTAIN)
        photo_box.append(self.photo_preview)
        

        
        # Use ViewStack for proper ViewSwitcher integration
        photo_page = self.preview_stack.add_titled(photo_box, "photo", _("Foto"))
        photo_page.set_icon_name("camera-photo-symbolic")
        
        # Video preview page with GStreamer
        video_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        video_box.set_vexpand(True)
        video_box.set_hexpand(True)
        
        # GStreamer video widget
        self.video_picture = Gtk.Picture()
        self.video_picture.set_vexpand(True)
        self.video_picture.set_hexpand(True)
        self.video_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        video_box.append(self.video_picture)
        
        video_page = self.preview_stack.add_titled(video_box, "video", _("Webcam"))
        video_page.set_icon_name("camera-video-symbolic")
        
        # Connect ViewSwitcher to Stack
        self.view_switcher.set_stack(self.preview_stack)
        self.preview_stack.connect("notify::visible-child-name", self.on_mode_changed)
        
        # GStreamer pipeline (initialized as None)
        self.gst_pipeline = None
        
        # Initialize UI state
        self.update_mode_ui()
        self.load_last_photo()
        
        self.win.present()
        
        # Check for background session
        self.check_existing_session()
        
        # Setup actions for menu
        self._setup_actions()
        
        # Start hot-plug detection (poll every 15 seconds, and it's async)
        self._hotplug_timer = GLib.timeout_add(15000, self._poll_cameras)

    def _create_menu_button(self):
        menu = Gio.Menu.new()
        section = Gio.Menu.new()
        section.append(_("Atualizar Câmeras"), "app.refresh")
        section.append(_("Abrir outra câmera (Nova Janela)"), "app.new_window")
        section.append(_("Sobre"), "app.about")
        section.append(_("Sair"), "app.quit")
        menu.append_section(None, section)
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(menu)
        menu_button.set_tooltip_text(_("Menu principal"))
        menu_button.set_css_classes(["flat"])
        return menu_button

    def _setup_actions(self):
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)
        new_window_action = Gio.SimpleAction.new("new_window", None)
        new_window_action.connect("activate", self._on_new_window)
        self.add_action(new_window_action)
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh)
        self.add_action(refresh_action)

    def _on_about(self, action=None, param=None):
        about = Adw.AboutDialog(
            application_name="Big DigiCam",
            application_icon="big-digicam",
            developer_name="BigLinux Team",
            version="1.0.0",
            comments=_("Transforme sua câmera digital em uma webcam profissional."),
            website="https://github.com/ruscher/cannon-rebel-t3-webcam-gphoto2-ffmpeg",
            issue_url="https://github.com/ruscher/cannon-rebel-t3-webcam-gphoto2-ffmpeg/issues",
            license_type=Gtk.License.GPL_3_0,
            copyright="© 2026 BigLinux Team",
        )
        
        # Original Authors
        about.add_credit_section(
            _("Autores Originais"),
            ["Rafael Ruscher", "Barnabé di Kartola"]
        )
        
        # Technologies
        about.add_credit_section(
            _("Tecnologias"),
            ["libgphoto2", "FFmpeg", "GStreamer", "v4l2loopback", "GTK4 / Libadwaita"]
        )
        
        about.present(self.win)

    def _on_refresh(self, action=None, param=None):
        self.show_toast(_("Buscando câmeras..."), "accent")
        self.detect_camera(callback=self._update_camera_dropdown)

    def _on_new_window(self, action=None, param=None):
        import sys
        subprocess.Popen([sys.executable, sys.argv[0]])

    def get_selected_camera_port(self):
        if not hasattr(self, 'camera_list') or not self.camera_list:
            return None
        selected_idx = self.camera_dropdown.get_selected()
        if selected_idx != Gtk.INVALID_LIST_POSITION and selected_idx < len(self.camera_list):
            return self.camera_list[selected_idx]['port']
        return None

    def _kill_my_processes(self):
        port = self.get_selected_camera_port()
        if port:
            subprocess.run(["pkill", "-f", f"gphoto2.*{port}"], check=False)
        else:
            subprocess.run(["pkill", "-f", "gphoto2 --stdout"], check=False)
        subprocess.run(["pkill", "-f", f"ffmpeg.*udp://127.0.0.1:{self.udp_port}"], check=False)

    def _on_quit(self, action=None, param=None):
        # Stop hot-plug polling
        if self._hotplug_timer:
            GLib.source_remove(self._hotplug_timer)
            self._hotplug_timer = None
        
        self.stop_video_preview()
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except:
                pass
        
        self._kill_my_processes()
        
        # Quit application
        self.quit()

    def apply_css(self):
        css = b"""
        .toolbar {
            background: alpha(@window_fg_color, 0.05);
            border-radius: 8px;
            padding: 6px;
        }
        
        .mode-button {
            min-width: 40px;
            min-height: 40px;
        }
        
        .mode-active {
            background: @accent_bg_color;
            color: @accent_fg_color;
        }
        
        .action-button {
            background: white;
            color: #333;
            border: 3px solid #666;
        }
        
        .action-button:hover {
            background: #eee;
        }
        
        .circular {
            border-radius: 999px;
            padding: 0;
            min-width: 48px;
            min-height: 48px;
        }

        .thumbnail-button {
            padding: 0;
            margin: 0;
            border: 2px solid white;
            min-width: 48px;
            min-height: 48px;
            border-radius: 999px;
            background: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        .preview-frame {
            background: #1a1a1a;
            border-radius: 12px;
            border: 1px solid alpha(@window_fg_color, 0.1);
        }
        
        .status-bar {
            padding: 8px;
            background: alpha(@window_fg_color, 0.03);
            border-radius: 6px;
        }
        
        .recording {
            background: #e01b24;
            animation: pulse 1s infinite;
        }
        
        .floating-toolbar {
            padding: 12px 20px;
            border-radius: 32px;
            background: alpha(@window_bg_color, 0.85);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        
        .fps-osd {
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            background: alpha(black, 0.7);
            color: #00ff00;
        }
        
        .top-toast {
            padding: 8px 18px;
            border-radius: 20px;
            background: #303030;
            color: white;
            font-weight: bold;
            box-shadow: 0 3px 10px rgba(0,0,0,0.3);
        }
        .top-toast.accent { background: @accent_bg_color; color: @accent_fg_color; }
        .top-toast.success { background: #26a269; color: white; }
        .top-toast.warning { background: #cd9309; color: white; }
        .top-toast.error { background: #e01b24; color: white; }
        
        .app-notification {
            padding: 8px 16px;
            font-weight: 500;
        }
        
        .app-notification.accent {
            background: @accent_bg_color;
            color: @accent_fg_color;
        }
        
        .app-notification.success {
            background: #26a269;
            color: white;
        }
        
        .app-notification.warning {
            background: #e5a50a;
            color: black;
        }
        
        .app-notification.error {
            background: #e01b24;
            color: white;
        }
        
        .accent { color: @accent_bg_color; font-weight: bold; }
        .error { color: #e01b24; font-weight: bold; }
        .thin-progress > trough {
            min-height: 2px;
            background-color: transparent;
            box-shadow: none;
            border: none;
        }
        
        .thin-progress > trough > progress {
            min-height: 2px;
            border-radius: 999px;
            background-color: @accent_bg_color;
        }
        """
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def update_mode_ui(self):
        if self.is_capturing:
            self.btn_action.set_sensitive(False)
        else:
            self.btn_action.set_sensitive(True)

        if self.current_mode == "photo":
            self.btn_action.set_icon_name("camera-photo-symbolic")
            self.preview_stack.set_visible_child_name("photo")
        else:
            self.btn_action.set_icon_name("media-record-symbolic")
            self.preview_stack.set_visible_child_name("video")

    def on_mode_changed(self, stack, param):
        page_name = stack.get_visible_child_name()
        if page_name == "photo":
            self.current_mode = "photo"
            self.btn_action.set_icon_name("camera-photo-symbolic")
            if not self.is_capturing:
                self.btn_action.set_sensitive(True)
            self.fps_label.set_visible(False)
        else:
            self.current_mode = "video"
            self.btn_action.set_icon_name("media-record-symbolic")
            if not self.is_capturing:
                self.btn_action.set_sensitive(True)

    def on_action_clicked(self, btn):
        if self.is_capturing:
            return
        if self.current_mode == "photo":
            self.take_photo()
        else:
            self.start_webcam()

    def on_thumbnail_clicked(self, btn):
        if self.last_photo and os.path.exists(self.last_photo):
            subprocess.run(["xdg-open", self.last_photo])

    def load_last_photo(self):
        try:
            files = glob.glob("capt*.jpg")
            if files:
                self.last_photo = max(files, key=os.path.getctime)
                self.photo_preview.set_filename(self.last_photo)
                try:
                    texture = Gdk.Texture.new_from_filename(self.last_photo)
                    self.thumbnail_avatar.set_custom_image(texture)
                except:
                    pass
        except Exception as e:
            pass

    def detect_camera(self, callback=None, retry=1):
        """Asynchronous camera detection to avoid blocking the UI."""
        if self._detecting:
            if callback: callback()
            return
        
        self._detecting = True
        
        def run_detection():
            self.camera_list = []
            try:
                # Be more aggressive killing GVFS
                print("[Detection] Killing GVFS and probing USB...")
                subprocess.run(["pkill", "-f", "gvfs-gphoto2-volume-monitor"], check=False)
                subprocess.run(["gio", "mount", "-u", "gphoto2://*"], capture_output=True, check=False)
                
                # Small wait for device release
                time.sleep(1.0)

                result = subprocess.run(
                    ["gphoto2", "--auto-detect"],
                    capture_output=True, text=True, timeout=10
                )
                output = result.stdout
                print(f"[Detection] Output:\n{output}")
                lines = output.strip().split('\n')
                for line in lines[2:]:
                    line = line.strip()
                    if line and 'usb:' in line:
                        parts = line.split('usb:')
                        if len(parts) >= 2:
                            name = parts[0].strip() or _("Câmera Genérica")
                            port = "usb:" + parts[1].strip()
                            self.camera_list.append({"name": name, "port": port})
                
                if self.camera_list:
                    self.camera_detected = True
                    self.camera_name = self.camera_list[0]['name']
                else:
                    self.camera_name = _("Câmera não detectada")
                    self.camera_detected = False
                    # Retry once if failed and not a manual request
                    if retry > 0:
                        self._detecting = False
                        GLib.idle_add(lambda: self.detect_camera(callback, retry=retry-1))
                        return

            except Exception as e:
                print(f"Detection error: {e}")
                self.camera_name = _("Câmera não detectada")
                self.camera_detected = False
            finally:
                self._detecting = False
                if callback:
                    GLib.idle_add(callback)

        import threading
        threading.Thread(target=run_detection, daemon=True).start()

    def _poll_cameras(self):
        """Periodically poll for USB camera changes (hot-plug detection)."""
        # CRITICAL: Skip polling if ANY capture or start-up process is active
        # OR if gphoto2 is already running (don't interfere with ourselves)
        if self.is_capturing or (hasattr(self, 'loading') and self.loading) or self._detecting:
            return True

        try:
            # Check for any active gphoto2 process
            res = subprocess.run(["pgrep", "-f", "gphoto2"], capture_output=True)
            if res.returncode == 0:
                return True
        except:
            pass

        old_ports = set(c['port'] for c in self.camera_list)
        
        def on_detection_done():
            new_ports = set(c['port'] for c in self.camera_list)
            if old_ports != new_ports:
                self._update_camera_dropdown()
        
        self.detect_camera(callback=on_detection_done)
        return True  # Keep polling

    def _update_camera_dropdown(self):
        """Rebuild the dropdown model with current camera_list."""
        # Safeguard: UI might not be ready yet
        if not hasattr(self, 'camera_dropdown') or self.camera_dropdown is None:
            return

        # Remember current selection
        old_selected = self.camera_dropdown.get_selected()
        old_port = None
        if hasattr(self, '_last_camera_list') and old_selected < len(self._last_camera_list):
            old_port = self._last_camera_list[old_selected]['port']
        
        # Rebuild model
        self.camera_model.splice(0, self.camera_model.get_n_items(), [])
        
        if self.camera_detected and self.camera_list:
            for cam in self.camera_list:
                self.camera_model.append(cam['name'])
            
            # Try to preserve selection
            new_idx = 0
            if old_port:
                for i, c in enumerate(self.camera_list):
                    if c['port'] == old_port:
                        new_idx = i
                        break
            self.camera_dropdown.set_selected(new_idx)
        else:
            self.camera_model.append(_("Nenhuma câmera detectada"))
            self.camera_dropdown.set_selected(0)
        
        self._last_camera_list = list(self.camera_list)
        
        # Update status icon
        is_error = not self.camera_detected
        icon_name = "dialog-error-symbolic" if is_error else "emblem-ok-symbolic"
        style_class = "error" if is_error else "success"
        
        # Clear old classes
        self.status_icon.set_css_classes([])
        self.status_icon.set_from_icon_name(icon_name)
        self.status_icon.add_css_class(style_class)
        
        self.camera_dropdown.set_css_classes([])
        self.camera_dropdown.add_css_class(style_class)
        
        if self.camera_detected and not is_error:
            self.show_toast(_("Câmera detectada!"), "success")

    def check_existing_session(self):
        try:
            port = self.get_selected_camera_port()
            if not port:
                return
            
            # Check for a gphoto2 process specifically for THIS camera's port
            res = subprocess.run(["pgrep", "-af", f"gphoto2.*{port}"], capture_output=True, text=True)
            
            if res.returncode == 0 and res.stdout.strip():
                self.current_mode = "video"
                self.update_mode_ui()
                
                # Update state
                self.btn_action.set_visible(False)
                self.btn_stop.set_visible(True)
                
                self.show_toast(_("Sessão restaurada"), "accent")
                
                # Show status without trying preview (keeps v4l2loopback free for OBS)
                GLib.idle_add(self.show_webcam_active_status)
        except Exception as e:
            print(f"Erro ao verificar sessão: {e}")

    def take_photo(self):
        self.is_capturing = True
        self.btn_action.set_sensitive(False)
        self.set_loading(True)
        
        # Determine if webcam was running via our internal state or process check
        try:
            res = subprocess.run(["pgrep", "-f", "gphoto2.*stdout"], capture_output=True)
            was_webcam_running = res.returncode == 0
        except:
            was_webcam_running = False

        if was_webcam_running:
            self.show_toast(_("Parando webcam..."), "warning")
            self.stop_video_preview()
            self._kill_my_processes()
            time.sleep(3) # Wait for mirror to lower on T3
        
        self.current_mode = "photo"
        self.update_mode_ui()
        
        def do_capture():
            try:
                # 1. Radical cleanup of GVFS
                # We do this twice to ensure it doesn't respawn fast enough
                for i in range(2):
                    subprocess.run(["pkill", "-9", "-f", "gvfs-gphoto2-volume-monitor"], check=False)
                    subprocess.run(["gio", "mount", "-u", "gphoto2://*"], capture_output=True, check=False)
                
                # 2. Identify camera by MODEL NAME (more stable than dynamic ports)
                selected_idx = self.camera_dropdown.get_selected()
                camera_model_name = None
                if selected_idx != Gtk.INVALID_LIST_POSITION and selected_idx < len(self.camera_list):
                    camera_model_name = self.camera_list[selected_idx]['name']
                
                # If we don't have a model, we'll let gphoto2 auto-detect
                camera_arg = ["--camera", camera_model_name] if camera_model_name else []
                
                target_filename = self.get_next_filename()
                GLib.idle_add(lambda: self.show_toast(f"{_('Capturando')} {target_filename}...", "accent"))
                
                # 3. Capture command with retries
                success = False
                error_msg = ""
                
                # Retry loop for photography
                for attempt in range(2):
                    # For Canon, force viewfinder off before capture
                    if camera_model_name and "Canon" in camera_model_name:
                        subprocess.run(["gphoto2"] + camera_arg + ["--set-config", "viewfinder=0"], capture_output=True)
                    
                    result = subprocess.run(
                        ["gphoto2"] + camera_arg + ["--capture-image-and-download", "--filename", target_filename, "--force-overwrite", "--keep"],
                        capture_output=True, text=True, timeout=60
                    )
                    
                    if result.returncode == 0:
                        success = True
                        break
                    else:
                        error_msg = result.stderr or result.stdout
                        print(f"[Capture Attempt {attempt+1}] Failed: {error_msg}")
                        # If busy, try a hard reset of the USB bus (ONLY for Canon, Nikons freeze on reset)
                        if camera_model_name and "Canon" in camera_model_name:
                            subprocess.run(["gphoto2"] + camera_arg + ["--reset"], capture_output=True)
                            time.sleep(4) # Wait for re-registration
                        else:
                            time.sleep(2) # Just wait a bit for Nikons
                
                if success:
                    GLib.idle_add(self.on_photo_captured, target_filename)
                else:
                    GLib.idle_add(self.on_photo_error, error_msg)
                
            except subprocess.TimeoutExpired:
                GLib.idle_add(self.on_photo_error, _("Timeout - câmera demorou muito"))
            except Exception as e:
                GLib.idle_add(self.on_photo_error, str(e))
        
        import threading
        threading.Thread(target=do_capture, daemon=True).start()

    def on_photo_captured(self, filename):
        self.is_capturing = False
        self.btn_action.set_sensitive(True)
        self.last_photo = filename
        self.load_last_photo()
        self.set_loading(False)
        self.show_toast(f"{_('Foto salva:')} {filename}", "success")
        self.ask_open_photo(filename)
        return False

    def on_photo_error(self, error):
        self.is_capturing = False
        self.btn_action.set_sensitive(True)
        self.set_loading(False)
        self.show_toast(_("Erro ao capturar foto"), "error")
        print(f"[Photo Error] {error}")
        return False

    def get_next_filename(self):
        files = glob.glob("capt*.jpg")
        max_idx = 0
        for f in files:
            try:
                num_part = f[4:-4]
                idx = int(num_part)
                if idx > max_idx:
                    max_idx = idx
            except:
                pass
        return f"capt{max_idx+1:04d}.jpg"

    def start_webcam(self):
        self.is_capturing = True
        self.btn_action.set_sensitive(False)
        self.set_loading(True)
        self.show_toast(_("Iniciando webcam..."), "warning")
        self.btn_action.set_visible(False)
        self.btn_stop.set_visible(True)
        
        # Determine correct path relative to this script
        base_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(base_dir, "script", "run_webcam.sh")
        
        # Ensure it is executable
        if not os.access(script_path, os.X_OK):
            try:
                os.chmod(script_path, 0o755)
            except:
                pass
                
        def run_script_thread():
            try:
                port = self.get_selected_camera_port()
                port_arg = port if port else ""
                
                # Run the script and wait for it to finish (it waits for device ready)
                # We use subprocess.run so we block this thread until script exits
                res = subprocess.run(
                    [script_path, port_arg, str(self.udp_port)],
                    capture_output=True,
                    text=True
                )
                
                # Check retuncode
                if res.returncode == 0:
                    # Success path - script outputs "SUCCESS: /dev/videoX"
                    output = res.stdout.strip()
                    dev = None
                    for line in output.split('\n'):
                        if line.startswith('SUCCESS:'):
                            dev = line.split('SUCCESS:')[1].strip()
                            break
                    GLib.idle_add(self.on_webcam_started_success, dev)
                else:
                    # Failure path
                    # Capture stdout as well since run_webcam.sh logs there (exec 2>&1)
                    error_msg = res.stdout.strip() if res.stdout else res.stderr.strip()
                    if not error_msg:
                        error_msg = "Unknown Error (No Output)"
                        
                    print(f"Script failed: {error_msg}")
                    GLib.idle_add(self.on_webcam_started_error, error_msg)
                    
            except Exception as e:
                GLib.idle_add(self.on_webcam_started_error, str(e))

        import threading
        threading.Thread(target=run_script_thread, daemon=True).start()

    def on_webcam_started_success(self, video_device=None):
        self.set_loading(False)
        if video_device:
            self.my_video_device = video_device
        self.show_webcam_active_status()

    def show_webcam_active_status(self):
        # Use the device assigned by run_webcam.sh to THIS instance
        if self.my_video_device and os.path.exists(self.my_video_device):
            self.preview_device = self.my_video_device
        else:
            # Fallback: find last device
            devices = sorted(glob.glob("/dev/video*"))
            if not devices:
                return
            self.preview_device = devices[-1]
        
        # Try to start preview (with exclusive_caps=0, this should work)
        GLib.timeout_add(1000, self.start_video_preview)

    def on_webcam_started_error(self, error):
        self.is_capturing = False
        self.btn_action.set_sensitive(True)
        if "No camera" in error or "Nenhuma câmera" in error:
            self.show_toast(_("Erro: Nenhuma câmera localizada"), "error")
        else:
            self.show_toast(_("Erro ao iniciar webcam"), "error")
            
        print(f"[Webcam Error] {error}")
        self.btn_action.set_visible(True)
        self.btn_stop.set_visible(False)
        self.set_loading(False)

    def start_video_preview(self):
        self.set_loading(True)
        # self.show_toast("Aguardando stream...", "warning")
        
        # Determine device
        devices = sorted(glob.glob("/dev/video*"))
        if not devices:
            self.show_toast(_("Nenhum dispositivo"), "warning")
            self.set_loading(False)
            return
        self.preview_device = devices[-1]
        
        # Wait for device to be ready (ffmpeg needs time to start streaming)
        self._preview_retry_count = 0
        self._preview_max_retries = 30  # 30 * 500ms = 15 seconds max wait
        GLib.timeout_add(500, self._try_start_gst_preview)

    def _try_start_gst_preview(self):
        self._preview_retry_count += 1
        
        try:
            # Skip v4l2-ctl check which might fail if device is busy
            # Just verify if we have retried enough times to allow ffmpeg to start
            if self._preview_retry_count < 3: # Wait at least 1.5s
                # self.show_toast(f"Iniciando stream... ({self._preview_retry_count})", "warning")
                return True

            # Device ready or max retries reached, try to start
            self.use_opencv = False
            self.preview_active = True
            self.fps_counter = 0
            self.last_fps_time = time.time()
            
            # Try UDP stream (Guaranteed no conflict)
            # Using packetsize=1316 to match ffmpeg output
            pipeline_attempts = [
                # Try 1: Explicit MPEG-TS caps with localhost bind
                (
                    f"udpsrc port={self.udp_port} address=127.0.0.1 caps=\"video/mpegts,packetsize=(int)1316\" ! "
                    "queue max-size-bytes=2097152 ! "
                    "tsdemux ! "
                    "decodebin ! "
                    "videoconvert ! "
                    "video/x-raw,format=RGB ! "
                    "appsink name=sink emit-signals=True drop=True max-buffers=2 sync=False"
                ),
                # Try 2: Bind to ALL interfaces (0.0.0.0) just in case
                (
                    f"udpsrc port={self.udp_port} caps=\"video/mpegts,packetsize=(int)1316\" ! "
                    "queue max-size-bytes=2097152 ! "
                    "decodebin ! "
                    "videoconvert ! "
                    "video/x-raw,format=RGB ! "
                    "appsink name=sink emit-signals=True drop=True max-buffers=2 sync=False"
                ),
            ]
            
            for i, pipeline_str in enumerate(pipeline_attempts):
                try:
                    # print(f"[Preview] Tentando pipeline {i+1}...")
                    self.gst_pipeline = Gst.parse_launch(pipeline_str)
                    appsink = self.gst_pipeline.get_by_name("sink")
                    appsink.connect("new-sample", self.on_gst_sample_with_fps)
                    
                    bus = self.gst_pipeline.get_bus()
                    bus.add_signal_watch()
                    bus.connect("message::error", self.on_gst_error)
                    
                    # Try to start
                    ret = self.gst_pipeline.set_state(Gst.State.PLAYING)
                    if ret == Gst.StateChangeReturn.FAILURE:
                        print(f"[Preview] Pipeline {i+1} falhou ao iniciar")
                        self.gst_pipeline.set_state(Gst.State.NULL)
                        self.gst_pipeline = None
                        continue
                    
                    # Wait a bit to see if it errors immediately (MAX 2 seconds)
                    # Don't use CLOCK_TIME_NONE as it freezes the UI waiting for stream
                    ret, state, pending = self.gst_pipeline.get_state(2 * Gst.SECOND)
                    
                    if ret == Gst.StateChangeReturn.FAILURE:
                         print(f"[Preview] Pipeline {i+1} falhou state change")
                         self.gst_pipeline.set_state(Gst.State.NULL)
                         self.gst_pipeline = None
                         continue
                         
                    if state == Gst.State.PLAYING or ret == Gst.StateChangeReturn.SUCCESS or ret == Gst.StateChangeReturn.ASYNC:
                        # print(f"[Preview] Pipeline {i+1} iniciado (State: {state}, Ret: {ret})")
                        # self.show_toast(f"Preview ativo", "accent")
                        GLib.timeout_add(500, lambda: self.show_toast(_("Webcam disponível!"), "success") or False)
                        self.set_loading(False)
                        return False
                        
                except Exception as e:
                    print(f"[Preview] Pipeline {i+1} erro: {e}")
                    if self.gst_pipeline:
                        self.gst_pipeline.set_state(Gst.State.NULL)
                        self.gst_pipeline = None
                    continue
            
            # All pipelines failed - show message but don't block OBS
            print("[Preview] Todos pipelines falharam")
            # self.show_toast("Preview indisponível (OBS/Meet funcionam)", "warning")
            self.preview_active = False
            self.set_loading(False)
            # Alternative: Try OpenCV Fallback?
            # self.try_opencv_fallback()
            return False
            
        except Exception as e:
            if self._preview_retry_count < self._preview_max_retries:
                return True  # Retry
            self.show_toast("Preview indisponível", "warning")
            self.set_loading(False)
            return False

    def update_opencv_frame(self):
        if not self.preview_active or not hasattr(self, 'cap'):
            return False
            
        ret, frame = self.cap.read()
        if ret:
            # FPS Calc
            self.fps_counter += 1
            t = time.time()
            if t - self.last_fps_time >= 1.0:
                fps = self.fps_counter
                self.fps_counter = 0
                self.last_fps_time = t
                self.fps_label.set_label(f"FPS {fps}")
                # Only show FPS in video mode
                if self.current_mode == "video":
                    self.fps_label.set_visible(True)

            # Convert BGR to RGB
            # Frame is numpy array
            import cv2
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            h, w, ch = rgb_frame.shape
            data = rgb_frame.tobytes()
            glib_bytes = GLib.Bytes.new(data)
            
            self.update_texture(w, h, glib_bytes)
            
        return True # Keep calling

    def on_gst_sample_with_fps(self, sink):
        if not self.preview_active:
            return Gst.FlowReturn.ERROR
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.ERROR
        
        # FPS Calculation
        self.fps_counter += 1
        t = time.time()
        if t - self.last_fps_time >= 1.0:
            fps = self.fps_counter
            self.fps_counter = 0
            self.last_fps_time = t
            GLib.idle_add(lambda: self.fps_label.set_label(f"FPS {fps}") or self.fps_label.set_visible(self.current_mode == "video"))
        
        buf = sample.get_buffer()
        caps = sample.get_caps()
        s = caps.get_structure(0)
        w = s.get_value("width")
        h = s.get_value("height")
        result, map_info = buf.map(Gst.MapFlags.READ)
        if result:
            glib_bytes = GLib.Bytes.new(map_info.data)
            buf.unmap(map_info)
            GLib.idle_add(self.update_texture, w, h, glib_bytes)
        return Gst.FlowReturn.OK

    def on_gst_error(self, bus, msg):
        err, debug = msg.parse_error()
        print(f"[GStreamer Error] {err}: {debug}")
        self.show_toast("Erro no preview, tentando alternativa...", "warning")
        GLib.idle_add(self.try_opencv_fallback)

    def try_opencv_fallback(self):
        try:
            import cv2
            dev_idx = int(re.search(r'\d+$', self.preview_device).group())
            self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
            if self.cap.isOpened():
                self.use_opencv = True
                self.preview_active = True
                self.fps_counter = 0
                self.last_fps_time = time.time()
                GLib.timeout_add(33, self.update_opencv_frame)
                self.show_toast("Preview via OpenCV (acesso exclusivo)", "warning")
            else:
                self.show_toast("Falha no fallback OpenCV", "error")
        except Exception as e:
            self.show_toast(f"Fallback falhou: {e}", "error")


    def update_texture(self, w, h, glib_bytes):
        if not self.preview_active:
            return
            
        try:
            texture = Gdk.MemoryTexture.new(
                w, h, 
                Gdk.MemoryFormat.R8G8B8, 
                glib_bytes, 
                w * 3
            )
            self.video_picture.set_paintable(texture)
        except:
            pass

    def stop_video_preview(self):
        """Stop preview (OpenCV or GStreamer)."""
        self.preview_active = False
        self.fps_label.set_visible(False)
        
        # Stop OpenCV
        if hasattr(self, 'cap') and self.cap:
            self.cap.release()
            self.cap = None
        
        # Stop GStreamer
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.NULL)
            self.gst_pipeline = None
            
        self.video_picture.set_paintable(None)
    def on_stop_clicked(self, btn):
        self.is_capturing = False
        self.btn_action.set_sensitive(True)
        self.stop_video_preview()
        
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process = None
            except:
                pass

        # Only kill THIS instance's processes (not other cameras)
        self._kill_my_processes()
        self.my_video_device = None
        
        self.btn_action.set_visible(True)
        self.btn_stop.set_visible(False)
        self.fps_label.set_visible(False)
        self.show_toast("Webcam parada", "warning")
        self.update_mode_ui()

    def ask_open_photo(self, filename):
        def on_response(dialog, result):
            try:
                response = dialog.choose_finish(result)
                if response == "open":
                    subprocess.run(["xdg-open", filename])
            except:
                pass

        dialog = Adw.AlertDialog(
            heading="Foto Capturada",
            body=f"'{filename}' foi salva.\nDeseja abrir?"
        )
        dialog.add_response("cancel", "Não")
        dialog.add_response("open", "Sim")
        dialog.set_default_response("open")
        dialog.set_close_response("cancel")
        dialog.choose(self.win, None, on_response)

    def set_loading(self, loading=True):
        if hasattr(self, 'loading_bar'):
             self.loading_bar.set_visible(loading)
             
        if loading:
            if not hasattr(self, '_pulse_timer') or self._pulse_timer is None:
                self._pulse_timer = GLib.timeout_add(100, self._pulse_progress)
        else:
            if hasattr(self, '_pulse_timer') and self._pulse_timer:
                try:
                    GLib.source_remove(self._pulse_timer)
                except:
                    pass
                self._pulse_timer = None

    def _pulse_progress(self):
        if hasattr(self, 'loading_bar') and self.loading_bar.get_visible():
            self.loading_bar.pulse()
            return True
        return False

    def show_toast(self, message, style=None):
        self.top_toast_label.set_label(message)
        
        # Reset classes
        self.top_toast_label.set_css_classes(["top-toast"])
        if style:
            self.top_toast_label.add_css_class(style)
            
        self.top_toast_revealer.set_reveal_child(True)
        if hasattr(self, '_toast_timer') and self._toast_timer is not None:
            try:
                GLib.source_remove(self._toast_timer)
            except:
                pass
            self._toast_timer = None
            
        self._toast_timer = GLib.timeout_add(3000, self.hide_top_toast)

    def hide_top_toast(self):
        self.top_toast_revealer.set_reveal_child(False)
        self._toast_timer = None
        return False



if __name__ == '__main__':
    app = WebcamApp()
    app.run(sys.argv)
