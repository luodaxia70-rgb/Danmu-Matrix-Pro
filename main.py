# ===============================================================
# == 弹幕矩阵机 PRO v4.2 (UI修复版)
# == 阿b搜索: 来陪小狗玩 (免费获取开源代码)
# == 
# == 修复日志:
# == 1. 修复悬浮窗高度过小导致[省流]按钮消失的问题。
# == 2. 保持[防折叠短句]引擎。
# == 3. 保持极简界面，移除暖场设置。
# ===============================================================
import time
import random
import threading
import os
import sys
import json 
import tkinter as tk
from tkinter import messagebox, simpledialog, Toplevel, Label, Entry, Button
from concurrent.futures import ThreadPoolExecutor
import keyboard
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException

# ================= 🔓 开源核心配置 =================
CONFIG_FILE = "Matrix_Config_OpenSource.json" 

# 📢 默认锁定的宣传口令
DEFAULT_AD_TEXT = "免费无畏契约夜市多账户弹幕口令抽奖,代码开源地址:https://github.com/luodaxia70-rgb/Danmu-Matrix-Pro."

# 默认配置
DEFAULT_CONFIG = {
    "global": {
        "stagger": 0.04,   # 错落延迟
        "cooldown": 0.2    # 冷却时间
    }
}

# ================= 💾 配置持久化模块 =================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config_to_file():
    data = { "global": GLOBAL_CONFIG }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"配置保存失败: {e}")

# 初始化配置
_loaded_data = load_config()
GLOBAL_CONFIG = _loaded_data.get("global", DEFAULT_CONFIG["global"])

# 全局状态
drivers = []
ELEMENT_CACHE = {} 
running_msg = False  
eco_mode = False     
current_msg = DEFAULT_AD_TEXT 
dashboard_win = None 
status_label = None 
eco_label = None     
root = None 

# ================= 🛡️ 防折叠引擎 (表情+短句) =================
def get_anti_fold_suffix():
    # 1. 表情池
    emoji_pool = [
        "🥛", "🍰", "🎂", "💎", "🍀", "🎀", "🎈", "🧸", "✨", "💖", 
        "🍓", "🍒", "🍭", "🍦", "🦄", "🌈", "🪐", "💫", "👑", "💍",
        "🍬", "🍪", "🧊", "🍹", "🌙", "⭐", "🦋", "🌷", "🌹", "🔥"
    ]
    
    # 2. 防折叠短句池
    anti_fold_texts = [
        "(字数多是为了降低重复率，防弹幕被折叠",
        "(长文本在屏幕停留时间更久，权重更高,",
        "(有意义的汉字组合权重比纯表情高",
        "(多打几个字是为了防止系统折叠弹幕o(TヘTo)",
        "(长文本降低被系统折叠的概率",
        "(字多一点是防止被识别为刷屏口号隐藏,",
        "(别禁言，这是为了增加弹幕的有效曝光时长",
        "(文字越长重复率越低，直播间热度才更真实,",
        "(汉字比表情更有利于算法推荐",
        "(偷得浮生半日闲"

    ]

    selected_text = random.choice(anti_fold_texts)
    selected_emojis = "".join(random.sample(emoji_pool, random.randint(2, 4)))
    
    return f" {selected_text}{selected_emojis}"

# ================= 🍃 智能省流 (主号保留声画) =================
def toggle_eco_mode():
    global eco_mode
    eco_mode = not eco_mode
    update_status_display()
    
    # 逻辑：除第0个主窗口外，其余窗口暂停视频并静音
    js_pause = "document.querySelectorAll('video').forEach(v => { v.pause(); v.muted=true; });"
    js_play  = "document.querySelectorAll('video').forEach(v => { v.muted=true; v.play(); });"
    
    script = js_pause if eco_mode else js_play

    def apply_js(index, driver):
        if index == 0: return # 跳过主账号
        try:
            driver.execute_script(script)
        except:
            pass

    with ThreadPoolExecutor(max_workers=len(drivers) + 1) as executor:
        for i, driver in enumerate(drivers):
            executor.submit(apply_js, i, driver)

# ================= 🔄 刷新与功能逻辑 =================
def refresh_single_driver(driver):
    global ELEMENT_CACHE
    try: 
        driver.refresh()
        if driver in ELEMENT_CACHE:
            del ELEMENT_CACHE[driver]
    except: pass

