#!/usr/bin/env python3
import sys
import subprocess
import os
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

# Initialize GStreamer
Gst.init(None)

class WebcamApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.biglinux.GPhoto2WebcamController',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.process = None
        self.log_process = None
        self.camera_name = "Nenhuma câmera detectada"
        self.current_mode = "photo"  # "photo" or "video"
        self.last_photo = None
        
        # Setup Dark Mode
        manager = Adw.StyleManager.get_default()
        manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_default_size(635, 480)
        
        # Detect camera first
        self.detect_camera()
        self.win.set_title(f"Webcam: {self.camera_name}")
        
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
        
        # Right side - Menu button
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_css_classes(["flat"])
        header.pack_end(menu_btn)
        
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
        self.photo_thumbnail.set_tooltip_text("Última foto")
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
        self.btn_stop.set_tooltip_text("Parar Webcam")
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
        photo_page = self.preview_stack.add_titled(photo_box, "photo", "Foto")
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
        
        video_page = self.preview_stack.add_titled(video_box, "video", "Webcam")
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
            border-radius: 50%;
            padding: 0;
            min-width: 48px;
            min-height: 48px;
            max-width: 48px;
            max-height: 48px;
        }

        .thumbnail-button {
            padding: 0;
            margin: 0;
            border: 2px solid white;
            min-width: 48px;
            min-height: 48px;
            max-width: 48px;
            max-height: 48px;
            border-radius: 50%;
            background: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            overflow: hidden;
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
        """
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def update_mode_ui(self):
        """Update UI elements based on current mode."""
        if self.current_mode == "photo":
            self.btn_action.set_icon_name("camera-photo-symbolic")
            self.preview_stack.set_visible_child_name("photo")
        else:
            self.btn_action.set_icon_name("media-record-symbolic")
            self.preview_stack.set_visible_child_name("video")

    def on_mode_changed(self, stack, param):
        """Called when ViewSwitcher changes the visible page."""
        page_name = stack.get_visible_child_name()
        if page_name == "photo":
            self.current_mode = "photo"
            self.btn_action.set_icon_name("camera-photo-symbolic")
        else:
            self.current_mode = "video"
            self.btn_action.set_icon_name("media-record-symbolic")

    def on_action_clicked(self, btn):
        if self.current_mode == "photo":
            self.take_photo()
        else:
            self.start_webcam()

    def on_thumbnail_clicked(self, btn):
        if self.last_photo and os.path.exists(self.last_photo):
            subprocess.run(["xdg-open", self.last_photo])

    def load_last_photo(self):
        """Load the most recent photo into preview and thumbnail."""
        try:
            files = glob.glob("capt*.jpg")
            if files:
                self.last_photo = max(files, key=os.path.getctime)
                
                # Load into main preview
                self.photo_preview.set_filename(self.last_photo)
                
                # Load into thumbnail (Avatar)
                try:
                    texture = Gdk.Texture.new_from_filename(self.last_photo)
                    self.thumbnail_avatar.set_custom_image(texture)
                except:
                    pass
        except Exception as e:
            pass

    def detect_camera(self):
        """Detect connected camera using gphoto2 --auto-detect."""
        try:
            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout
            lines = output.strip().split('\n')
            for line in lines[2:]:
                line = line.strip()
                if line and 'usb:' in line:
                    parts = line.split('usb:')
                    if parts:
                        self.camera_name = parts[0].strip()
                        return
        except:
            self.camera_name = "Câmera não detectada"

    def check_existing_session(self):
        try:
            # Check for gphoto2 process (since run_webcam.sh exits now)
            # We look for the specific command used in the pipeline
            res = subprocess.run(["pgrep", "-f", "gphoto2 --stdout"], capture_output=True, text=True)
            
            if res.returncode == 0 and res.stdout.strip():
                print("Sessão existente detectada. Restaurando...")
                self.current_mode = "video"
                self.update_mode_ui()
                
                # Update state
                self.btn_action.set_visible(False)
                self.btn_stop.set_visible(True)
                
                self.show_toast("Sessão restaurada", "accent")
                
                # Start preview immediately since pipeline is already running
                GLib.idle_add(self.start_video_preview)
        except Exception as e:
            print(f"Erro ao verificar sessão: {e}")

    def take_photo(self):
        """Take a photo and update the preview."""
        self.set_loading(True)
        # self.photo_label removed, status shown via toast if needed or implicitly by loading state
        
        # Stop webcam if running (camera can only do one thing at a time)
        was_webcam_running = getattr(self, 'process', None) is not None
        if was_webcam_running:
            self.show_toast("Parando webcam...", "warning")
            self.stop_video_preview()
            
            # Kill webcam processes
            subprocess.run(["pkill", "-f", "run_webcam.sh"], check=False)
            subprocess.run(["pkill", "-f", "gphoto2 --stdout"], check=False)
            subprocess.run(["pkill", "-f", "ffmpeg -stats -i"], check=False)
            self.process = None
            time.sleep(2)
        
        # Switch to photo view
        self.current_mode = "photo"
        self.update_mode_ui()
        self.btn_action.set_visible(True)
        self.btn_stop.set_visible(False)
        
        def do_capture():
            try:
                # Kill interfering processes
                subprocess.run(["pkill", "-f", "gvfs-gphoto2-volume-monitor"], check=False)
                time.sleep(1)
                
                target_filename = self.get_next_filename()
                GLib.idle_add(lambda: self.show_toast(f"Capturando {target_filename}...", "accent"))
                
                result = subprocess.run(
                    ["gphoto2", "--capture-image-and-download", "--filename", target_filename, "--force-overwrite"],
                    check=True, capture_output=True, text=True, timeout=20
                )
                
                GLib.idle_add(self.on_photo_captured, target_filename)
                
            except subprocess.TimeoutExpired:
                GLib.idle_add(self.on_photo_error, "Timeout - câmera demorou muito")
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                GLib.idle_add(self.on_photo_error, error_msg)
            except Exception as e:
                GLib.idle_add(self.on_photo_error, str(e))
        
        import threading
        threading.Thread(target=do_capture, daemon=True).start()

    def on_photo_captured(self, filename):
        self.last_photo = filename
        self.load_last_photo()
        self.set_loading(False)
        self.show_toast(f"Foto salva: {filename}", "success")
        self.ask_open_photo(filename)
        return False

    def on_photo_error(self, error):
        self.set_loading(False)
        self.show_toast("Erro ao capturar foto", "error")
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
        """Start webcam streaming."""
        self.set_loading(True)
        self.show_toast("Iniciando webcam...", "warning")
        self.btn_action.set_visible(False)
        self.btn_stop.set_visible(True)
        
        # Determine correct path relative to this script
        base_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(base_dir, "run_webcam.sh")
        
        # Ensure it is executable
        if not os.access(script_path, os.X_OK):
            try:
                os.chmod(script_path, 0o755)
            except:
                pass
                
        def run_script_thread():
            try:
                # Run the script and wait for it to finish (it waits for device ready)
                # We use subprocess.run so we block this thread until script exits
                res = subprocess.run(
                    [script_path],
                    capture_output=True,
                    text=True
                )
                
                # Check retuncode
                if res.returncode == 0:
                    # Success path
                    print(f"Script output: {res.stdout}")
                    GLib.idle_add(self.on_webcam_started_success)
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

    def on_webcam_started_success(self):
        self.show_toast("Webcam ativa!", "success")
        self.start_log_watcher()
        self.start_video_preview()

    def on_webcam_started_error(self, error):
        self.show_toast(f"Erro ao iniciar: {error}", "error")
        self.btn_action.set_visible(True)
        self.btn_stop.set_visible(False)
        self.set_loading(False)

    def start_video_preview(self):
        """Start video preview using OpenCV (fallback to GStreamer if needed)."""
        self.set_loading(True)
        self.show_toast("Iniciando preview...", "warning")
        
        # Determine device
        try:
            devices = sorted(glob.glob("/dev/video*"))
            if not devices:
                self.show_toast("Nenhum dispositivo", "warning")
                self.set_loading(False)
                return
            self.preview_device = devices[-1]
            
            # Extract index from /dev/videoX
            try:
                dev_idx = int(re.search(r'\d+$', self.preview_device).group())
            except:
                dev_idx = 0
            
            # Try OpenCV first as requested by user ("bibilioteca, não sei!")
            import cv2
            self.use_opencv = True
            
            # Create Capture
            # CAP_V4L2 is robust
            self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
            
            if not self.cap.isOpened():
                # Try waiting a bit more or fallback
                raise Exception("OpenCV não conseguiu abrir o dispositivo")
                
            self.preview_active = True
            self.fps_counter = 0
            self.last_fps_time = time.time()
            
            # Start polling timer
            GLib.timeout_add(33, self.update_opencv_frame) # ~30 FPS
            
            self.show_toast(f"Preview (OpenCV): {self.preview_device}", "accent")
            self.set_loading(False)
            
        except ImportError:
            self.show_toast("OpenCV não encontrado, usando GStreamer...", "warning")
            self.use_opencv = False
            self.start_gstreamer_preview()
        except Exception as e:
            self.show_toast(f"Erro Preview: {e}", "error")
            self.set_loading(False)

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

    def start_gstreamer_preview(self):
        # Fallback implementation (Simplified)
        try:
             # v4l2src device=... ! decodebin ! videoconvert ! ...
             # Using decodebin is safer than forcing raw caps
            pipeline_str = (
                f"v4l2src device={self.preview_device} ! "
                "decodebin ! "
                "videoconvert ! "
                "videoscale ! "
                "video/x-raw,format=RGB,width=640,height=480 ! "
                "appsink name=sink emit-signals=True drop=True max-buffers=1 sync=False"
            )
            self.gst_pipeline = Gst.parse_launch(pipeline_str)
            appsink = self.gst_pipeline.get_by_name("sink")
            appsink.connect("new-sample", self.on_gst_sample)
            self.gst_pipeline.set_state(Gst.State.PLAYING)
            self.preview_active = True
        except Exception as e:
             self.show_toast(f"Erro GStreamer: {e}", "error")

    # Keep on_gst_sample for fallback
    def on_gst_sample(self, sink):
        if not self.preview_active:
            return Gst.FlowReturn.ERROR
        sample = sink.emit("pull-sample")
        if not sample: return Gst.FlowReturn.ERROR
        
        # Basic stats if GStreamer running
        self.fps_label.set_visible(True)
        
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

    def start_log_watcher(self):
        # Deprecated: log watcher not needed for GStreamer pipeline
        pass

    def on_log_output(self, fd, condition):
        # Deprecated
        return False

    def on_stop_clicked(self, btn):
        # Stop video preview first
        self.stop_video_preview()
        
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process = None
            except:
                pass

        try:
            subprocess.run(["pkill", "-f", "run_webcam.sh"], check=False)
            subprocess.run(["pkill", "-f", "ffmpeg -stats -i"], check=False)
            subprocess.run(["pkill", "-f", "gphoto2 --stdout"], check=False)
        except:
            pass
        
        self.btn_action.set_visible(True)
        self.btn_stop.set_visible(False)
        self.fps_label.set_visible(False)
        self.show_toast("Webcam parada", "warning")

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
        # Progress bar removed, no-op or maybe show a spinner toast later if requested
        pass

    def show_toast(self, message, style=None):
        """Show a custom top toast with the message."""
        self.top_toast_label.set_label(message)
        
        # Reset classes
        self.top_toast_label.set_css_classes(["top-toast"])
        if style:
            self.top_toast_label.add_css_class(style)
            
        self.top_toast_revealer.set_reveal_child(True)
        
        # Remove existing timer if active
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

    def on_close_clicked(self, btn):
        """Close the application, stopping any running processes first."""
        # Stop video preview
        self.stop_video_preview()
        
        # Stop webcam processes if running
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except:
                pass
        
        subprocess.run(["pkill", "-f", "run_webcam.sh"], check=False)
        subprocess.run(["pkill", "-f", "gphoto2 --stdout"], check=False)
        
        # Close window
        self.win.close()

if __name__ == '__main__':
    app = WebcamApp()
    app.run(sys.argv)
