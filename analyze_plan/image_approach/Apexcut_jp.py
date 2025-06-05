import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import logging
import threading
from urllib.parse import urlparse
import subprocess
import sys # For platform-specific open

# Assuming these files are in the same directory
# analysis_functions と general_function, clip_functions は同じディレクトリにあると仮定します
# また、WEAPON_METADATA はこのスクリプト内で定義されるため、analysis_functions からのインポートは変更されます
# from analysis_functions import find_shooting_moments, WEAPON_METADATA # Import WEAPON_METADATA
from analysis_functions import find_shooting_moments, WEAPON_METADATA
from general_function import download_twitch, hms_to_seconds, seconds_to_hms #
# Import the new merge function as well
from clip_functions import clip_video_ffmpeg, generate_clips_from_multiple_weapon_times, clip_video_ffmpeg_merged, clip_video_ffmpeg_with_duration, process_and_merge_times, generate_clips_from_multiple_weapon_times_merge, generate_concatenated_video_from_timestamps #

# --- GUIおよび適応されたメインロジック用のロガー ---

class TextHandler(logging.Handler): #
    def __init__(self, text_widget): #
        logging.Handler.__init__(self) #
        self.text_widget = text_widget #
        self.text_widget.configure(state='disabled') #

    def emit(self, record): #
        msg = self.format(record) #
        def append(): #
            self.text_widget.configure(state='normal') #
            self.text_widget.insert(tk.END, msg + '\n') #
            self.text_widget.see(tk.END) #
            self.text_widget.configure(state='disabled') #
        self.text_widget.after(0, append) #