def refresh_all_drivers():
    if not drivers: return
    
    global running_msg, eco_mode
    was_running_msg = running_msg
    
    running_msg = False
    eco_mode = False 
    update_status_display()
    
    if status_label:
        status_label.config(text="⏳ 全局刷新中...", fg="cyan")
    
    ELEMENT_CACHE.clear()
    
    with ThreadPoolExecutor(max_workers=len(drivers)) as executor:
        for driver in drivers:
            executor.submit(refresh_single_driver, driver)
            
    time.sleep(2)
    if was_running_msg:
        running_msg = True
    update_status_display()

# ================= 🛸 悬浮仪表盘 =================
def create_dashboard():
    global dashboard_win, status_label, eco_label
    if dashboard_win: return
    
    dashboard_win = Toplevel()
    dashboard_win.title("监控")
    # 🌟 修复：增加高度到 150，确保两排按钮都能显示
    dashboard_win.geometry("260x150+50+50") 
    dashboard_win.attributes("-topmost", True)
    dashboard_win.overrideredirect(True)
    dashboard_win.configure(bg="#1e1e1e")
    dashboard_win.attributes("-alpha", 0.92)
    
    def start_move(event):
        dashboard_win.x = event.x
        dashboard_win.y = event.y
    def do_move(event):
        x = dashboard_win.winfo_x() + (event.x - dashboard_win.x)
        y = dashboard_win.winfo_y() + (event.y - dashboard_win.y)
        dashboard_win.geometry(f"+{x}+{y}")
        
    dashboard_win.bind("<Button-1>", start_move)
    dashboard_win.bind("<B1-Motion>", do_move)
    
    Label(dashboard_win, text="🚀 矩阵监控 (开源版)", font=("微软雅黑", 9, "bold"), bg="#1e1e1e", fg="#ddd").pack(pady=5)
    status_label = Label(dashboard_win, text="状态: ⏸️ 待机", font=("微软雅黑", 10), bg="#1e1e1e", fg="yellow")
    status_label.pack()
    
    eco_label = Label(dashboard_win, text=f"画质: 原画", font=("Arial", 8), bg="#1e1e1e", fg="#aaa")
    eco_label.pack(pady=2)

    # 第一排按钮
    row1 = tk.Frame(dashboard_win, bg="#1e1e1e")
    row1.pack(pady=3)
    Button(row1, text="📝 改字 F9", font=("Arial", 9, "bold"), bg="#ff9900", fg="white", bd=0, width=10,
           command=lambda: root.after(0, safe_set_message)).pack(side="left", padx=2)
    Button(row1, text="💬 弹幕 F8", font=("Arial", 9, "bold"), bg="#444", fg="white", bd=0, width=10,
           command=lambda: root.after(0, safe_toggle_msg)).pack(side="left", padx=2)
    
    # 第二排按钮 (省流 + 刷新)
    row2 = tk.Frame(dashboard_win, bg="#1e1e1e")
    row2.pack(pady=3)
    Button(row2, text="🍃 省流", font=("Arial", 9), bg="#5bc0de", fg="white", bd=0, width=10,
           command=lambda: threading.Thread(target=toggle_eco_mode).start()).pack(side="left", padx=2)
    Button(row2, text="🔄 刷新", font=("Arial", 9), bg="#5cb85c", fg="white", bd=0, width=10,
           command=lambda: threading.Thread(target=refresh_all_drivers).start()).pack(side="left", padx=2)

    Label(dashboard_win, text="按住拖动 | F8 启停", font=("Arial", 7), bg="#1e1e1e", fg="#555").pack(side="bottom", pady=2)

def update_status_display():
    if not status_label: return
    
    if running_msg:
        state_text = "🔥 弹幕轰炸"
        color = "#00ff00" 
    else:
        state_text = "⏸️ 全部待机"
        color = "yellow"
        
    display_msg = current_msg if len(current_msg) < 8 else current_msg[:8]+".."
    status_label.config(text=f"{state_text} | 口令: {display_msg or '空'}", fg=color)
    
    if eco_mode:
        eco_label.config(text=f"🍃 主号播放/小号暂停", fg="#5bc0de")
    else:
        eco_label.config(text=f"📺 全员正常播放", fg="#aaa")

# ================= 🛠️ 核心功能区 =================
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
DATA_DIR = os.path.join(BASE_DIR, "Matrix_Data")

def get_all_profiles():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    return [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]

