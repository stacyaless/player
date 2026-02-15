# main.py
import sys
import os
import re
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk 
import pygame
from PIL import Image, ImageTk
import math
import splash
import config
import utils
import metadata
import assets 
import online_fetcher  # 实验性功能：在线获取歌词和封面 

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("Error", "pip install tkinterdnd2")
    sys.exit(1)

# 字体配置
BASE_SIZE_MAIN = 24
BASE_SIZE_SUB = 14
BASE_SIZE_BTN_BIG = 55 
BASE_SIZE_BTN_SMALL = 30
BASE_SIZE_IMPORT = 12

class MusicPlayer(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("Music")
        self.geometry(f"{config.START_WIDTH}x{config.START_HEIGHT}")
        self.resizable(True, True)
        self.minsize(360, 600)
        self.configure(fg_color="#000000")

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)

        try: pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        except: pass

        icon_path = self.resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # State
        self.playlist = []
        self.current_index = -1  # -1 表示没有当前播放的歌曲
        self.is_playing = False
        self.is_dragging = False
        self.total_duration = 1 
        self.seek_offset = 0
        self.original_cover = metadata.get_default_cover()
        self.tiny_cover = self.original_cover.resize((50, 50)) 
        self.lyrics_map = {}
        self.time_points = []
        self.active_lyric_index = -1
        self.resize_timer = None
        self.tk_bg_ref = None
        self.tk_cover_ref = None
        self.playlist_window = None  # 播放列表窗口（废弃，改用下拉菜单）
        
        # 下拉菜单状态
        self.playlist_dropdown = None  # 下拉菜单的 Frame
        self.playlist_canvas = None    # 下拉菜单内的 Canvas
        self.playlist_scrollbar = None # 滚动条
        self.dropdown_visible = False  # 是否显示
        self.dropdown_target_height = 0  # 目标高度
        self.dropdown_current_height = 0 # 当前高度
        self.dropdown_animation_id = None # 动画定时器
        self.playlist_song_frames = []  # 保存每首歌的frame引用
        self.playlist_song_buttons = [] # 保存每首歌的按钮引用
        
        # 背景动画状态
        self.bg_animation_phase = 0.0  # 动画相位 (0.0 - 4.0)
        self.bg_animation_speed = 0.01  # 动画速度（每帧增加的相位）
        self.bg_animation_timer = None  # 动画定时器
        self.bg_original_image = None  # 原始背景图（用于动画）
        
        # 实验性功能开关
        self.enable_online_fetch = True  # 是否启用在线获取歌词和封面

        self.refs = {
            "bg": None, "cover": None, 
            "btn_play": None, "btn_pause": None,
            "btn_prev": None, "btn_next": None, "btn_import": None,
            "btn_playlist": None
        }

        # Canvas
        self.canvas = tk.Canvas(self, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # 创建下拉菜单（初始隐藏，放在Canvas之上）
        self.create_playlist_dropdown()

        self.btn_objects = {} 
        self.prog_x_start = 0
        self.prog_x_end = 0
        self.prog_width = 1

        self.id_bg = self.canvas.create_image(0, 0, anchor="nw")
        self.id_cover = self.canvas.create_image(0, 0, anchor="center")
        
        # 文本
        f_main = (utils.REAL_FONT_NAME, BASE_SIZE_MAIN, "bold")
        f_sub = (utils.REAL_FONT_NAME, BASE_SIZE_SUB)
        self.id_title = self.canvas.create_text(0, 0, text="Ready", font=f_main, fill="white", anchor="center")
        self.id_artist = self.canvas.create_text(0, 0, text="Drag & Drop music", font=f_sub, fill="#DDDDDD", anchor="center")
        
        # 歌词Canvas - 用于滚动歌词显示
        self.lyric_items = []
        self.lyric_scroll_offset = 0      # 当前滚动位置 (像素)
        self.target_scroll_offset = 0     # 目标滚动位置 (像素)
        

        # 时间
        f_time = (utils.REAL_FONT_NAME, 11)
        self.id_time_curr = self.canvas.create_text(0, 0, text="0:00", font=f_time, fill="#DDDDDD", anchor="w")
        self.id_time_total = self.canvas.create_text(0, 0, text="-0:00", font=f_time, fill="#DDDDDD", anchor="e")
        
        # 进度条
        self.id_prog_bg = self.canvas.create_line(0, 0, 0, 0, fill="#555555", width=4, capstyle="round")
        self.id_prog_fg = self.canvas.create_line(0, 0, 0, 0, fill="white", width=4, capstyle="round")
        self.id_prog_hitbox = self.canvas.create_line(0, 0, 0, 0, fill="", width=20) 

        self.load_icon_assets()

        self.create_img_btn("prev", self.refs["btn_prev"], self.prev_song)
        self.create_img_btn("play", self.refs["btn_play"], self.toggle_play) 
        self.create_img_btn("next", self.refs["btn_next"], self.next_song)
        self.create_img_btn("import", self.refs["btn_import"], self.load_files)
        self.create_img_btn("playlist", self.refs["btn_playlist"], self.toggle_playlist_dropdown)

        self.canvas.tag_bind(self.id_prog_hitbox, "<Button-1>", self.on_prog_click)
        self.canvas.tag_bind(self.id_prog_hitbox, "<B1-Motion>", self.on_prog_drag)
        self.canvas.tag_bind(self.id_prog_hitbox, "<ButtonRelease-1>", self.on_prog_release)
        self.canvas.tag_bind(self.id_prog_hitbox, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(self.id_prog_hitbox, "<Leave>", lambda e: self.canvas.config(cursor=""))

        self.bind("<Configure>", self.on_resize)

        # 启动动画循环
        self.animate_lyrics() 
        
        self.update_visuals(self.original_cover)
        self.monitor()

    def load_icon_assets(self):
        self.refs["btn_play"] = assets.get_icon_tk("play", 55)
        self.refs["btn_pause"] = assets.get_icon_tk("pause", 55)
        self.refs["btn_prev"] = assets.get_icon_tk("prev", 35)
        self.refs["btn_next"] = assets.get_icon_tk("next", 35)
        self.refs["btn_import"] = assets.get_icon_tk("import", 30)
        self.refs["btn_playlist"] = assets.get_icon_tk("playlist", 30)

    def create_img_btn(self, name, tk_img, cmd):
        item_id = self.canvas.create_image(0, 0, image=tk_img, anchor="center")
        self.btn_objects[name] = {"id": item_id, "cmd": cmd}
        self.canvas.tag_bind(item_id, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(item_id, "<Leave>", lambda e: self.canvas.config(cursor=""))
        self.canvas.tag_bind(item_id, "<Button-1>", lambda e, n=name: self.on_btn_press(n))
        self.canvas.tag_bind(item_id, "<ButtonRelease-1>", lambda e, n=name: self.on_btn_release(n))

    def on_btn_press(self, name):
        self.canvas.move(self.btn_objects[name]["id"], 0, 1)

    def on_btn_release(self, name):
        self.canvas.move(self.btn_objects[name]["id"], 0, -1)
        if self.btn_objects[name]["cmd"]:
            self.btn_objects[name]["cmd"]()

    def create_playlist_dropdown(self):
        """创建播放列表下拉菜单"""
        # 创建一个Frame作为下拉菜单容器
        self.playlist_dropdown = ctk.CTkFrame(
            self,
            fg_color="#1a1a1a",
            corner_radius=0,
            border_width=2,
            border_color="#333333",
            height=0  # 初始高度为0（隐藏）
        )
        # 使用place布局，relwidth=1表示宽度100%
        self.playlist_dropdown.place(x=0, y=0, relwidth=1)
        # 禁止自动调整大小
        self.playlist_dropdown.pack_propagate(False)
        
        # 创建滚动框架（直接从顶部开始，没有标题栏）
        self.playlist_scroll_frame = ctk.CTkScrollableFrame(
            self.playlist_dropdown,
            fg_color="#1a1a1a",
            scrollbar_button_color="#333333",
            scrollbar_button_hover_color="#555555"
        )
        self.playlist_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def toggle_playlist_dropdown(self):
        """切换播放列表下拉菜单的显示/隐藏"""
        if self.dropdown_visible:
            # 收起菜单
            self.hide_playlist_dropdown()
        else:
            # 展开菜单
            self.show_playlist_dropdown()

    def show_playlist_dropdown(self):
        """展开播放列表下拉菜单"""
        self.dropdown_visible = True
        
        # 刷新播放列表内容
        self.refresh_playlist_content()
        
        # 计算目标高度（专辑图下方）
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 100:
            w = config.START_WIDTH
            h = config.START_HEIGHT
        
        # 封面底部位置
        cover_y = h * 0.26
        max_size = int(w * config.WIDTH_RATIO)
        max_h = int(h * config.ALBUM_HEIGHT_RATIO)
        size = min(max_size, max_h)
        cover_bottom = cover_y + size / 2
        
        # 下拉菜单高度：从顶部到封面底部 + 一点间距
        self.dropdown_target_height = int(cover_bottom + 20)
        
        # 提升到最前面
        self.playlist_dropdown.lift()
        
        # 开始动画
        self.animate_dropdown()

    def hide_playlist_dropdown(self):
        """收起播放列表下拉菜单"""
        self.dropdown_visible = False
        self.dropdown_target_height = 0
        self.animate_dropdown()

    def animate_dropdown(self):
        """下拉菜单的平滑动画"""
        # 取消之前的动画
        if self.dropdown_animation_id:
            self.after_cancel(self.dropdown_animation_id)
        
        # 计算差值
        diff = self.dropdown_target_height - self.dropdown_current_height
        
        if abs(diff) > 1:
            # 平滑过渡
            self.dropdown_current_height += diff * 0.3
            self.playlist_dropdown.configure(height=int(self.dropdown_current_height))
            
            # 继续动画
            self.dropdown_animation_id = self.after(16, self.animate_dropdown)  # ~60fps
        else:
            # 动画结束
            self.dropdown_current_height = self.dropdown_target_height
            self.playlist_dropdown.configure(height=int(self.dropdown_current_height))
            self.dropdown_animation_id = None

    def refresh_playlist_content(self):
        """刷新播放列表内容"""
        # 清空现有内容
        for widget in self.playlist_scroll_frame.winfo_children():
            widget.destroy()
        
        # 保存歌曲项的引用，用于后续更新高亮
        self.playlist_song_frames = []
        self.playlist_song_buttons = []
        
        if not self.playlist:
            empty_label = ctk.CTkLabel(
                self.playlist_scroll_frame,
                text="No songs in playlist",
                font=(utils.REAL_FONT_NAME, 12),
                text_color="#888888"
            )
            empty_label.pack(pady=20)
        else:
            for idx, path in enumerate(self.playlist):
                # 获取歌曲信息
                title, artist, _, _ = metadata.get_track_info(path)
                
                is_current = (idx == self.current_index)
                
                # 创建歌曲项容器
                song_frame = ctk.CTkFrame(
                    self.playlist_scroll_frame,
                    fg_color="#2a2a2a" if is_current else "transparent",
                    corner_radius=5
                )
                song_frame.pack(fill="x", pady=2, padx=5)
                self.playlist_song_frames.append(song_frame)
                
                # 歌曲信息按钮
                song_btn = ctk.CTkButton(
                    song_frame,
                    text=f"{title}\n{artist}",
                    font=(utils.REAL_FONT_NAME, 11),
                    text_color="white" if is_current else "#CCCCCC",
                    fg_color="transparent",
                    hover_color="#333333",
                    anchor="w",
                    command=lambda i=idx: self.play_from_playlist(i)
                )
                song_btn.pack(side="left", fill="x", expand=True, padx=5, pady=5)
                self.playlist_song_buttons.append(song_btn)
                
                # 删除按钮
                delete_btn = ctk.CTkButton(
                    song_frame,
                    text="✕",
                    width=30,
                    font=(utils.REAL_FONT_NAME, 14),
                    text_color="#888888",
                    fg_color="transparent",
                    hover_color="#ff4444",
                    command=lambda i=idx: self.remove_from_playlist(i)
                )
                delete_btn.pack(side="right", padx=5)

    def update_playlist_highlight(self, old_index, new_index):
        """只更新播放列表的高亮状态，不重建整个列表"""
        if not hasattr(self, 'playlist_song_frames') or not self.playlist_song_frames:
            return
        
        # 取消旧的高亮
        if 0 <= old_index < len(self.playlist_song_frames):
            self.playlist_song_frames[old_index].configure(fg_color="transparent")
            self.playlist_song_buttons[old_index].configure(text_color="#CCCCCC")
        
        # 设置新的高亮
        if 0 <= new_index < len(self.playlist_song_frames):
            self.playlist_song_frames[new_index].configure(fg_color="#2a2a2a")
            self.playlist_song_buttons[new_index].configure(text_color="white")

    def append_songs_to_playlist(self, new_songs, start_index):
        """追加新歌曲到播放列表显示（不重建整个列表）"""
        if not hasattr(self, 'playlist_song_frames'):
            self.playlist_song_frames = []
            self.playlist_song_buttons = []
        
        # 如果列表之前是空的，需要先清除"空列表"提示
        if start_index == 0:
            for widget in self.playlist_scroll_frame.winfo_children():
                widget.destroy()
            self.playlist_song_frames = []
            self.playlist_song_buttons = []
        
        # 追加新歌曲
        for i, path in enumerate(new_songs):
            idx = start_index + i
            # 获取歌曲信息
            title, artist, _, _ = metadata.get_track_info(path)
            
            is_current = (idx == self.current_index)
            
            # 创建歌曲项容器
            song_frame = ctk.CTkFrame(
                self.playlist_scroll_frame,
                fg_color="#2a2a2a" if is_current else "transparent",
                corner_radius=5
            )
            song_frame.pack(fill="x", pady=2, padx=5)
            self.playlist_song_frames.append(song_frame)
            
            # 歌曲信息按钮
            song_btn = ctk.CTkButton(
                song_frame,
                text=f"{title}\n{artist}",
                font=(utils.REAL_FONT_NAME, 11),
                text_color="white" if is_current else "#CCCCCC",
                fg_color="transparent",
                hover_color="#333333",
                anchor="w",
                command=lambda i=idx: self.play_from_playlist(i)
            )
            song_btn.pack(side="left", fill="x", expand=True, padx=5, pady=5)
            self.playlist_song_buttons.append(song_btn)
            
            # 删除按钮
            delete_btn = ctk.CTkButton(
                song_frame,
                text="✕",
                width=30,
                font=(utils.REAL_FONT_NAME, 14),
                text_color="#888888",
                fg_color="transparent",
                hover_color="#ff4444",
                command=lambda i=idx: self.remove_from_playlist(i)
            )
            delete_btn.pack(side="right", padx=5)

    def on_playlist_close(self):
        """播放列表窗口关闭时的回调（已废弃）"""
        pass

    def play_from_playlist(self, index):
        """从播放列表中播放指定歌曲"""
        old_index = self.current_index
        self.play_index(index)
        # 只更新高亮状态，不重建整个列表
        if self.dropdown_visible:
            self.update_playlist_highlight(old_index, index)

    def remove_from_playlist(self, index):
        """从播放列表中移除歌曲"""
        if 0 <= index < len(self.playlist):
            # 如果删除的是当前播放的歌曲
            if index == self.current_index:
                # 停止播放
                try:
                    pygame.mixer.music.stop()
                except:
                    pass
                # 如果还有其他歌曲，播放下一首
                if len(self.playlist) > 1:
                    next_index = index if index < len(self.playlist) - 1 else 0
                    del self.playlist[index]
                    self.current_index = next_index if next_index < index else next_index - 1
                    self.play_index(self.current_index)
                else:
                    # 播放列表清空
                    self.playlist = []
                    self.current_index = -1
                    self.is_playing = False
                    self.canvas.itemconfig(self.id_title, text="Ready")
                    self.canvas.itemconfig(self.id_artist, text="Drag & Drop music")
                    self.canvas.itemconfig(self.btn_objects["play"]["id"], image=self.refs["btn_play"])
            else:
                # 删除其他歌曲
                del self.playlist[index]
                # 调整当前索引
                if index < self.current_index:
                    self.current_index -= 1
            
            # 刷新播放列表内容
            if self.dropdown_visible:
                self.refresh_playlist_content()

    def resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def update_layout(self):
        w = self.winfo_width(); h = self.winfo_height()
        if w < 100: w = config.START_WIDTH; h = config.START_HEIGHT
        cx = w / 2
        
        # 1. 封面
        cover_y = h * 0.26
        self.canvas.coords(self.id_cover, cx, cover_y)

        # 2. 信息
        info_start_y = h * 0.52  # 增加信息区域下移距离
        self.canvas.coords(self.id_title, cx, info_start_y)
        self.canvas.coords(self.id_artist, cx, info_start_y + 35)  # 增加标题与艺术家间距

        # 3. 歌词区域（直接在主Canvas上，调用绘制）
        self.draw_lyrics_on_canvas()
        
        # 4. 进度条
        prog_y = h * 0.74  # 向上移动进度条，与歌词保持合适间距
        margin_x = 40
        self.prog_x_start = margin_x
        self.prog_x_end = w - margin_x
        self.prog_width = self.prog_x_end - self.prog_x_start
        
        self.canvas.coords(self.id_prog_bg, self.prog_x_start, prog_y, self.prog_x_end, prog_y)
        self.canvas.coords(self.id_prog_fg, self.prog_x_start, prog_y, self.prog_x_start, prog_y)
        self.canvas.coords(self.id_prog_hitbox, self.prog_x_start, prog_y, self.prog_x_end, prog_y)
        
        # 5. 时间
        time_y = prog_y + 20
        self.canvas.coords(self.id_time_curr, self.prog_x_start, time_y)
        self.canvas.coords(self.id_time_total, self.prog_x_end, time_y)
        
        # 6. 按钮
        btn_y = h * 0.82  # 向上移动控制按钮区域
        btn_spacing = 90
        self.canvas.coords(self.btn_objects["prev"]["id"], cx - btn_spacing, btn_y)
        self.canvas.coords(self.btn_objects["play"]["id"], cx, btn_y)
        self.canvas.coords(self.btn_objects["next"]["id"], cx + btn_spacing, btn_y)

        # 7. 底部按钮（播放列表在左，导入在右）
        bottom_y = h - 50
        bottom_spacing = 100  # 两个按钮之间的间距
        self.canvas.coords(self.btn_objects["playlist"]["id"], cx - bottom_spacing, bottom_y)
        self.canvas.coords(self.btn_objects["import"]["id"], cx + bottom_spacing, bottom_y)

    def update_visuals(self, new_cover):
        if new_cover is None:
            new_cover = self.original_cover
        else:
            self.original_cover = new_cover

        w = self.winfo_width(); h = self.winfo_height()
        if w < 100: w = config.START_WIDTH; h = config.START_HEIGHT

        # 保存原始背景图用于动画
        self.bg_original_image = new_cover
        self.bg_animation_phase = 0.0  # 重置动画相位
        
        # 背景（初始位置）
        bg_img = utils.process_background(new_cover, w, h, 0, 0)
        self.tk_bg_ref = ImageTk.PhotoImage(bg_img)
        self.canvas.itemconfig(self.id_bg, image=self.tk_bg_ref)
        
        # 如果正在播放，启动背景动画
        if self.is_playing:
            self.start_background_animation()

        # 封面
        max_size = int(w * config.WIDTH_RATIO)
        max_h = int(h * config.ALBUM_HEIGHT_RATIO)
        size = min(max_size, max_h)
        cover_resized = new_cover.resize((size, size), Image.Resampling.LANCZOS)
        self.tk_cover_ref = ImageTk.PhotoImage(cover_resized)
        self.canvas.itemconfig(self.id_cover, image=self.tk_cover_ref)

        self.update_layout()

    def draw_lyrics_on_canvas(self):
        """在主Canvas上绘制歌词（Apple Music风格）"""
        # 清除旧的歌词对象
        for item_id in self.lyric_items:
            self.canvas.delete(item_id)
        self.lyric_items = []

        w = self.winfo_width(); h = self.winfo_height()
        if w < 100: w = config.START_WIDTH; h = config.START_HEIGHT
        cx = w / 2

        if not self.time_points:
            # 无歌词时显示音符
            lrc_y = h * 0.60
            item_id = self.canvas.create_text(
                cx, lrc_y, text="♪",
                font=(utils.REAL_FONT_NAME, 20),
                fill="#888888", anchor="center"
            )
            self.lyric_items.append(item_id)
            return

        # 歌词区域的中心Y坐标
        lrc_center_y = h * 0.63

        # 显示5行以实现平滑过渡：上上行、上一行、当前行、下一行、下下行
        for offset in [-2, -1, 0, 1, 2]:
            idx = self.active_lyric_index + offset
            if 0 <= idx < len(self.time_points):
                t = self.time_points[idx]
                text = self.lyrics_map[t]

                # Y坐标 = 中心 + 相对偏移 + 滚动动画偏移
                y_pos = lrc_center_y + (offset * config.LYRIC_LINE_HEIGHT) + self.lyric_scroll_offset

                # 只绘制中间可见的区域（动态调整，在滚动时扩大下方范围）
                visible_range = config.LYRIC_LINE_HEIGHT * 1.38
                if lrc_center_y - visible_range < y_pos < lrc_center_y + visible_range:
                    is_active = (idx == self.active_lyric_index)
                    color = "white" if is_active else "#888888"
                    size = config.LYRIC_FONT_SIZE if is_active else config.LYRIC_FONT_SIZE_SUB
                    weight = "bold" if is_active else "normal"

                    item_id = self.canvas.create_text(
                        cx, y_pos, text=text,
                        font=(utils.REAL_FONT_NAME, size, weight),
                        fill=color, anchor="center", width=w-80
                    )
                    self.lyric_items.append(item_id)



    def animate_lyrics(self):
        """每一帧平滑更新滚动位置"""
        # 计算当前位置与目标位置的差距
        diff = self.target_scroll_offset - self.lyric_scroll_offset

        # 如果差距大于 0.5 像素，则继续滑动
        if abs(diff) > 0.5:
            self.lyric_scroll_offset += diff * config.LYRIC_SMOOTHING
            self.draw_lyrics_on_canvas()

        # 保持 60FPS 循环
        self.after(config.LYRIC_REFRESH_RATE, self.animate_lyrics)

    def on_resize(self, event):
        if event.widget == self:
            if self.resize_timer: self.after_cancel(self.resize_timer)
            self.resize_timer = self.after(50, lambda: self.update_visuals(None))
            
            # 如果下拉菜单是打开的，重新计算目标高度
            if self.dropdown_visible:
                self.after(60, self.update_dropdown_height)
    
    def update_dropdown_height(self):
        """更新下拉菜单的目标高度"""
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 100:
            w = config.START_WIDTH
            h = config.START_HEIGHT
        
        # 封面底部位置
        cover_y = h * 0.26
        max_size = int(w * config.WIDTH_RATIO)
        max_h = int(h * config.ALBUM_HEIGHT_RATIO)
        size = min(max_size, max_h)
        cover_bottom = cover_y + size / 2
        
        # 更新目标高度
        self.dropdown_target_height = int(cover_bottom + 20)
        self.animate_dropdown()

    def on_prog_click(self, event):
        self.update_drag_pos(event.x)
        self.is_dragging = True
        
    def on_prog_drag(self, event):
        self.update_drag_pos(event.x)
        
    def on_prog_release(self, event):
        if self.playlist and self.total_duration > 0:
            try:
                ratio = (event.x - self.prog_x_start) / self.prog_width
                ratio = max(0, min(1, ratio))
                target = ratio * self.total_duration
                pygame.mixer.music.play(start=target)
                self.seek_offset = target
                self.is_playing = True
                self.canvas.itemconfig(self.btn_objects["play"]["id"], image=self.refs["btn_pause"])
            except: pass
        self.is_dragging = False

    def update_drag_pos(self, mouse_x):
        x = max(self.prog_x_start, min(mouse_x, self.prog_x_end))
        y = self.canvas.coords(self.id_prog_bg)[1]
        self.canvas.coords(self.id_prog_fg, self.prog_x_start, y, x, y)

    def on_drop(self, event):
        raw = event.data
        if raw.startswith('{') and raw.endswith('}'): raw = raw[1:-1]
        valid = []
        if os.path.exists(raw): valid.append(raw)
        else:
            for p in re.findall(r'\{.*?\}|\S+', raw):
                if os.path.exists(p.strip('{}')): valid.append(p.strip('{}'))
        valid = [f for f in valid if f.lower().endswith(('.mp3', '.wav', '.flac', '.m4a'))]
        if valid:
            # 将新文件添加到播放列表末尾
            new_count = len(valid)
            start_index = len(self.playlist)  # 记录添加前的位置
            self.playlist.extend(valid)
            # 如果当前没有播放或播放列表只有新添加的歌曲，则播放第一首
            if self.current_index == -1 or len(self.playlist) == new_count:
                self.current_index = 0
                self.play_index(0)
            
            # 如果下拉菜单是打开的，只追加新歌曲
            if self.dropdown_visible:
                self.append_songs_to_playlist(valid, start_index)

    def load_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Audio", "*.mp3 *.wav *.flac *.m4a")])
        if files:
            files_list = list(files)
            new_count = len(files_list)
            start_index = len(self.playlist)  # 记录添加前的位置
            # 将新文件添加到播放列表末尾
            self.playlist.extend(files_list)
            # 如果当前没有播放或播放列表只有新添加的歌曲，则播放第一首
            if self.current_index == -1 or len(self.playlist) == new_count:
                self.current_index = 0
                self.play_index(0)
            
            # 如果下拉菜单是打开的，只追加新歌曲
            if self.dropdown_visible:
                self.append_songs_to_playlist(files_list, start_index)

    def play_index(self, index):
        if not self.playlist: return
        try: pygame.mixer.music.unload()
        except: pass
        self.current_index = index
        path = self.playlist[index]
        
        t, a, d, c = metadata.get_track_info(path)
        self.canvas.itemconfig(self.id_title, text=t)
        self.canvas.itemconfig(self.id_artist, text=a)
        
        self.total_duration = d
        self.seek_offset = 0
        
        # ===== 歌词获取策略（优先级从高到低） =====
        # 1. 首先尝试从文件内嵌歌词获取
        self.lyrics_map, self.time_points = metadata.get_lyrics(path)
        
        # 2. 如果没有内嵌歌词，检查本地 sinf 文件夹缓存
        if not self.lyrics_map and self.enable_online_fetch:
            cached_lyrics, cached_times = self._load_lyrics_from_sinf(t)
            if cached_lyrics:
                self.lyrics_map = cached_lyrics
                self.time_points = cached_times
                print(f"[本地缓存] ✓ 使用本地歌词: {t}.lrc")
            else:
                # 显示 loading 提示
                self._show_loading_text("正在获取歌词...")
                
                # 3. 如果缓存也没有，尝试在线获取
                print(f"[实验性功能] 歌曲无内嵌歌词且无本地缓存，尝试在线获取...")
                try:
                    online_lyrics, online_times = online_fetcher.fetch_lyrics_online(t, a)
                    if online_lyrics:
                        self.lyrics_map = online_lyrics
                        self.time_points = online_times
                except Exception as e:
                    print(f"[实验性功能] 在线获取歌词失败: {e}")
        
        self.active_lyric_index = -1

        # 重置滚动位置
        self.lyric_scroll_offset = 0
        self.target_scroll_offset = 0
        self.draw_lyrics_on_canvas()
        
        # ===== 封面获取策略（优先级从高到低） =====
        cover_to_use = c
        # 1. 如果没有内嵌封面，检查本地 sinf 文件夹缓存
        if self.enable_online_fetch and c == metadata.get_default_cover():
            cached_cover = self._load_cover_from_sinf(t)
            if cached_cover:
                cover_to_use = cached_cover
                print(f"[本地缓存] ✓ 使用本地封面: {t}.jpg")
            else:
                # 显示 loading 提示
                self._show_loading_text("正在获取封面...")
                
                # 2. 如果缓存也没有，尝试在线获取
                print(f"[实验性功能] 歌曲无内嵌封面且无本地缓存，尝试在线获取...")
                try:
                    online_cover = online_fetcher.fetch_cover_online(t, a)
                    if online_cover:
                        cover_to_use = online_cover
                except Exception as e:
                    print(f"[实验性功能] 在线获取封面失败: {e}")

        self.update_visuals(cover_to_use)

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self.is_playing = True
            self.canvas.itemconfig(self.btn_objects["play"]["id"], image=self.refs["btn_pause"])
            self.monitor()
        except: pass
    
    def _show_loading_text(self, message):
        """在歌词位置显示loading提示"""
        # 清除旧的歌词显示
        for item_id in self.lyric_items:
            self.canvas.delete(item_id)
        self.lyric_items = []
        
        # 显示loading文本
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 100:
            w = config.START_WIDTH
            h = config.START_HEIGHT
        cx = w / 2
        lrc_y = h * 0.63
        
        item_id = self.canvas.create_text(
            cx, lrc_y,
            text=message,
            font=(utils.REAL_FONT_NAME, 12),
            fill="#888888",
            anchor="center"
        )
        self.lyric_items.append(item_id)
        
        # 强制更新画布
        self.canvas.update()
    
    def _load_lyrics_from_sinf(self, title):
        """
        从 sinf 文件夹加载歌词缓存
        :param title: 歌曲标题
        :return: (lyrics_map, time_points) 或 ({}, [])
        """
        try:
            # 创建安全的文件名
            safe_title = self._get_safe_filename(title)
            # 兼容脚本运行和EXE运行
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
            sinf_dir = os.path.join(script_dir, "sinf")
            lrc_path = os.path.join(sinf_dir, f"{safe_title}.lrc")
            
            if os.path.exists(lrc_path):
                # 导入必要的解析函数
                import re
                
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lrc_text = f.read()
                
                # 解析 LRC 格式
                lyrics_map = {}
                time_points = []
                pattern = r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'
                
                for line in lrc_text.split('\n'):
                    match = re.match(pattern, line)
                    if match:
                        minutes = int(match.group(1))
                        seconds = int(match.group(2))
                        milliseconds = int(match.group(3))
                        text = match.group(4).strip()
                        
                        time_in_seconds = minutes * 60 + seconds + milliseconds / 1000
                        
                        if text:
                            lyrics_map[time_in_seconds] = text
                            time_points.append(time_in_seconds)
                
                time_points.sort()
                return lyrics_map, time_points
            
            return {}, []
        except Exception as e:
            print(f"[本地缓存] 加载歌词失败: {e}")
            return {}, []
    
    def _load_cover_from_sinf(self, title):
        """
        从 sinf 文件夹加载封面缓存
        :param title: 歌曲标题
        :return: PIL Image 对象或 None
        """
        try:
            # 创建安全的文件名
            safe_title = self._get_safe_filename(title)
            # 兼容脚本运行和EXE运行
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
            sinf_dir = os.path.join(script_dir, "sinf")
            jpg_path = os.path.join(sinf_dir, f"{safe_title}.jpg")
            
            if os.path.exists(jpg_path):
                from PIL import Image
                cover_image = Image.open(jpg_path)
                return cover_image
            
            return None
        except Exception as e:
            print(f"[本地缓存] 加载封面失败: {e}")
            return None
    
    def _get_safe_filename(self, title):
        """
        生成安全的文件名（移除不合法字符）
        :param title: 歌曲标题
        :return: 安全的文件名
        """
        # 移除文件名中不允许的字符
        invalid_chars = '<>:"/\\|?*'
        safe_name = title
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')
        # 限制文件名长度
        if len(safe_name) > 200:
            safe_name = safe_name[:200]
        return safe_name

    def toggle_play(self):
        if not self.playlist: return
        if self.is_playing:
            pygame.mixer.music.pause(); self.is_playing = False; self.canvas.itemconfig(self.btn_objects["play"]["id"], image=self.refs["btn_play"])
            self.stop_background_animation()  # 暂停时停止动画
        else:
            pygame.mixer.music.unpause(); self.is_playing = True; self.canvas.itemconfig(self.btn_objects["play"]["id"], image=self.refs["btn_pause"])
            self.start_background_animation()  # 播放时启动动画
    
    def start_background_animation(self):
        """启动背景动画"""
        if self.bg_animation_timer is None and self.bg_original_image is not None:
            self._animate_background()
    
    def stop_background_animation(self):
        """停止背景动画"""
        if self.bg_animation_timer is not None:
            self.after_cancel(self.bg_animation_timer)
            self.bg_animation_timer = None
    
    def _animate_background(self):
        """背景动画循环 - Apple Music风格"""
        if not self.is_playing or self.bg_original_image is None:
            self.bg_animation_timer = None
            return
        
        # 增加动画相位
        self.bg_animation_phase += self.bg_animation_speed
        if self.bg_animation_phase >= 4.0:
            self.bg_animation_phase = 0.0  # 循环
        
        # 计算当前偏移量（循环：下 → 右 → 上 → 左）
        phase = self.bg_animation_phase
        offset_x = 0
        offset_y = 0
        
        if phase < 1.0:
            # 阶段1: 向下移动
            offset_y = phase  # 0.0 → 1.0
        elif phase < 2.0:
            # 阶段2: 向右移动
            offset_y = 1.0
            offset_x = phase - 1.0  # 0.0 → 1.0
        elif phase < 3.0:
            # 阶段3: 向上移动
            offset_x = 1.0
            offset_y = 1.0 - (phase - 2.0)  # 1.0 → 0.0
        else:
            # 阶段4: 向左移动
            offset_y = 0.0
            offset_x = 1.0 - (phase - 3.0)  # 1.0 → 0.0
        
        # 转换为 -1.0 到 1.0 的范围（中心为0）
        offset_x = (offset_x - 0.5) * 2  # 0→1 变成 -1→1
        offset_y = (offset_y - 0.5) * 2
        
        # 更新背景
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 100:  # 窗口已初始化
            bg_img = utils.process_background(
                self.bg_original_image, 
                w, h, 
                offset_x, 
                offset_y
            )
            self.tk_bg_ref = ImageTk.PhotoImage(bg_img)
            self.canvas.itemconfig(self.id_bg, image=self.tk_bg_ref)
        
        # 继续动画（约60fps）
        self.bg_animation_timer = self.after(16, self._animate_background)

    def prev_song(self):
        if self.playlist:
            old_index = self.current_index
            new_index = (self.current_index - 1) % len(self.playlist)
            self.play_index(new_index)
            # 更新播放列表高亮
            if self.dropdown_visible:
                self.update_playlist_highlight(old_index, new_index)

    def next_song(self):
        if self.playlist:
            old_index = self.current_index
            new_index = (self.current_index + 1) % len(self.playlist)
            self.play_index(new_index)
            # 更新播放列表高亮
            if self.dropdown_visible:
                self.update_playlist_highlight(old_index, new_index)

    def monitor(self):
        if self.is_playing and not self.is_dragging:
            try:
                raw = pygame.mixer.music.get_pos()
                if raw == -1: raw = 0
                curr = (raw / 1000) + self.seek_offset
                if curr < 0: curr = 0
                if curr > self.total_duration: curr = self.total_duration
                
                if self.total_duration > 0:
                    ratio = curr / self.total_duration
                    curr_x = self.prog_x_start + (self.prog_width * ratio)
                    y = self.canvas.coords(self.id_prog_bg)[1]
                    self.canvas.coords(self.id_prog_fg, self.prog_x_start, y, curr_x, y)
                
                self.canvas.itemconfig(self.id_time_curr, text=utils.fmt_time(curr))
                rem = max(0, self.total_duration - curr)
                self.canvas.itemconfig(self.id_time_total, text=f"-{utils.fmt_time(rem)}")
                
                # 更新歌词
                if self.time_points:
                    new_idx = -1
                    for i, t in enumerate(self.time_points):
                        if t <= curr: new_idx = i
                        else: break

                    if new_idx != -1 and new_idx != self.active_lyric_index:
                        self.active_lyric_index = new_idx
                        # 核心：更新目标滚动位置 = 当前索引 * 行高
                        self.lyric_scroll_offset = config.LYRIC_LINE_HEIGHT
                        self.target_scroll_offset = 0

                if not pygame.mixer.music.get_busy() and (self.total_duration - curr) < 1:
                    self.next_song()
            except: pass
        self.after(500, self.monitor)

if __name__ == "__main__":
    # 显示开屏页面
    splash_screen = splash.SplashScreen()
    splash_screen.show()
    
    # 启动主应用
    app = MusicPlayer()
    app.mainloop()
