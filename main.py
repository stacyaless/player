# main.py
import sys
import os
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import pygame
from PIL import Image

# 导入模块
import config
import utils
import metadata

# 检查库
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("Error", "pip install tkinterdnd2")
    sys.exit(1)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class MusicPlayer(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("Music Pro Modular")
        self.geometry(f"{config.START_WIDTH}x{config.START_HEIGHT}")
        self.resizable(True, True)
        self.minsize(360, 600)
        
        # 🟢 这里的变量现在一定存在于 config.py 中
        self.configure(fg_color=config.COLOR_BG_DEFAULT)

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)

        try: pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        except: pass

        # 状态
        self.playlist = []
        self.current_index = 0
        self.is_playing = False
        self.is_dragging = False
        self.total_duration = 0
        self.seek_offset = 0
        self.show_playlist = False
        
        # 缓存
        self.original_cover = metadata.get_default_cover()
        self.tiny_cover = self.original_cover.resize((50, 50)) 
        self.lyrics_map = {}
        self.time_points = []
        self.active_lyric_index = -1
        self.current_scroll_y = 0
        self.target_scroll_y = 0
        self.resize_timer = None

        self.setup_ui()
        self.bind("<Configure>", self.on_resize)
        
        # 启动
        self.update_visuals(self.original_cover)
        self.animate_lyrics()

    def setup_ui(self):
        # Layer 0: Background
        self.bg_label = ctk.CTkLabel(self, text="")
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Layer 1: Content
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_frame.pack(fill="both", expand=True)

        # Header
        self.header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent", height=50)
        self.header_frame.pack(side="top", fill="x", padx=20, pady=(10,0))
        
        self.btn_menu = ctk.CTkButton(
            self.header_frame, text="☰", width=40, height=40,
            fg_color="transparent", hover_color=config.COLOR_BTN_HOVER, 
            text_color=config.COLOR_TEXT_WHITE, font=("Arial", 20),
            command=self.toggle_playlist_view
        )
        self.btn_menu.pack(side="right")

        # Top Area
        self.top_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent", corner_radius=0)
        self.top_frame.pack(side="top", fill="both", expand=True)

        self.cover_label = ctk.CTkLabel(self.top_frame, text="", corner_radius=15, fg_color="transparent")
        self.cover_label.place(relx=0.5, rely=0.5, anchor="center")

        # Playlist Area
        self.playlist_frame = ctk.CTkScrollableFrame(self.top_frame, fg_color="transparent")

        # Bottom Area
        self.ctrl_frame = ctk.CTkFrame(self.content_frame, corner_radius=0, fg_color=config.COLOR_BG_DEFAULT)
        self.ctrl_frame.pack(side="bottom", fill="x", expand=False)

        self.setup_controls()

    def setup_controls(self):
        f_title = ctk.CTkFont(family=utils.REAL_FONT_NAME, size=24, weight="bold")
        f_sub = ctk.CTkFont(family=utils.REAL_FONT_NAME, size=14)
        f_time = ctk.CTkFont(family=utils.REAL_FONT_NAME, size=12)
        f_btn = ctk.CTkFont(family=utils.REAL_FONT_NAME, size=13, weight="bold")

        self.lbl_title = ctk.CTkLabel(self.ctrl_frame, text="Ready", font=f_title, text_color=config.COLOR_TEXT_WHITE)
        self.lbl_title.pack(pady=(10, 5), fill="x", padx=20)
        self.lbl_artist = ctk.CTkLabel(self.ctrl_frame, text="Drag & Drop music", font=f_sub, text_color=config.COLOR_TEXT_GRAY)
        self.lbl_artist.pack(pady=(0, 10), fill="x", padx=20)

        self.lyric_canvas = tk.Canvas(self.ctrl_frame, height=120, bg=config.COLOR_BG_DEFAULT, highlightthickness=0)
        self.lyric_canvas.pack(fill="x", pady=(5, 5))

        self.slider_val = tk.DoubleVar()
        self.slider = ctk.CTkSlider(self.ctrl_frame, from_=0, to=100, variable=self.slider_val, height=18,
                                    fg_color="#000000", progress_color="white", button_color="white", 
                                    button_hover_color="#EEEEEE", command=self.on_drag_start)
        self.slider.bind("<ButtonRelease-1>", self.on_drag_end)
        self.slider.pack(fill="x", padx=30, pady=10)

        self.time_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        self.time_frame.pack(fill="x", padx=35)
        self.lbl_curr = ctk.CTkLabel(self.time_frame, text="0:00", text_color=config.COLOR_TEXT_GRAY, font=f_time)
        self.lbl_curr.pack(side="left")
        self.lbl_total = ctk.CTkLabel(self.time_frame, text="-0:00", text_color=config.COLOR_TEXT_GRAY, font=f_time)
        self.lbl_total.pack(side="right")

        self.btn_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        self.btn_frame.pack(pady=20)

        def mk_btn(txt, cmd, size=24, big=False):
            w, h = (80, 80) if big else (50, 50)
            f_size = 50 if big else size
            return ctk.CTkButton(self.btn_frame, text=txt, width=w, height=h, font=("Arial", f_size),
                                 fg_color="transparent", hover_color=None, text_color="white", 
                                 border_width=0, corner_radius=0, command=cmd)

        self.btn_prev = mk_btn("⏮", self.prev_song)
        self.btn_prev.pack(side="left", padx=15)
        self.btn_play = mk_btn("▶", self.toggle_play, big=True)
        self.btn_play.pack(side="left", padx=15)
        self.btn_next = mk_btn("⏭", self.next_song)
        self.btn_next.pack(side="left", padx=15)

        self.btn_import = ctk.CTkButton(self.ctrl_frame, text="Import", fg_color="transparent", hover_color=None,
                                        text_color="white", font=f_btn, height=45, border_width=0, 
                                        command=self.load_files)
        self.btn_import.pack(side="bottom", pady=10)

    def on_drop(self, event):
        raw = event.data
        if raw.startswith('{') and raw.endswith('}'): raw = raw[1:-1]
        valid = []
        if os.path.exists(raw): valid.append(raw)
        else:
            import re
            for p in re.findall(r'\{.*?\}|\S+', raw):
                p = p.strip('{}')
                if os.path.exists(p): valid.append(p)
        valid = [f for f in valid if f.lower().endswith(('.mp3', '.wav', '.flac', '.m4a'))]
        if valid:
            self.playlist.extend(valid)
            self.refresh_playlist_ui()
            if len(self.playlist) == len(valid):
                self.current_index = 0
                self.play_index(0)

    def load_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Audio", "*.mp3 *.wav *.flac *.m4a")])
        if files:
            self.playlist.extend(list(files))
            self.refresh_playlist_ui()
            if len(self.playlist) == len(files):
                self.current_index = 0
                self.play_index(0)

    def play_index(self, index):
        if not self.playlist: return
        try: pygame.mixer.music.unload()
        except: pass
        self.current_index = index
        path = self.playlist[index]
        
        t, a, d, c = metadata.get_track_info(path)
        self.lbl_title.configure(text=t, font=ctk.CTkFont(family=utils.REAL_FONT_NAME, size=24, weight="bold"))
        self.lbl_artist.configure(text=a, font=ctk.CTkFont(family=utils.REAL_FONT_NAME, size=14))
        
        self.total_duration = d
        # 🟢 进度条设置
        slider_max = d if d > 0 else 100
        self.slider.configure(to=slider_max)
        self.slider.set(0)
        self.seek_offset = 0
        
        self.lyrics_map, self.time_points = metadata.get_lyrics(path)
        self.active_lyric_index = -1
        self.current_scroll_y = 0
        self.target_scroll_y = 0
        self.draw_lyrics_on_canvas()

        self.update_visuals(c)
        self.refresh_playlist_ui()

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self.is_playing = True
            self.btn_play.configure(text="⏸")
            self.monitor()
        except: pass

    def update_visuals(self, pil_img=None):
        curr_w = self.winfo_width()
        curr_h = self.winfo_height()
        if curr_w < 100: curr_w = config.START_WIDTH
        if curr_h < 100: curr_h = config.START_HEIGHT

        if pil_img:
            self.original_cover = pil_img
            self.tiny_cover = pil_img.resize((40, 40), Image.Resampling.BILINEAR)
        
        bg_img, bg_color = utils.process_background(self.tiny_cover, curr_w, curr_h)
        self.tk_bg = ctk.CTkImage(bg_img, size=(curr_w, curr_h))
        self.bg_label.configure(image=self.tk_bg)

        self.ctrl_frame.configure(fg_color=bg_color)
        self.top_frame.configure(fg_color="transparent")
        self.lyric_canvas.configure(bg=bg_color)
        
        # 🟢 专辑图尺寸计算 (使用 config 里的变量)
        target_size = int(curr_w * config.WIDTH_RATIO)
        max_h = int(curr_h * config.ALBUM_HEIGHT_RATIO)
        final_size = min(target_size, max_h)
        
        cover_resized = self.original_cover.resize((final_size, final_size), Image.Resampling.BICUBIC)
        self.tk_cover = ctk.CTkImage(cover_resized, size=(final_size, final_size))
        self.cover_label.configure(image=self.tk_cover)

        r = int(bg_color[1:3], 16) + 30
        g = int(bg_color[3:5], 16) + 30
        b = int(bg_color[5:7], 16) + 30
        hover = f"#{min(r,255):02x}{min(g,255):02x}{min(b,255):02x}"
        self.btn_import.configure(hover_color=hover)

    def on_resize(self, event):
        if event.widget == self:
            if self.resize_timer: self.after_cancel(self.resize_timer)
            self.resize_timer = self.after(50, lambda: self.update_visuals(None))

    def draw_lyrics_on_canvas(self):
        self.lyric_canvas.delete("all")
        center_x = self.winfo_width() / 2
        center_y = 60 
        
        if not self.time_points:
            tk_font = (utils.REAL_FONT_NAME, config.LYRIC_FONT_SIZE)
            self.lyric_canvas.create_text(center_x, center_y, text="No Lyrics", font=tk_font, fill="#888888", anchor="center")
            return

        start_idx = max(0, int(self.current_scroll_y / config.LYRIC_LINE_HEIGHT) - 2)
        end_idx = min(len(self.time_points), start_idx + 6)

        for i in range(start_idx, end_idx):
            text = self.lyrics_map[self.time_points[i]]
            y_pos = center_y + (i * config.LYRIC_LINE_HEIGHT) - self.current_scroll_y
            
            if i == self.active_lyric_index:
                fill = "white"; tk_font = (utils.REAL_FONT_NAME, config.LYRIC_FONT_SIZE, "bold")
            else:
                fill = "#888888"; tk_font = (utils.REAL_FONT_NAME, config.LYRIC_FONT_SIZE_SUB)
            
            self.lyric_canvas.create_text(center_x, y_pos, text=text, font=tk_font, fill=fill, anchor="center", width=self.winfo_width()-40)

    def animate_lyrics(self):
        if abs(self.target_scroll_y - self.current_scroll_y) > 0.5:
            self.current_scroll_y += (self.target_scroll_y - self.current_scroll_y) * 0.1
            self.draw_lyrics_on_canvas()
        self.after(33, self.animate_lyrics)

    def toggle_play(self):
        if not self.playlist: return
        if self.is_playing:
            pygame.mixer.music.pause(); self.is_playing = False; self.btn_play.configure(text="▶")
        else:
            pygame.mixer.music.unpause(); self.is_playing = True; self.btn_play.configure(text="⏸")

    def prev_song(self):
        if self.playlist:
            idx = (self.current_index - 1) % len(self.playlist)
            self.play_index(idx)

    def next_song(self):
        if self.playlist:
            idx = (self.current_index + 1) % len(self.playlist)
            self.play_index(idx)

    def on_drag_start(self, val): self.is_dragging = True
    def on_drag_end(self, val):
        if self.playlist:
            try:
                t = self.slider.get()
                pygame.mixer.music.play(start=t)
                self.seek_offset = t
                self.is_playing = True
                self.btn_play.configure(text="⏸")
            except: pass
        self.is_dragging = False

    def monitor(self):
        if self.is_playing and not self.is_dragging:
            try:
                raw = pygame.mixer.music.get_pos()
                if raw == -1: raw = 0
                curr = (raw / 1000) + self.seek_offset
                if curr < 0: curr = 0
                if curr > self.total_duration: curr = self.total_duration
                
                self.slider.set(curr)
                self.lbl_curr.configure(text=utils.fmt_time(curr))
                rem = max(0, self.total_duration - curr)
                self.lbl_total.configure(text=f"-{utils.fmt_time(rem)}")
                
                if self.time_points:
                    new_idx = -1
                    for i, t in enumerate(self.time_points):
                        if t <= curr: new_idx = i
                        else: break
                    if new_idx != -1 and new_idx != self.active_lyric_index:
                        self.active_lyric_index = new_idx
                        self.target_scroll_y = self.active_lyric_index * config.LYRIC_LINE_HEIGHT

                if not pygame.mixer.music.get_busy() and (self.total_duration - curr) < 1:
                    self.next_song()
            except: pass
        self.after(500, self.monitor)

    def toggle_playlist_view(self):
        self.show_playlist = not self.show_playlist
        if self.show_playlist:
            self.cover_label.place_forget()
            self.playlist_frame.pack(fill="both", expand=True, padx=20, pady=20)
            self.refresh_playlist_ui()
        else:
            self.playlist_frame.pack_forget()
            self.cover_label.place(relx=0.5, rely=0.5, anchor="center")

    def refresh_playlist_ui(self):
        for w in self.playlist_frame.winfo_children(): w.destroy()
        for i, p in enumerate(self.playlist):
            name = os.path.basename(p)
            fg = "white" if i == self.current_index else "#AAAAAA"
            font_w = "bold" if i == self.current_index else "normal"
            btn = ctk.CTkButton(self.playlist_frame, text=f"{i+1}. {name}", anchor="w",
                                font=(utils.REAL_FONT_NAME, 14, font_w),
                                fg_color="transparent", hover_color="#333333", text_color=fg, height=40,
                                command=lambda x=i: self.play_index(x))
            btn.pack(fill="x")

if __name__ == "__main__":
    app = MusicPlayer()
    app.mainloop()