def add_new_account():
    name = simpledialog.askstring("添加节点", "请输入节点编号 (例如: by1, by2, me):")
    if not name: return
    profile_path = os.path.join(DATA_DIR, name)
    messagebox.showinfo("提示", "即将打开浏览器，请扫码登录。\n登录成功后，直接【关闭浏览器】即可自动保存。")
    
    edge_options = Options()
    edge_options.add_argument(f"--user-data-dir={profile_path}")
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = webdriver.Edge(options=edge_options)
    driver.get("https://www.douyin.com")
    while True:
        try:
            _ = driver.window_handles
            time.sleep(1)
        except: break
    update_dashboard_ui()

def launch_single_browser(index, profile_name, url, position_step):
    try:
        profile_path = os.path.join(DATA_DIR, profile_name)
        edge_options = Options()
        edge_options.add_argument(f"--user-data-dir={profile_path}")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        edge_options.add_argument("--log-level=3")
        edge_options.add_argument("--disable-gpu-shader-disk-cache")
        edge_options.add_argument("--disable-extensions") 
        
        driver = webdriver.Edge(options=edge_options)
        
        driver.set_window_size(966, 630)
        driver.set_window_position(index * position_step, 0)
        
        if url:
            try: driver.get(url)
            except: pass
            
        return driver
    except Exception as e:
        print(f"❌ 节点 {profile_name} 启动失败: {e}")
        return None

def start_matrix():
    global drivers
    profiles = get_all_profiles()
    if not profiles:
        messagebox.showwarning("警告", "节点列表为空！请先添加账号。")
        return
        
    url = simpledialog.askstring("启动", "请输入直播间网址 (留空手动进入):")
    root.iconify() 
    create_dashboard()
    
    position_step = 300 
    drivers = []
    
    print(f"🚀 正在启动 {len(profiles)} 个矩阵节点...")
    
    with ThreadPoolExecutor(max_workers=len(profiles)) as executor:
        futures = []
        for i, profile_name in enumerate(profiles):
            futures.append(executor.submit(launch_single_browser, i, profile_name, url, position_step))
        
        for f in futures:
            driver = f.result()
            if driver:
                drivers.append(driver)
    
    t = threading.Thread(target=worker_loop)
    t.daemon = True
    t.start()

# ================= ⌨️ 互斥控制逻辑 =================
def safe_toggle_msg():
    global running_msg
    if not current_msg and not running_msg:
        safe_set_message()
        if not current_msg: return
    running_msg = not running_msg
    update_status_display()

def ask_string_topmost(title, prompt):
    dialog = Toplevel()
    dialog.title(title)
    dialog.configure(bg="#f0f0f0")
    dialog.attributes("-topmost", True)
    dialog.grab_set() 
    dialog.focus_force()

    sw = dialog.winfo_screenwidth()
    sh = dialog.winfo_screenheight()
    x = (sw - 400) // 2
    y = (sh - 250) // 2
    dialog.geometry(f"400x180+{x}+{y}")

    Label(dialog, text=prompt, font=("微软雅黑", 14, "bold"), bg="#f0f0f0").pack(pady=20)
    
    entry_var = tk.StringVar()
    entry = Entry(dialog, textvariable=entry_var, font=("Consolas", 12), width=30, bd=2, relief="groove")
    entry.insert(0, current_msg)
    entry.pack(pady=5)
    entry.select_range(0, 'end')
    entry.focus_set() 

    result = [None]
    def on_ok(event=None):
        val = entry.get().strip()
        if val: result[0] = val
        dialog.destroy()
    def on_cancel(event=None):
        dialog.destroy()
    btn_frame = tk.Frame(dialog, bg="#f0f0f0")
    btn_frame.pack(pady=20)
    Button(btn_frame, text="✅ 确定", command=on_ok, width=12, bg="#007acc", fg="white", font=("微软雅黑", 10)).pack(side="left", padx=10)
    Button(btn_frame, text="❌ 取消", command=on_cancel, width=10, font=("微软雅黑", 10)).pack(side="left", padx=10)
    dialog.bind("<Return>", on_ok)
    dialog.bind("<Escape>", on_cancel)
    dialog.wait_window() 
    return result[0]

def safe_set_message():
    global current_msg, running_msg
    was = running_msg
    running_msg = False
    update_status_display()
    msg = ask_string_topmost("设置口令 (F9)", "📢 请输入新的弹幕口令:")
    if msg: current_msg = msg
    running_msg = was 
    update_status_display()

def on_set_msg(): root.after(0, safe_set_message)
def on_toggle_msg(): root.after(0, safe_toggle_msg)
def on_quit(): root.after(0, stop_all)

# ================= ⚡ 核心执行逻辑 =================

