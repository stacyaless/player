import os
import ctypes
import tkinter as tk
from tkinter import font
from PIL import Image, ImageFilter, ImageEnhance

def load_font_and_get_name():
    return "Microsoft YaHei UI"

REAL_FONT_NAME = load_font_and_get_name()

def fmt_time(sec):
    return f"{int(sec//60)}:{int(sec%60):02}"

def process_background(pil_img, win_w, win_h, offset_x=0, offset_y=0):
    """
    生成全屏模糊背景图（支持动态偏移）
    :param pil_img: 原始图片
    :param win_w: 窗口宽度
    :param win_h: 窗口高度
    :param offset_x: X轴偏移 (-1.0 到 1.0)
    :param offset_y: Y轴偏移 (-1.0 到 1.0)
    """
    img_ratio = pil_img.width / pil_img.height
    win_ratio = win_w / win_h
    
    # 放大图片以留出移动空间（增加10%的裁剪余量）
    scale_factor = 1.1
    
    if img_ratio > win_ratio:
        new_h = int(win_h * scale_factor)
        new_w = int(new_h * img_ratio)
    else:
        new_w = int(win_w * scale_factor)
        new_h = int(new_w / img_ratio)
        
    bg_resized = pil_img.resize((new_w, new_h), Image.Resampling.BICUBIC)
    
    # 计算可移动的范围
    max_offset_x = (new_w - win_w) / 2
    max_offset_y = (new_h - win_h) / 2
    
    # 应用偏移（offset_x/y 范围 -1.0 到 1.0）
    actual_offset_x = offset_x * max_offset_x * 0.5  # 限制移动幅度为50%
    actual_offset_y = offset_y * max_offset_y * 0.5
    
    # 计算裁剪区域（中心点 + 偏移）
    center_x = new_w / 2
    center_y = new_h / 2
    
    left = center_x - win_w / 2 + actual_offset_x
    top = center_y - win_h / 2 + actual_offset_y
    right = center_x + win_w / 2 + actual_offset_x
    bottom = center_y + win_h / 2 + actual_offset_y
    
    bg_cropped = bg_resized.crop((left, top, right, bottom))
    
    bg_blur = bg_cropped.filter(ImageFilter.GaussianBlur(radius=80))
    
    enhancer = ImageEnhance.Brightness(bg_blur)
    bg_final = enhancer.enhance(0.4)
    
    return bg_final
