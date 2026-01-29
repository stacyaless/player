# splash.py
import tkinter as tk
import utils

class SplashScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Music")
        
        # 窗口设置
        width, height = 600, 350
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.overrideredirect(True)  # 无边框
        self.root.configure(bg="#EEEEEE")
        
        # 创建Canvas
        self.canvas = tk.Canvas(self.root, bg="#EEEEEE", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # 绘制内容
        self.draw_content()
        
        # 1.5秒后关闭
        self.root.after(1500, self.close)
        
    def draw_content(self):
        w, h = 600, 350
        cx, cy = w / 2, h / 2
        
        
        
        # 绘制应用名称
        self.canvas.create_text(
            cx, cy, 
            text="♪Music", 
            font=(utils.REAL_FONT_NAME, 49, "bold"), 
            fill="black"
        )
        
        
    def close(self):
        self.root.destroy()
        
    def show(self):
        self.root.mainloop()