def get_cached_element(driver, key, locator):
    if driver not in ELEMENT_CACHE:
        ELEMENT_CACHE[driver] = {}
    try:
        el = ELEMENT_CACHE[driver].get(key)
        if el: return el
        el = driver.find_element(*locator)
        ELEMENT_CACHE[driver][key] = el
        return el
    except Exception:
        return None

def task_send_msg(driver, text):
    try:
        final_text = f"{text}{get_anti_fold_suffix()}"
        input_box = get_cached_element(driver, 'input_box', (By.CSS_SELECTOR, "div[contenteditable='true']"))
        
        if not input_box: return 
        
        actions = ActionChains(driver)
        actions.move_to_element(input_box).click()
        actions.send_keys(final_text)
        actions.send_keys(Keys.ENTER)
        actions.pause(0.05)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        
    except StaleElementReferenceException:
        if driver in ELEMENT_CACHE: del ELEMENT_CACHE[driver]
    except: pass

def worker_loop():
    executor = ThreadPoolExecutor(max_workers=20)
    while True:
        if not running_msg:
            time.sleep(1.0) 
            continue

        if running_msg and current_msg and drivers:
            stagger = GLOBAL_CONFIG["stagger"]
            cooldown = GLOBAL_CONFIG["cooldown"]
            for driver in drivers:
                if not running_msg: break
                executor.submit(task_send_msg, driver, current_msg)
                time.sleep(stagger) 
            time.sleep(cooldown)
        else:
            time.sleep(0.1)

def stop_all():
    global drivers
    for d in drivers:
        try: d.quit()
        except: pass
    os._exit(0)

# ================= 🖥️ 界面设置逻辑 =================
def update_dashboard_ui():
    profiles = get_all_profiles()
    lbl_count.config(text=f"当前节点数: {len(profiles)}")
    if len(profiles) == 0:
        lbl_tips.config(text="⚠ 请添加至少一个节点", fg="red")
    else:
        lbl_tips.config(text="✅ 系统就绪", fg="green")

def open_settings():
    win = Toplevel(root)
    win.title("参数调优")
    win.geometry("300x180")
    
    Label(win, text="错落延迟 (s):").pack(pady=2)
    e1 = Entry(win); e1.insert(0, str(GLOBAL_CONFIG["stagger"])); e1.pack()
    
    Label(win, text="冷却时间 (s):").pack(pady=2)
    e2 = Entry(win); e2.insert(0, str(GLOBAL_CONFIG["cooldown"])); e2.pack()
    
    def save():
        try:
            GLOBAL_CONFIG["stagger"] = float(e1.get())
            GLOBAL_CONFIG["cooldown"] = float(e2.get())
            save_config_to_file() 
            win.destroy()
            messagebox.showinfo("成功", "参数已保存")
        except: messagebox.showerror("错误", "请输入数字")
    Button(win, text="保存", command=save).pack(pady=10)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("弹幕矩阵机 - 开源分享版")
    root.geometry("480x360") 
    
    keyboard.add_hotkey('esc+`', on_quit) 
    keyboard.add_hotkey('f9', on_set_msg)      
    keyboard.add_hotkey('f8', on_toggle_msg)   
    
    tk.Label(root, text="🚀 弹幕矩阵机 (开源版)", font=("微软雅黑", 16, "bold"), fg="#007acc").pack(pady=15)
    tk.Label(root, text="阿b搜索: 来陪小狗玩 | 免费获取", font=("微软雅黑", 10), fg="gray").pack()

    lbl_count = tk.Label(root, text="扫描中...", font=("微软雅黑", 12))
    lbl_count.pack(pady=10)
    lbl_tips = tk.Label(root, text="", font=("微软雅黑", 10))
    lbl_tips.pack(pady=5)
    
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="➕ 添加节点", width=12, height=2, command=add_new_account).grid(row=0, column=0, padx=5)
    tk.Button(btn_frame, text="⚙️ 极速参数", width=12, height=2, command=open_settings).grid(row=0, column=1, padx=5)
    
    tk.Button(root, text="▶ 启动矩阵 (Launch)", width=30, height=2, bg="#007acc", fg="white", font=("微软雅黑", 10, "bold"), command=start_matrix).pack(pady=20)
    
    tk.Label(root, text="快捷键: [F9] 设置口令  |  [F8] 启/停弹幕", fg="gray", font=("微软雅黑", 9)).pack(side="bottom", pady=15)
    
    update_dashboard_ui()
    root.mainloop()