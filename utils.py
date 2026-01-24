# utils.py
import os
import ctypes
import tkinter as tk
from tkinter import font
from PIL import Image, ImageFilter, ImageStat, ImageEnhance

def load_font_and_get_name():
    """Loads font from ./fonts folder and finds its system name."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # UPDATE THIS FILENAME IF NEEDED
    font_filename = "AlibabaPuHuiTi-3-65-Medium.ttf" 
    font_path = os.path.join(current_dir, "fonts", font_filename)
    detected_name = "Arial"

    if not os.path.exists(font_path):
        return detected_name

    try:
        # Load font into Windows memory
        gdi32 = ctypes.windll.gdi32
        FR_PRIVATE = 0x10
        path_buf = ctypes.create_unicode_buffer(font_path)
        gdi32.AddFontResourceExW(path_buf, FR_PRIVATE, 0)
        
        # Find the actual family name
        temp_root = tk.Tk()
        all_fonts = font.families()
        temp_root.destroy()

        candidates = ["Alibaba PuHuiTi 3.0", "Alibaba PuHuiTi 3.0 Medium", "Alibaba PuHuiTi", "Alibaba Sans"]
        found = False
        for f in all_fonts:
            if f in candidates:
                detected_name = f
                found = True
                break
        if not found:
            for f in all_fonts:
                if "Alibaba" in f:
                    detected_name = f
                    found = True
                    break
    except Exception as e:
        print(f"Font Load Error: {e}")
    
    return detected_name

# Global font name
REAL_FONT_NAME = load_font_and_get_name()

def fmt_time(sec):
    return f"{int(sec//60)}:{int(sec%60):02}"

def get_avg_color(pil_img):
    try:
        small = pil_img.resize((1, 1))
        color = small.getpixel((0, 0))
        r = int(color[0] * 0.5)
        g = int(color[1] * 0.5)
        b = int(color[2] * 0.5)
        return f"#{r:02x}{g:02x}{b:02x}"
    except:
        return "#1a1a1a"

def process_background(pil_img, win_w, win_h):
    """Generates a blurred, darkened background image that fills the window."""
    img_ratio = pil_img.width / pil_img.height
    win_ratio = win_w / win_h
    
    # Aspect Fill calculation
    if img_ratio > win_ratio:
        new_h = win_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = win_w
        new_h = int(new_w / img_ratio)
        
    bg_resized = pil_img.resize((new_w, new_h), Image.Resampling.BICUBIC)
    
    # Center Crop
    left = (new_w - win_w) / 2
    top = (new_h - win_h) / 2
    bg_cropped = bg_resized.crop((left, top, left + win_w, top + win_h))
    
    # Blur
    bg_blur = bg_cropped.filter(ImageFilter.GaussianBlur(radius=50))
    
    # Darken
    enhancer = ImageEnhance.Brightness(bg_blur)
    bg_blur = enhancer.enhance(0.4)
    
    # Extract color for buttons
    bottom_crop = bg_blur.crop((0, win_h//2, win_w, win_h))
    color = get_avg_color(bottom_crop)
    
    return bg_blur, color