class VideoProcessingGUI:
    def __init__(self, master):
        self.master = master
        master.title("ApexTool(ベータ版)") #
        master.geometry("900x850") # より多くのパラメータに対応するため高さを調整

        self.style = ttk.Style() #
        self.style.theme_use('clam') #

        self.default_root = os.path.expanduser("~") #
        self.default_log_file = os.path.join(self.default_root, "Apex_tool(beta)_jp.log") # ログファイル名を変更
        
        self.file_handler = None # 現在のファイルハンドラを追跡するため

        self.params = {
            "NUMBER_ROI_X1": tk.StringVar(value="1723"), "NUMBER_ROI_Y1": tk.StringVar(value="958"), #
            "NUMBER_ROI_X2": tk.StringVar(value="1787"), "NUMBER_ROI_Y2": tk.StringVar(value="1002"), #
            "NUMBER_MID": tk.StringVar(value="1754"), #
            "BOW_ROI_X1": tk.StringVar(value="1554"), "BOW_ROI_Y1": tk.StringVar(value="958"), #
            "BOW_ROI_X2": tk.StringVar(value="1702"), "BOW_ROI_Y2": tk.StringVar(value="998"), #
            "INFINITE_ROI_X1": tk.StringVar(value="1723"), "INFINITE_ROI_Y1": tk.StringVar(value="964"), #
            "INFINITE_ROI_X2": tk.StringVar(value="1782"), "INFINITE_ROI_Y2": tk.StringVar(value="993"), #
            "BOW_SIMILARITY_THRESHOLD": tk.StringVar(value="0.75"), #
            "SIMILARITY_THRESHOLD_INFINITE": tk.StringVar(value="0.74"), #
            "COARSE_SCAN_INTERVAL_SECONDS": tk.StringVar(value="2.8"), #
            "FINE_SCAN_INTERVAL_SECONDS": tk.StringVar(value="0.1"), #
            "CLIP_DURATION": tk.StringVar(value="1.0"), # 新しいパラメータ
            "MERGE_THRESHOLD_FACTOR": tk.StringVar(value="3.0"), # 新しいパラメータ (秒単位に変更)
            "START_TIME": tk.StringVar(value="00:00:00.000"), #
            "ROOT": tk.StringVar(value=self.default_root), #
            "LOG_FILE_PATH": tk.StringVar(value=self.default_log_file) #
        }

        self.selected_parts_vars = { #
            '1': tk.BooleanVar(value=False), '2': tk.BooleanVar(value=False), #
            '4': tk.BooleanVar(value=False), '5': tk.BooleanVar(value=False), #
            '6': tk.BooleanVar(value=False) #
        }
        self.part3_enabled = tk.BooleanVar(value=False) #
        self.part3_clip_mode = tk.StringVar(value="individual") #
        
        self.video_checkbox_vars = {} #
        self.selected_weapons_vars = { #
            weapon_name: tk.BooleanVar(value=False) for weapon_name in WEAPON_METADATA.keys()
        }

        self.create_widgets() 
        self._setup_gui_text_handler_and_initial_root_config()

    def _setup_gui_text_handler_and_initial_root_config(self):
        self.text_widget_handler = TextHandler(self.log_text_widget)
        gui_formatter = logging.Formatter("%(asctime)s [%(levelname)s] (%(name)s): %(message)s", "%H:%M:%S") #
        self.text_widget_handler.setFormatter(gui_formatter) #
        self.text_widget_handler.setLevel(logging.INFO) #

        root_logger = logging.getLogger()
        root_logger.addHandler(self.text_widget_handler)
        root_logger.setLevel(logging.INFO) 

        self.gui_instance_logger = logging.getLogger("VideoProcessingApp.GUI")
        self.gui_instance_logger.info("GUIが初期化されました。ウィンドウへのロギングがアクティブです (INFOレベル)。")

    def _update_file_logging(self, new_log_file_path):
        root_logger = logging.getLogger()

        if self.file_handler:
            root_logger.removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None
            self.gui_instance_logger.info("以前のファイルログハンドラを閉じました。")

        log_dir = os.path.dirname(new_log_file_path)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                self.gui_instance_logger.info(f"ログディレクトリを作成しました: {log_dir}")
            except Exception as e:
                self.gui_instance_logger.error(f"ログディレクトリ {log_dir} の作成に失敗しました: {e}")
        
        try:
            self.file_handler = logging.FileHandler(new_log_file_path, mode='a', encoding='utf-8')
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s](%(module)s.%(funcName)s): %(message)s", #
                "%Y-%m-%d %H:%M:%S" #
            )
            self.file_handler.setFormatter(file_formatter)
            self.file_handler.setLevel(logging.DEBUG) 

            root_logger.addHandler(self.file_handler)
            root_logger.setLevel(logging.DEBUG) 

            logging.info(f"ファイルロギングを {new_log_file_path} に設定しました。ルートロガーのレベルはDEBUGです。")
            logging.debug("これは _update_file_logging 後のファイルへのテストデバッグメッセージです。")
        except Exception as e:
            self.gui_instance_logger.error(f"{new_log_file_path} へのファイルロギング設定に失敗しました: {e}")


    def create_widgets(self):
        main_frame = ttk.Frame(self.master, padding="5") # パディングを削減
        main_frame.pack(fill=tk.BOTH, expand=True) #

        paths_frame = ttk.LabelFrame(main_frame, text="設定パス", padding="5") # パディングを削減
        paths_frame.pack(fill=tk.X, expand=False, pady=3, anchor=tk.N) # padyを削減
        ttk.Label(paths_frame, text="ルートプロジェクトディレクトリ:").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W) # padyを削減
        self.root_entry = ttk.Entry(paths_frame, textvariable=self.params["ROOT"], width=50) #
        self.root_entry.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW) # padyを削減
        ttk.Button(paths_frame, text="参照", command=lambda: self.browse_directory(self.params["ROOT"])).grid(row=0, column=2, padx=5, pady=3) # padyを削減
        ttk.Label(paths_frame, text="ログファイルパス:").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W) # padyを削減
        self.log_file_entry = ttk.Entry(paths_frame, textvariable=self.params["LOG_FILE_PATH"], width=50) #
        self.log_file_entry.grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW) # padyを削減
        ttk.Button(paths_frame, text="ログ参照", command=lambda: self.browse_file(self.params["LOG_FILE_PATH"], save=True)).grid(row=1, column=2, padx=5, pady=3) # padyを削減
        self.open_urls_button = ttk.Button(paths_frame, text="video_urls.txtを編集", command=self.open_video_urls_txt) #
        self.open_urls_button.grid(row=0, column=3, rowspan=2, padx=10, pady=3, sticky="nsew") # padyを削減
        paths_frame.columnconfigure(1, weight=1) #

        params_frame = ttk.LabelFrame(main_frame, text="分析パラメータ", padding="5") # パディングを削減
        params_frame.pack(fill=tk.X, expand=False, pady=3, anchor=tk.N) # padyを削減
        param_layout = [ #
            [("数字ROI (X1 Y1 X2 Y2 M):", ["NUMBER_ROI_X1", "NUMBER_ROI_Y1", "NUMBER_ROI_X2", "NUMBER_ROI_Y2", "NUMBER_MID"])], #
            [("武器画像ROI (X1 Y1 X2 Y2):", ["BOW_ROI_X1", "BOW_ROI_Y1", "BOW_ROI_X2", "BOW_ROI_Y2"])],
            [("ボウ無限ROI (X1 Y1 X2 Y2):", ["INFINITE_ROI_X1", "INFINITE_ROI_Y1", "INFINITE_ROI_X2", "INFINITE_ROI_Y2"])], #
            [("武器画像しきい値:", ["BOW_SIMILARITY_THRESHOLD"]), ("ボウ無限しきい値:", ["SIMILARITY_THRESHOLD_INFINITE"])],
            [("粗スキャン(秒):", ["COARSE_SCAN_INTERVAL_SECONDS"]), ("詳細スキャン(秒):", ["FINE_SCAN_INTERVAL_SECONDS"])], #
            [("分析開始時間 (HH:MM:SS.mmm):", ["START_TIME"], 3)],
            [("クリップ時間(秒):", ["CLIP_DURATION"]), ("マージしきい値(秒):", ["MERGE_THRESHOLD_FACTOR"])]
        ]
        current_row_param = 0 #
        for row_def in param_layout: #
            current_col_param = 0 #
            for item_def in row_def: #
                label_text, param_keys = item_def[0], item_def[1] #
                colspan_val = item_def[2] if len(item_def) > 2 else 1 #
                ttk.Label(params_frame, text=label_text).grid(row=current_row_param, column=current_col_param, padx=5, pady=1, sticky=tk.W) # padyを削減
                current_col_param += 1 #
                entry_frame = ttk.Frame(params_frame) #
                entry_frame.grid(row=current_row_param, column=current_col_param, columnspan=colspan_val * (len(param_keys) if len(param_keys)>1 else 1) , padx=2, pady=1, sticky=tk.W) # 単一エントリが必要に応じてより多くのスペースを取るようにcolspanを調整
                for p_idx, p_key in enumerate(param_keys): #
                    width = 15 if len(param_keys) == 1 and colspan_val > 1 else (10 if len(param_keys) == 1 else 6) # 幅を調整
                    ttk.Entry(entry_frame, textvariable=self.params[p_key], width=width).pack(side=tk.LEFT, padx=1) #
                current_col_param += (colspan_val * (len(param_keys) if len(param_keys) > 1 else 2)) -1 # current_col_paramの増分を調整
            current_row_param += 1 #


        # --- 武器選択フレーム (水平スクロール可能) ---
        weapon_select_outer_frame = ttk.LabelFrame(main_frame, text="分析用武器選択 (パート2 & 3)", padding="5")
        weapon_select_outer_frame.pack(fill=tk.X, expand=False, pady=3, anchor=tk.N)

        weapon_scroll_canvas_container = ttk.Frame(weapon_select_outer_frame)
        weapon_scroll_canvas_container.pack(fill=tk.X, expand=True, pady=(2,0))
        
        self.weapon_scroll_canvas = tk.Canvas(weapon_scroll_canvas_container, height=45) # チェックボックス1行分の高さを調整
        self.weapon_scroll_x = ttk.Scrollbar(weapon_scroll_canvas_container, orient=tk.HORIZONTAL, command=self.weapon_scroll_canvas.xview)
        self.weapon_checkbox_inner_frame = ttk.Frame(self.weapon_scroll_canvas)

        self.weapon_scroll_canvas.configure(xscrollcommand=self.weapon_scroll_x.set)
        self.weapon_scroll_canvas.create_window((0, 0), window=self.weapon_checkbox_inner_frame, anchor="nw")

        self.weapon_scroll_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.weapon_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        for weapon_internal_name, metadata in WEAPON_METADATA.items():
            display_name = metadata.get("display_name_jp", metadata.get("display_name", weapon_internal_name.replace("_", " ").title()))
            cb = ttk.Checkbutton(self.weapon_checkbox_inner_frame, text=display_name, variable=self.selected_weapons_vars[weapon_internal_name])
            cb.pack(side=tk.LEFT, padx=3, pady=2)
        
        self.weapon_checkbox_inner_frame.update_idletasks()
        self.weapon_scroll_canvas.config(scrollregion=self.weapon_scroll_canvas.bbox("all"))
        
        self.weapon_checkbox_inner_frame.bind("<Configure>", lambda e: self.weapon_scroll_canvas.configure(scrollregion=self.weapon_scroll_canvas.bbox("all")))


        weapon_buttons_frame = ttk.Frame(weapon_select_outer_frame) 
        weapon_buttons_frame.pack(fill=tk.X, pady=(3,2))
        ttk.Button(weapon_buttons_frame, text="全武器選択", command=self.select_all_weapons).pack(side=tk.LEFT, padx=5)
        ttk.Button(weapon_buttons_frame, text="全武器選択解除", command=self.deselect_all_weapons).pack(side=tk.LEFT, padx=5)


        tasks_frame = ttk.LabelFrame(main_frame, text="実行するパートを選択", padding="5") 
        tasks_frame.pack(fill=tk.X, expand=False, pady=3, anchor=tk.N) 
        
        ttk.Checkbutton(tasks_frame, text="パート1: 動画ダウンロード", variable=self.selected_parts_vars['1']).grid(row=0, column=0, sticky=tk.W, padx=5, pady=1) 
        ttk.Checkbutton(tasks_frame, text="パート2: 動画分析 (選択武器用)", variable=self.selected_parts_vars['2']).grid(row=0, column=1, sticky=tk.W, padx=5, pady=1) 

        part3_outer_frame = ttk.Frame(tasks_frame) 
        part3_outer_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=0, pady=1)

        self.part3_enable_cb = ttk.Checkbutton(part3_outer_frame, text="パート3: 武器クリップ ", variable=self.part3_enabled, command=self._toggle_part3_options)
        self.part3_enable_cb.pack(side=tk.LEFT, padx=(5,0)) 
        
        self.part3_rb_individual = ttk.Radiobutton(part3_outer_frame, text="個別", variable=self.part3_clip_mode, value="individual", state=tk.DISABLED)
        self.part3_rb_individual.pack(side=tk.LEFT, padx=(5,0))
        self.part3_rb_merged = ttk.Radiobutton(part3_outer_frame, text="近接マージ", variable=self.part3_clip_mode, value="merged", state=tk.DISABLED)
        self.part3_rb_merged.pack(side=tk.LEFT, padx=(5,0))
        self.part3_rb_concatenated = ttk.Radiobutton(part3_outer_frame, text="全て連結", variable=self.part3_clip_mode, value="concatenated", state=tk.DISABLED)
        self.part3_rb_concatenated.pack(side=tk.LEFT, padx=(5,0))
        part_descriptions_rest = { 
            '4': "パート4: ボウ無限クリップ (infinite_2.txtより)", 
            '5': "パート5: ボウTXTマージ (shooting_bow.txt + infinite_3.txt)", 
            '6': "パート6: ボウマージクリップ (shooting_bow_sum.txtより)" 
        }
        
        col_task, row_task = 0, 2 
        for part_num, desc in part_descriptions_rest.items(): 
            ttk.Checkbutton(tasks_frame, text=desc, variable=self.selected_parts_vars[part_num]).grid(row=row_task, column=col_task, sticky=tk.W, padx=5, pady=1) 
            col_task += 1 
            if col_task >= 2: col_task = 0; row_task += 1 
        
        task_buttons_frame = ttk.Frame(tasks_frame) 
        task_buttons_frame.grid(row=row_task+1, column=0, columnspan=2, pady=3) 
        ttk.Button(task_buttons_frame, text="全パート選択", command=self.select_all_parts).pack(side=tk.LEFT, padx=5) 
        ttk.Button(task_buttons_frame, text="全パート選択解除", command=self.deselect_all_parts).pack(side=tk.LEFT, padx=5) 
        
        video_select_outer_frame = ttk.LabelFrame(main_frame, text="処理用動画選択 (パート2-6)", padding="5")
        video_select_outer_frame.pack(fill=tk.X, expand=False, pady=(5,3), anchor=tk.N)

        self.refresh_videos_button = ttk.Button(video_select_outer_frame, text="動画リスト更新", command=self.refresh_video_checkboxes)
        self.refresh_videos_button.pack(pady=(2,3)) 

        video_scroll_canvas_container = ttk.Frame(video_select_outer_frame)
        video_scroll_canvas_container.pack(fill=tk.X, expand=True, pady=(0,2))

        self.video_scroll_canvas = tk.Canvas(video_scroll_canvas_container, height=45) 
        self.video_scroll_x = ttk.Scrollbar(video_scroll_canvas_container, orient=tk.HORIZONTAL, command=self.video_scroll_canvas.xview)
        self.video_checkbox_inner_frame = ttk.Frame(self.video_scroll_canvas) 

        self.video_scroll_canvas.configure(xscrollcommand=self.video_scroll_x.set)
        self.video_scroll_canvas.create_window((0,0), window=self.video_checkbox_inner_frame, anchor="nw")

        self.video_scroll_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.video_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.video_checkbox_inner_frame.bind("<Configure>", lambda e: self.video_scroll_canvas.configure(scrollregion=self.video_scroll_canvas.bbox("all")))


        self.run_button = ttk.Button(main_frame, text="処理実行", command=self.start_processing_thread_gui) #
        self.run_button.pack(pady=(5,3)) #

        log_frame = ttk.LabelFrame(main_frame, text="ログ", padding="5") #
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(3,0)) #
        self.log_text_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, state='disabled') #
        self.log_text_widget.pack(fill=tk.BOTH, expand=True) #

    def _toggle_part3_options(self):
        if self.part3_enabled.get():
            self.part3_rb_individual.config(state=tk.NORMAL)
            self.part3_rb_merged.config(state=tk.NORMAL)
            self.part3_rb_concatenated.config(state=tk.NORMAL)
        else:
            self.part3_rb_individual.config(state=tk.DISABLED)
            self.part3_rb_merged.config(state=tk.DISABLED)
            self.part3_rb_concatenated.config(state=tk.DISABLED)

    def open_video_urls_txt(self): #
        root_dir = self.params["ROOT"].get() #
        if not root_dir: #
            messagebox.showerror("エラー", "ルートプロジェクトディレクトリが設定されていません。") #
            return #
        urls_file_path = os.path.join(root_dir, "video_urls.txt") #
        if not os.path.exists(urls_file_path): #
            create_q = messagebox.askyesno("ファイル未発見", f"{urls_file_path} が存在しません。作成しますか？") #
            if create_q: #
                try: #
                    with open(urls_file_path, 'w', encoding='utf-8') as f: #
                        f.write("# ここにビデオURLを1行に1つずつ追加してください\n") #
                        f.write("# フォーマット: <URL>,[開始時間],[終了時間] (開始/終了時間はオプションです)\n") #
                    self.gui_instance_logger.info(f"空のファイルを作成しました: {urls_file_path}")
                except Exception as e: #
                    messagebox.showerror("エラー", f"ファイルを作成できませんでした: {e}") #
                    return #
            else: #
                return #
        try: #
            if sys.platform == "win32": os.startfile(urls_file_path) #
            elif sys.platform == "darwin": subprocess.run(["open", urls_file_path], check=True) #
            else: subprocess.run(["xdg-open", urls_file_path], check=True) #
            self.gui_instance_logger.info(f"{urls_file_path} を編集用に開こうとしています。")
        except FileNotFoundError: messagebox.showerror("エラー", f"ファイルを開くプログラムが見つかりませんでした。\n手動で開いてください:\n{urls_file_path}") #
        except Exception as e: messagebox.showerror("エラー", f"ファイルを開けませんでした: {e}\nパス: {urls_file_path}") #


    def refresh_video_checkboxes(self): #
        for widget in self.video_checkbox_inner_frame.winfo_children(): #
            widget.destroy() 
        self.video_checkbox_vars.clear() 
        
        root_dir_val = self.params["ROOT"].get() 
        if not root_dir_val or not os.path.isdir(root_dir_val): 
            messagebox.showerror("エラー", "ルートプロジェクトディレクトリが設定されていないか無効です。") 
            return 
            
        video_download_base_dir = os.path.join(root_dir_val, "downloaded_videos") 
        if not os.path.isdir(video_download_base_dir): 
            ttk.Label(self.video_checkbox_inner_frame, text=f"ディレクトリが見つかりません: {video_download_base_dir}").pack(padx=5,pady=5, anchor=tk.W) #
            self.gui_instance_logger.info(f"動画ダウンロードディレクトリが見つかりません: {video_download_base_dir}。リストを更新できません。")
            self.video_checkbox_inner_frame.update_idletasks() #
            self.video_scroll_canvas.config(scrollregion=self.video_scroll_canvas.bbox("all")) #
            return 

        try: 
            video_files = [f for f in os.listdir(video_download_base_dir) if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))] 
            if not video_files: 
                ttk.Label(self.video_checkbox_inner_frame, text="downloaded_videosフォルダに動画が見つかりません。").pack(padx=5, pady=5, anchor=tk.W) #
                self.gui_instance_logger.info(f"{video_download_base_dir} に動画ファイルが見つかりません。")
            else:
                for filename in sorted(video_files): 
                    video_id = os.path.splitext(filename)[0] 
                    var = tk.BooleanVar(value=False) 
                    self.video_checkbox_vars[video_id] = var 
                    
                    cb = ttk.Checkbutton(self.video_checkbox_inner_frame, text=filename, variable=var) 
                    cb.pack(side=tk.LEFT, padx=3, pady=2) 
                self.gui_instance_logger.info(f"動画リストを更新しました。{len(video_files)}個の動画が見つかりました。")

            self.video_checkbox_inner_frame.update_idletasks() #
            self.video_scroll_canvas.config(scrollregion=self.video_scroll_canvas.bbox("all")) #

        except Exception as e: 
            self.gui_instance_logger.error(f"動画チェックボックスリストの更新中にエラーが発生しました: {e}")
            messagebox.showerror("エラー", f"動画ディレクトリを読み取れませんでした: {e}") 
        
    def browse_directory(self, string_var): 
        dirname = filedialog.askdirectory(initialdir=string_var.get() if string_var.get() else os.getcwd()) 
        if dirname: string_var.set(dirname) 

    def browse_file(self, string_var, save=False): 
        initial_dir_file = string_var.get() if string_var.get() else os.getcwd() 
        if save: 
            filename = filedialog.asksaveasfilename(initialfile=initial_dir_file, defaultextension=".log", 
                                                    filetypes=[("ログファイル", "*.log"), ("すべてのファイル", "*.*")]) 
        else: 
            filename = filedialog.askopenfilename(initialfile=initial_dir_file) 
        if filename: string_var.set(filename) 
            
    def select_all_parts(self): 
        for var in self.selected_parts_vars.values(): var.set(True) 
        self.part3_enabled.set(True) 
        self._toggle_part3_options() 

    def deselect_all_parts(self): 
        for var in self.selected_parts_vars.values(): var.set(False) 
        self.part3_enabled.set(False) 
        self._toggle_part3_options() 

    def select_all_weapons(self):
        for var in self.selected_weapons_vars.values(): var.set(True)

    def deselect_all_weapons(self):
        for var in self.selected_weapons_vars.values(): var.set(False)

    def start_processing_thread_gui(self): #
        self.run_button.config(state=tk.DISABLED) #
        self.log_text_widget.configure(state='normal') #
        self.log_text_widget.delete(1.0, tk.END) #
        self.log_text_widget.configure(state='disabled') #
        
        config = {key: var.get() for key, var in self.params.items()} #
        try: #
            for k_int in ["NUMBER_ROI_X1", "NUMBER_ROI_Y1", "NUMBER_ROI_X2", "NUMBER_ROI_Y2", "NUMBER_MID", #
                      "BOW_ROI_X1", "BOW_ROI_Y1", "BOW_ROI_X2", "BOW_ROI_Y2", #
                      "INFINITE_ROI_X1", "INFINITE_ROI_Y1", "INFINITE_ROI_X2", "INFINITE_ROI_Y2"]: #
                config[k_int] = int(self.params[k_int].get()) #
            for k_float in ["BOW_SIMILARITY_THRESHOLD", "SIMILARITY_THRESHOLD_INFINITE", #
                      "COARSE_SCAN_INTERVAL_SECONDS", "FINE_SCAN_INTERVAL_SECONDS",
                      "CLIP_DURATION", "MERGE_THRESHOLD_FACTOR"]: # CLIP_DURATION と MERGE_THRESHOLD_FACTOR を追加
                config[k_float] = float(self.params[k_float].get()) #
        except ValueError as e: #
            messagebox.showerror("パラメータエラー", f"無効な数値パラメータです: {e}") #
            self.run_button.config(state=tk.NORMAL); return #
        
        selected_parts_set = {part_num for part_num, var in self.selected_parts_vars.items() if var.get()} #
        
        if self.part3_enabled.get():
            selected_parts_set.add('3') 
            config["part3_mode"] = self.part3_clip_mode.get() 
        else:
            config["part3_mode"] = None 

        if not selected_parts_set: #
            messagebox.showwarning("パート未選択", "実行するパートを少なくとも1つ選択してください。") #
            self.run_button.config(state=tk.NORMAL); return #
        config["selected_parts"] = selected_parts_set #
        
        config["selected_video_ids_for_processing"] = [ #
            video_id for video_id, var in self.video_checkbox_vars.items() if var.get() #
        ]
        if any(p in selected_parts_set for p in ['2', '3', '4', '5', '6']): #
            if not config["selected_video_ids_for_processing"] and self.video_checkbox_vars: # チェックボックスが存在するが何も選択されていない場合
                messagebox.showwarning("動画未選択", "パート2-6用にリストから動画を選択するか、リストが更新されていることを確認してください。") #
                self.run_button.config(state=tk.NORMAL); return #

        config["selected_weapons_for_analysis"] = [
            name for name, var in self.selected_weapons_vars.items() if var.get()
        ]
        if '2' in selected_parts_set and not config["selected_weapons_for_analysis"]:
            messagebox.showwarning("武器未選択", "パート2が選択されていますが、分析用の武器が選択されていません。少なくとも1つの武器を選択してください。")
            self.run_button.config(state=tk.NORMAL); return
        if '3' in selected_parts_set and not config["selected_weapons_for_analysis"]: 
            messagebox.showwarning("クリップ用武器なし", "パート3が選択されていますが、(パート2で)分析用の武器が選択されていませんでした。パート3はそれらの武器に関するパート2の出力に依存します。")
            self.run_button.config(state=tk.NORMAL); return


        log_file_path_for_this_run = config["LOG_FILE_PATH"]

        self.gui_instance_logger.info(f"処理スレッドを開始します。今回の実行のログファイルターゲット: {log_file_path_for_this_run}")
        processing_thread = threading.Thread(target=self.run_processing_logic, args=(config, log_file_path_for_this_run), daemon=True) #
        processing_thread.start() #

    def run_processing_logic(self, config, current_log_file_path): #
        self._update_file_logging(current_log_file_path)
        
        logic_logger = logging.getLogger("VideoProcessingApp.Logic")

        logic_logger.info(f"処理ロジックを開始しました。使用ログファイル: {current_log_file_path}")
        # master.title() からバージョン情報を取得する方法は、title が変更される可能性があるため注意が必要です。
        # ここでは、元の形式を維持しつつ、日本語のログメッセージにします。
        app_title = self.master.title()
        app_version_info = app_title.split('v')[-1] if 'v' in app_title else ""
        logic_logger.info(f"GUI経由でアプリケーションを開始しています (v{app_version_info})...")
        
        ROOT = config["ROOT"] #
        URLPATH = os.path.join(ROOT, "video_urls.txt") #
        
        infinite_symbol_template_path = os.path.join(ROOT, "pic_template", "template_infinite_bow.png") #
        
        output_root_folder = os.path.join(ROOT, "clips_output") #
        os.makedirs(output_root_folder, exist_ok=True) #
        video_download_base_dir = os.path.join(ROOT, "downloaded_videos") #
        os.makedirs(video_download_base_dir, exist_ok=True) #
        
        selected_parts = config["selected_parts"] #
        selected_video_ids_to_process = config.get("selected_video_ids_for_processing", []) #
        selected_weapons_for_analysis = config.get("selected_weapons_for_analysis", []) #
        part3_clip_mode_selected = config.get("part3_mode") #
        
        logic_logger.info(f"ユーザー選択パート: {sorted(list(selected_parts))}") #
        if '3' in selected_parts:
            logic_logger.info(f"パート3クリッピングモード: {part3_clip_mode_selected}")
        if selected_weapons_for_analysis and ('2' in selected_parts or '3' in selected_parts) : 
             logic_logger.info(f"ユーザー選択 分析/クリッピング用武器: {selected_weapons_for_analysis}")
        if selected_video_ids_to_process and any(p in selected_parts for p in ['2','3','4','5','6']): 
            logic_logger.info(f"ユーザー選択 処理用動画ID (パート2-6): {selected_video_ids_to_process}") 
        
        if '1' in selected_parts: 
            downloaded_video_files_info = [] 
            if os.path.exists(URLPATH): 
                with open(URLPATH, 'r', encoding='utf-8') as f: 
                    for line_num, line in enumerate(f, 1): 
                        line = line.strip() 
                        if not line or line.startswith('#'): continue 
                        try: 
                            parts = line.split(',') 
                            video_url = parts[0].strip() 
                            parsed_video_id = urlparse(video_url).path.split('/')[-1] or f"unknown_video_{line_num}" 
                            start_time_str, end_time_str = (parts[1].strip(), parts[2].strip()) if len(parts) == 3 else (None, None) 
                            if start_time_str and end_time_str: 
                                logic_logger.info(f"ビデオクリップをダウンロード準備中: {video_url} {start_time_str} から {end_time_str} まで") 
                                downloaded_file_path = download_twitch(video_url, video_download_base_dir, start_time_str, end_time_str) 
                            elif len(parts) == 1: 
                                logic_logger.info(f"フルビデオをダウンロード準備中: {video_url}") 
                                downloaded_file_path = download_twitch(video_url, video_download_base_dir) 
                            else: 
                                logic_logger.warning(f"URLファイル行のフォーマットエラー: {line}、スキップします。"); continue 
                            if downloaded_file_path and os.path.exists(downloaded_file_path): 
                                actual_filename = os.path.basename(downloaded_file_path) 
                                downloaded_video_files_info.append({"parsed_id": parsed_video_id, "filename": actual_filename, "path": downloaded_file_path}) 
                                logic_logger.info(f"ビデオ {parsed_video_id} (ファイル: {actual_filename}) はダウンロード済みか存在します: {downloaded_file_path}") 
                            else: logic_logger.error(f"ビデオ {video_url} のダウンロードまたは検索に失敗しました。") 
                        except Exception as e: logic_logger.error(f"URLファイル行 '{line}' の処理中にエラーが発生しました: {e}") 
            else: logic_logger.error(f"エラー: video_urls.txt ファイルが {URLPATH} に見つかりません") 
            logic_logger.info("--- パート1 完了 ---") 
            self.master.after(0, self.refresh_video_checkboxes) 
        else: logic_logger.info("--- パート1 スキップ: 動画ダウンロード ---") 
        
        def get_filename_for_id(video_id, base_dir): 
            if not os.path.isdir(base_dir): return None 
            for item in os.listdir(base_dir): 
                if os.path.isfile(os.path.join(base_dir, item)) and item.startswith(video_id): 
                    name_part, ext_part = os.path.splitext(item) 
                    if name_part == video_id and ext_part.lower() in ['.mp4', '.mkv', '.avi', '.mov']: return item 
            return None 
            
        if '2' in selected_parts: 
            if not selected_video_ids_to_process: logic_logger.warning("パート2: 動画が選択されていません。選択に依存するためパート2をスキップします。") 
            elif not selected_weapons_for_analysis: logic_logger.warning("パート2: 分析用の武器が選択されていません。パート2をスキップします。")
            else: 
                if "bow" in selected_weapons_for_analysis and not os.path.exists(infinite_symbol_template_path):
                     logic_logger.error(f"エラー: 無限大記号テンプレート画像 {infinite_symbol_template_path} が見つかりません (ボウ分析に必要です)。");
                
                logic_logger.info(f"選択された {len(selected_video_ids_to_process)} 個の動画の分析を開始します、対象武器: {selected_weapons_for_analysis}...") 
                processed_videos_in_part2 = 0 
                for video_id in selected_video_ids_to_process: 
                    filename_in_dir = get_filename_for_id(video_id, video_download_base_dir) 
                    if not filename_in_dir: logic_logger.warning(f"パート2: ID '{video_id}' の動画ファイルが見つかりません。スキップします。"); continue 
                    video_path_for_analysis = os.path.join(video_download_base_dir, filename_in_dir) 
                    logic_logger.info(f"\n[パート2] 動画ファイル分析: {filename_in_dir} (ID: {video_id})") 
                    video_specific_output_dir_part2 = os.path.join(output_root_folder, video_id) 
                    os.makedirs(video_specific_output_dir_part2, exist_ok=True) 
                    
                    find_shooting_moments(
                        video_path=video_path_for_analysis,
                        root_pic_template_dir=os.path.join(ROOT, "pic_template"), 
                        selected_weapon_names=selected_weapons_for_analysis, 
                        video_output_dir=video_specific_output_dir_part2,
                        infinite_symbol_template_path=infinite_symbol_template_path, 
                        weapon_activation_similarity_threshold=config["BOW_SIMILARITY_THRESHOLD"],
                        similarity_threshold_infinite=config["SIMILARITY_THRESHOLD_INFINITE"],
                        number_roi_x1=config["NUMBER_ROI_X1"], number_roi_y1=config["NUMBER_ROI_Y1"],
                        number_roi_x2=config["NUMBER_ROI_X2"], number_roi_y2=config["NUMBER_ROI_Y2"],
                        mid_split_x=config["NUMBER_MID"],
                        weapon_roi_x1=config["BOW_ROI_X1"], weapon_roi_y1=config["BOW_ROI_Y1"], 
                        weapon_roi_x2=config["BOW_ROI_X2"], weapon_roi_y2=config["BOW_ROI_Y2"], 
                        infinite_roi_x1=config["INFINITE_ROI_X1"], infinite_roi_y1=config["INFINITE_ROI_Y1"], 
                        infinite_roi_x2=config["INFINITE_ROI_X2"], infinite_roi_y2=config["INFINITE_ROI_Y2"], 
                        coarse_interval_seconds=config["COARSE_SCAN_INTERVAL_SECONDS"],
                        fine_interval_seconds=config["FINE_SCAN_INTERVAL_SECONDS"],
                        start_time=config["START_TIME"]
                    )
                    processed_videos_in_part2 += 1 
                if processed_videos_in_part2 == 0 and selected_video_ids_to_process : logic_logger.info(f"パート2: 選択された動画は正常に分析されませんでした。") 
            logic_logger.info("--- パート2 (分析) 完了 ---") 
        else: logic_logger.info("--- パート2 スキップ: 動画分析 ---") 
        
        if '3' in selected_parts: 
            if not selected_video_ids_to_process:
                logic_logger.warning("パート3: 動画が選択されていません。スキップします。")
            elif not selected_weapons_for_analysis:
                logic_logger.warning("パート3: (パート2で)分析用の武器が選択されていなかったため、"
                                     "クリップ元の武器固有TXTファイルがありません。スキップします。")
            elif not part3_clip_mode_selected: 
                logic_logger.error("パート3: クリッピングモードが指定されていません。スキップします。")
            else:
                logic_logger.info(f"選択された {len(selected_video_ids_to_process)} 個の動画について、"
                                 f"分析済みの武器 {selected_weapons_for_analysis} のクリップを開始します (パート3 - モード: {part3_clip_mode_selected})...")

                for video_id in selected_video_ids_to_process:
                    if not os.path.isdir(video_download_base_dir):
                        logic_logger.error(f"パート3用の動画ディレクトリが見つかりません: {video_download_base_dir}。パート3を中断します。")
                        break 

                    filename_in_dir_p3 = get_filename_for_id(video_id, video_download_base_dir)
                    if not filename_in_dir_p3:
                        logic_logger.warning(f"パート3: ID '{video_id}' の動画ファイルが "
                                             f"{video_download_base_dir} に見つかりません。パート3のこの動画をスキップします。")
                        continue

                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p3)
                    video_specific_output_dir_p3_base = os.path.join(output_root_folder, video_id) 

                    if not os.path.exists(video_specific_output_dir_p3_base):
                        logic_logger.warning(f"パート3: 動画ID '{video_id}' の基本出力ディレクトリ '{video_specific_output_dir_p3_base}' "
                                             f"が見つかりません (パート2から期待される)。パート3のこの動画をスキップします。")
                        continue

                    weapon_time_sources_for_this_video = []
                    for weapon_name_to_clip in selected_weapons_for_analysis:
                        weapon_actual_file_key_for_txt = weapon_name_to_clip 
                        if weapon_name_to_clip in WEAPON_METADATA: 
                            suffix = WEAPON_METADATA[weapon_name_to_clip].get('suffix')
                            if suffix:
                                weapon_actual_file_key_for_txt = suffix 
                            else:
                                logic_logger.warning(f"パート3: 武器 '{weapon_name_to_clip}' の接尾辞がWEAPON_METADATAに見つかりません。TXTファイル名に内部キーを使用します。")
                        else:
                            logic_logger.warning(f"パート3: 武器 '{weapon_name_to_clip}' がWEAPON_METADATAに見つかりません。TXTファイル名に内部キーを使用します。")
                        
                        weapon_times_txt_filename = f"shooting_{weapon_actual_file_key_for_txt}.txt" 
                        weapon_shooting_times_txt_path = os.path.join(video_specific_output_dir_p3_base, weapon_times_txt_filename)

                        if os.path.exists(weapon_shooting_times_txt_path) and os.path.getsize(weapon_shooting_times_txt_path) > 0:
                            weapon_time_sources_for_this_video.append({
                                'file_path': weapon_shooting_times_txt_path,
                                'weapon_name': weapon_name_to_clip 
                            })
                        else:
                            logic_logger.info(f"パート3: 動画 {video_id} の時間ファイル {weapon_times_txt_filename} "
                                             f"(武器: {weapon_name_to_clip}、ファイルキー '{weapon_actual_file_key_for_txt}' を使用) が存在しないか空です。 ") 
                    
                    if weapon_time_sources_for_this_video:
                        logic_logger.info(f"パート3 (モード: {part3_clip_mode_selected}): 動画ID '{video_id}' のため、 "
                                        f"{len(weapon_time_sources_for_this_video)} 個の武器時間ファイルからタイムスタンプを収集してクリップを準備します。")

                        if part3_clip_mode_selected == "individual" or part3_clip_mode_selected == "merged":
                            clips_subfolder_name = f"clips_{part3_clip_mode_selected}" 
                            final_clips_output_path = os.path.join(video_specific_output_dir_p3_base, clips_subfolder_name)
                            os.makedirs(final_clips_output_path, exist_ok=True)

                        if part3_clip_mode_selected == "individual":
                            generate_clips_from_multiple_weapon_times(
                                input_video_path=video_path_for_clipping,
                                weapon_time_sources=weapon_time_sources_for_this_video,
                                output_folder=final_clips_output_path, 
                                clip_duration=config["CLIP_DURATION"] 
                            )
                        elif part3_clip_mode_selected == "merged":
                            generate_clips_from_multiple_weapon_times_merge(
                                input_video_path=video_path_for_clipping,
                                weapon_time_sources=weapon_time_sources_for_this_video,
                                output_folder=final_clips_output_path, 
                                clip_duration=config["CLIP_DURATION"], 
                                merge_threshold_factor=config["MERGE_THRESHOLD_FACTOR"] 
                            )
                        elif part3_clip_mode_selected == "concatenated": 
                            logic_logger.info(f"パート3 (モード: 連結): 動画ID '{video_id}' 用に単一の結合ビデオを生成します。")
                            generate_concatenated_video_from_timestamps(
                                input_video_path=video_path_for_clipping,
                                weapon_time_sources=weapon_time_sources_for_this_video,
                                output_folder=video_specific_output_dir_p3_base, 
                                clip_duration=config["CLIP_DURATION"], 
                                merge_threshold_factor=config["MERGE_THRESHOLD_FACTOR"] 
                            )
                    else:
                        logic_logger.info(f"パート3: 動画ID '{video_id}' のクリップ用の有効な武器時間ファイルが見つかりませんでした (モード: {part3_clip_mode_selected})。")
                logic_logger.info(f"--- パート3 (クリップ - モード: {part3_clip_mode_selected}) 完了 ---")
        else:
            logic_logger.info("--- パート3 スキップ: 武器クリップのマージソート ---")
        
        if '4' in selected_parts: 
            if not selected_video_ids_to_process: logic_logger.warning("パート4 (ボウ無限クリップ): 動画が選択されていません。スキップします。") 
            else: 
                logic_logger.info(f"選択された {len(selected_video_ids_to_process)} 個の動画のボウ無限クリップを開始します (パート4)...") 
                processed_clips_in_part4 = 0 
                for video_id in selected_video_ids_to_process: 
                    if not os.path.isdir(video_download_base_dir): logic_logger.error(f"パート4用の動画ディレクトリが見つかりません。"); break 
                    filename_in_dir_p4 = get_filename_for_id(video_id, video_download_base_dir) 
                    if not filename_in_dir_p4: logic_logger.warning(f"パート4: '{video_id}' のファイルが見つかりません。スキップします。"); continue 
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p4) 
                    video_specific_output_dir_p4 = os.path.join(output_root_folder, video_id) 
                    infinite_txt_path_for_clipping = os.path.join(video_specific_output_dir_p4, "infinite_2.txt") 
                    if not os.path.exists(video_specific_output_dir_p4): 
                        logic_logger.warning(f"パート4: 動画ID '{video_id}' の出力ディレクトリ '{video_specific_output_dir_p4}' が見つかりません。スキップします。")
                        continue
                    if not (os.path.exists(infinite_txt_path_for_clipping) and os.path.getsize(infinite_txt_path_for_clipping) > 0): 
                        logic_logger.warning(f"パート4: {video_id} (ボウ) の infinite_2.txt が '{infinite_txt_path_for_clipping}' に見つからないか空です。スキップします。")
                        continue 
                    # 注意: clip_video_ffmpeg_with_duration は現在configからclip_durationを取得しません。txtファイルからdurationを読み取ります。
                    clip_video_ffmpeg_with_duration(video_path_for_clipping, infinite_txt_path_for_clipping, video_specific_output_dir_p4) 
                    processed_clips_in_part4 +=1 
                if processed_clips_in_part4 == 0 and selected_video_ids_to_process: logic_logger.info(f"パート4: 選択された動画はクリップされませんでした (ボウ無限)。") 
            logic_logger.info("--- パート4 (ボウ無限クリップ) 完了 ---") 
        else: logic_logger.info("--- パート4 スキップ: ボウ無限クリップ ---") 
        
        if '5' in selected_parts: 
            if not selected_video_ids_to_process: logic_logger.warning("パート5 (ボウTXTマージ): TXTマージ用の動画がありません。スキップします。") 
            else: 
                logic_logger.info(f"選択された {len(selected_video_ids_to_process)} 個の動画IDのボウTXTマージを開始します (パート5)...") 
                processed_merges_in_part5 = 0 
                for video_id in selected_video_ids_to_process: 
                    video_specific_output_dir_p5 = os.path.join(output_root_folder, video_id) 
                    if not os.path.isdir(video_specific_output_dir_p5): logic_logger.warning(f"パート5: {video_id} の出力ディレクトリ ('{video_specific_output_dir_p5}') が見つかりません。スキップします。"); continue 
                    logic_logger.info(f"\n[パート5] 動画ID {video_id} のために2つのボウtxtをマージします") 
                    shooting_bow_file = os.path.join(video_specific_output_dir_p5, "shooting_bow.txt") 
                    infinite_file_to_merge = os.path.join(video_specific_output_dir_p5, "infinite_3.txt") 
                    
                    if not os.path.exists(shooting_bow_file): 
                        logic_logger.warning(f"パート5: {video_id} の shooting_bow.txt が '{shooting_bow_file}' に見つかりません。このIDのマージをスキップします。")
                        continue 
                    process_and_merge_times(shooting_bow_file, infinite_file_to_merge) 
                    processed_merges_in_part5 +=1 
                if processed_merges_in_part5 == 0 and selected_video_ids_to_process: logic_logger.info(f"パート5: 選択された動画のボウTXTファイルのマージが正常に開始されませんでした（またはソースファイルがありません）。") 
            logic_logger.info("--- パート5 (ボウTXTマージ) 完了 ---") 
        else: logic_logger.info("--- パート5 スキップ: ボウTXTマージ ---") 
        
        if '6' in selected_parts: 
            if not selected_video_ids_to_process: logic_logger.warning("パート6 (ボウマージクリップ): 動画が選択されていません。スキップします。") 
            else: 
                logic_logger.info(f"選択された {len(selected_video_ids_to_process)} 個の動画のボウSUMクリップを開始します (パート6)...") 
                processed_clips_in_part6 = 0 
                for video_id in selected_video_ids_to_process: 
                    if not os.path.isdir(video_download_base_dir): logic_logger.error(f"パート6用の動画ディレクトリが見つかりません。"); break 
                    filename_in_dir_p6 = get_filename_for_id(video_id, video_download_base_dir) 
                    if not filename_in_dir_p6: logic_logger.warning(f"パート6: '{video_id}' のファイルが見つかりません。スキップします。"); continue 
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p6) 
                    video_specific_output_dir_p6 = os.path.join(output_root_folder, video_id) 
                    sum_txt_path_for_clipping = os.path.join(video_specific_output_dir_p6, "shooting_bow_sum.txt") 
                    if not os.path.exists(video_specific_output_dir_p6): 
                        logic_logger.warning(f"パート6: 動画ID '{video_id}' の出力ディレクトリ '{video_specific_output_dir_p6}' が見つかりません。スキップします。")
                        continue
                    if not (os.path.exists(sum_txt_path_for_clipping) and os.path.getsize(sum_txt_path_for_clipping) > 0): 
                        logic_logger.warning(f"パート6: {video_id} の shooting_bow_sum.txt が '{sum_txt_path_for_clipping}' に見つからないか空です。スキップします。")
                        continue 
                    clip_video_ffmpeg(video_path_for_clipping, sum_txt_path_for_clipping, video_specific_output_dir_p6, clip_duration=config["CLIP_DURATION"], weapon_name="bow_sum") 
                    processed_clips_in_part6 +=1 
                if processed_clips_in_part6 == 0 and selected_video_ids_to_process: logic_logger.info(f"パート6: 選択された動画はクリップされませんでした (ボウマージ)。") 
            logic_logger.info("--- パート6 (ボウSUMクリップ) 完了 ---") 
        else: logic_logger.info("--- パート6 スキップ: ボウSUMクリップ ---") 
        
        logic_logger.info(f"\nスクリプトの実行が終了しました。選択された実行パート: {sorted(list(selected_parts))}") 
        self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL)) 

if __name__ == "__main__": 
    # モック関数は開発用であり、ユーザーインターフェースに直接影響しないため、
    # ログメッセージの翻訳は必須ではありませんが、一貫性のために行ってもよいでしょう。
    # ここでは簡単のため、モックのログメッセージは英語のままにします。
    if 'analysis_functions' not in sys.modules:
        class MockAnalysis:
            def find_shooting_moments(*args, **kwargs): logging.info(f"Mock find_shooting_moments called with {args}, {kwargs}")
        try:
            # WEAPON_METADATA はこのスクリプトの先頭で定義されているため、
            # analysis_functions からのインポートは不要です。
            # from analysis_functions import WEAPON_METADATA
            pass # WEAPON_METADATA is defined globally in this script
        except ImportError:
            logging.warning("analysis_functions.WEAPON_METADATA not found, using fallback for GUI (though defined globally).")

    if 'general_function' not in sys.modules:
        class MockGeneral:
            def download_twitch(url, out_dir, start=None, end=None): 
                logging.info(f"Mock download_twitch: {url} to {out_dir} ({start}-{end})")
                parsed_id = urlparse(url).path.split('/')[-1] or f"unknown_video_download"
                dummy_path = os.path.join(out_dir, f"{parsed_id}.mp4")
                os.makedirs(out_dir, exist_ok=True)
                with open(dummy_path, 'w') as f: f.write("dummy video content")
                return dummy_path
            def hms_to_seconds(hms_str): return sum(x * float(t) for x, t in zip([3600, 60, 1], hms_str.split('.')[0].split(':'))) + float("0." + hms_str.split('.')[1]) if '.' in hms_str else sum(x * float(t) for x, t in zip([3600, 60, 1], hms_str.split(':')))
            def seconds_to_hms(sec): 
                if sec < 0: sec = 0
                hrs = int(sec // 3600)
                mins = int((sec % 3600) // 60)
                secs = int(sec % 60)
                ms = int((sec - int(sec)) * 1000)
                return f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:03d}"
        sys.modules['general_function'] = MockGeneral()
        download_twitch = MockGeneral.download_twitch

    if 'clip_functions' not in sys.modules:
        class MockClip:
            def clip_video_ffmpeg(*args, **kwargs): logging.info(f"Mock clip_video_ffmpeg called with {args}, {kwargs}")
            def generate_clips_from_multiple_weapon_times(*args, **kwargs): logging.info(f"Mock generate_clips_from_multiple_weapon_times with {args}, {kwargs}")
            def clip_video_ffmpeg_merged(*args, **kwargs): logging.info(f"Mock clip_video_ffmpeg_merged with {args}, {kwargs}")
            def clip_video_ffmpeg_with_duration(*args, **kwargs): logging.info(f"Mock clip_video_ffmpeg_with_duration with {args}, {kwargs}")
            def process_and_merge_times(*args, **kwargs): logging.info(f"Mock process_and_merge_times with {args}, {kwargs}")
            def generate_clips_from_multiple_weapon_times_merge(*args, **kwargs): logging.info(f"Mock generate_clips_from_multiple_weapon_times_merge with {args}, {kwargs}")
            def generate_concatenated_video_from_timestamps(*args, **kwargs): logging.info(f"Mock generate_concatenated_video_from_timestamps with {args}, {kwargs}")

        sys.modules['clip_functions'] = MockClip()
    
    root = tk.Tk() 
    app = VideoProcessingGUI(root) 
    root.mainloop()