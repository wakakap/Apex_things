import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import logging
import threading
from urllib.parse import urlparse
import subprocess
import sys # For platform-specific open

# Assuming these files are in the same directory
from analysis_functions import find_shooting_moments, WEAPON_METADATA # Import WEAPON_METADATA
from general_function import download_twitch, hms_to_seconds, seconds_to_hms #
# Import the new merge function as well
from clip_functions import clip_video_ffmpeg, generate_clips_from_multiple_weapon_times, clip_video_ffmpeg_merged, clip_video_ffmpeg_with_duration, process_and_merge_times, generate_clips_from_multiple_weapon_times_merge #

# --- Logger for the GUI and adapted main logic ---

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
        master.title("ApexTool(beta)") #
        master.geometry("900x980") # Increased height for weapon selection & new Part 3 options

        self.style = ttk.Style() #
        self.style.theme_use('clam') #

        self.default_root = "E:\\mande\\0_PLAN" #
        self.default_log_file = os.path.join(self.default_root, "Apex_tool(beta).log") #
        
        self.file_handler = None # To keep track of the current file handler

        self.params = {
            "NUMBER_ROI_X1": tk.StringVar(value="1723"), "NUMBER_ROI_Y1": tk.StringVar(value="958"), #
            "NUMBER_ROI_X2": tk.StringVar(value="1787"), "NUMBER_ROI_Y2": tk.StringVar(value="1002"), #
            "NUMBER_MID": tk.StringVar(value="1754"), #
            # BOW_ROI will be used as the general WEAPON_ACTIVATION_ROI
            "BOW_ROI_X1": tk.StringVar(value="1554"), "BOW_ROI_Y1": tk.StringVar(value="958"), #
            "BOW_ROI_X2": tk.StringVar(value="1702"), "BOW_ROI_Y2": tk.StringVar(value="998"), #
            "INFINITE_ROI_X1": tk.StringVar(value="1723"), "INFINITE_ROI_Y1": tk.StringVar(value="964"), # Specific to Bow
            "INFINITE_ROI_X2": tk.StringVar(value="1782"), "INFINITE_ROI_Y2": tk.StringVar(value="993"), # Specific to Bow
            # BOW_SIMILARITY_THRESHOLD will be used as WEAPON_ACTIVATION_SIMILARITY_THRESHOLD
            "BOW_SIMILARITY_THRESHOLD": tk.StringVar(value="0.75"), # General for weapon activation
            "SIMILARITY_THRESHOLD_INFINITE": tk.StringVar(value="0.74"), # Specific to Bow
            "COARSE_SCAN_INTERVAL_SECONDS": tk.StringVar(value="3.0"), #
            "FINE_SCAN_INTERVAL_SECONDS": tk.StringVar(value="0.1"), #
            "START_TIME": tk.StringVar(value="00:00:00.000"), #
            "ROOT": tk.StringVar(value=self.default_root), #
            "LOG_FILE_PATH": tk.StringVar(value=self.default_log_file) #
        }

        self.selected_parts_vars = { #
            '1': tk.BooleanVar(value=False), '2': tk.BooleanVar(value=False), #
            # '3' is handled by part3_enabled now
            '4': tk.BooleanVar(value=False), '5': tk.BooleanVar(value=False), #
            '6': tk.BooleanVar(value=False) #
        }
        # New variables for Part 3 clipping choice
        self.part3_enabled = tk.BooleanVar(value=False) # Checkbox to enable Part 3
        self.part3_clip_mode = tk.StringVar(value="individual") # Radio button choice: "individual" or "merged"
        
        self.video_checkbox_vars = {} #
        self.selected_weapons_vars = { # For selecting weapons for analysis (Part 2)
            weapon_name: tk.BooleanVar(value=False) for weapon_name in WEAPON_METADATA.keys()
        }
        # Default some common weapons to True if desired, e.g.:
        # if "bow" in self.selected_weapons_vars:
        #     self.selected_weapons_vars["bow"].set(True)
        # if "r3030" in self.selected_weapons_vars: # Ensure r3030 exists in WEAPON_METADATA if used here
        #     self.selected_weapons_vars["r3030"].set(True)


        self.create_widgets() # This creates self.log_text_widget
        self._setup_gui_text_handler_and_initial_root_config()
        # self.setup_gui_logging() # This line is replaced by the call above

    def _setup_gui_text_handler_and_initial_root_config(self):
        """Sets up the handler for the GUI's ScrolledText and initial root logger config."""
        self.text_widget_handler = TextHandler(self.log_text_widget)
        gui_formatter = logging.Formatter("%(asctime)s [%(levelname)s] (%(name)s): %(message)s", "%H:%M:%S") #
        self.text_widget_handler.setFormatter(gui_formatter) #
        self.text_widget_handler.setLevel(logging.INFO) # GUI shows INFO and above

        root_logger = logging.getLogger()
        root_logger.addHandler(self.text_widget_handler)
        root_logger.setLevel(logging.INFO) # Initial root level, can be overridden to DEBUG by file logger

        self.gui_instance_logger = logging.getLogger("VideoProcessingApp.GUI")
        self.gui_instance_logger.info("GUI initialized. Logging to window is active (INFO level).")

    def _update_file_logging(self, new_log_file_path):
        """Configures or updates file logging to the new_log_file_path."""
        root_logger = logging.getLogger()

        if self.file_handler:
            root_logger.removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None
            self.gui_instance_logger.info("Previous file log handler closed.")

        log_dir = os.path.dirname(new_log_file_path)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                self.gui_instance_logger.info(f"Created log directory: {log_dir}")
            except Exception as e:
                self.gui_instance_logger.error(f"Failed to create log directory {log_dir}: {e}")
        
        try:
            self.file_handler = logging.FileHandler(new_log_file_path, mode='a', encoding='utf-8')
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s](%(module)s.%(funcName)s): %(message)s", #
                "%Y-%m-%d %H:%M:%S" #
            )
            self.file_handler.setFormatter(file_formatter)
            self.file_handler.setLevel(logging.DEBUG) # File logs at DEBUG level

            root_logger.addHandler(self.file_handler)
            root_logger.setLevel(logging.DEBUG) # Ensure root logger processes DEBUG messages for the file handler

            logging.info(f"File logging configured to: {new_log_file_path}. Root logger level is now DEBUG.")
            logging.debug("This is a test debug message to the file after _update_file_logging.")
        except Exception as e:
            self.gui_instance_logger.error(f"Failed to configure file logging to {new_log_file_path}: {e}")


    def create_widgets(self):
        main_frame = ttk.Frame(self.master, padding="10") #
        main_frame.pack(fill=tk.BOTH, expand=True) #

        paths_frame = ttk.LabelFrame(main_frame, text="Configuration Paths", padding="10") #
        paths_frame.pack(fill=tk.X, expand=False, pady=5, anchor=tk.N) #
        ttk.Label(paths_frame, text="Root Project Directory:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W) #
        self.root_entry = ttk.Entry(paths_frame, textvariable=self.params["ROOT"], width=50) #
        self.root_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW) #
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_directory(self.params["ROOT"])).grid(row=0, column=2, padx=5, pady=5) #
        ttk.Label(paths_frame, text="Log File Path:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W) #
        self.log_file_entry = ttk.Entry(paths_frame, textvariable=self.params["LOG_FILE_PATH"], width=50) #
        self.log_file_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW) #
        ttk.Button(paths_frame, text="Browse Log", command=lambda: self.browse_file(self.params["LOG_FILE_PATH"], save=True)).grid(row=1, column=2, padx=5, pady=5) #
        self.open_urls_button = ttk.Button(paths_frame, text="Edit video_urls.txt", command=self.open_video_urls_txt) #
        self.open_urls_button.grid(row=0, column=3, rowspan=2, padx=10, pady=5, sticky="nsew") #
        paths_frame.columnconfigure(1, weight=1) #

        params_frame = ttk.LabelFrame(main_frame, text="Analysis Parameters", padding="10") #
        params_frame.pack(fill=tk.X, expand=False, pady=5, anchor=tk.N) #
        param_layout = [ #
            [("Number ROI (X1 Y1 X2 Y2 M):", ["NUMBER_ROI_X1", "NUMBER_ROI_Y1", "NUMBER_ROI_X2", "NUMBER_ROI_Y2", "NUMBER_MID"])], #
            [("Weapon Activation ROI (X1 Y1 X2 Y2):", ["BOW_ROI_X1", "BOW_ROI_Y1", "BOW_ROI_X2", "BOW_ROI_Y2"]), # Renamed label for clarity
             ("Bow Infinite ROI (X1 Y1 X2 Y2):", ["INFINITE_ROI_X1", "INFINITE_ROI_Y1", "INFINITE_ROI_X2", "INFINITE_ROI_Y2"])], #
            [("Weapon Act. Thresh:", ["BOW_SIMILARITY_THRESHOLD"]), ("Bow Infinite Thresh:", ["SIMILARITY_THRESHOLD_INFINITE"]), # Renamed label
             ("Coarse Scan (s):", ["COARSE_SCAN_INTERVAL_SECONDS"]), ("Fine Scan (s):", ["FINE_SCAN_INTERVAL_SECONDS"])], #
            [("Analysis Start Time (HH:MM:SS.mmm):", ["START_TIME"], 3)] #
        ]
        current_row_param = 0 #
        for row_def in param_layout: #
            current_col_param = 0 #
            for item_def in row_def: #
                label_text, param_keys = item_def[0], item_def[1] #
                colspan_val = item_def[2] if len(item_def) > 2 else 1 #
                ttk.Label(params_frame, text=label_text).grid(row=current_row_param, column=current_col_param, padx=5, pady=2, sticky=tk.W) #
                current_col_param += 1 #
                entry_frame = ttk.Frame(params_frame) #
                entry_frame.grid(row=current_row_param, column=current_col_param, columnspan=colspan_val * (len(param_keys) if len(param_keys)>1 else 1) , padx=2, pady=2, sticky=tk.W) #
                for p_idx, p_key in enumerate(param_keys): #
                    width = 15 if len(param_keys) == 1 and colspan_val > 1 else 6 #
                    ttk.Entry(entry_frame, textvariable=self.params[p_key], width=width).pack(side=tk.LEFT, padx=1) #
                current_col_param += (colspan_val * (len(param_keys) if len(param_keys) > 1 else 1)) -1 #
            current_row_param += 1 #

        # --- Weapon Selection Frame ---
        weapon_select_frame = ttk.LabelFrame(main_frame, text="Select Weapons for Analysis (Part 2 & 3)", padding="10")
        weapon_select_frame.pack(fill=tk.X, expand=False, pady=5, anchor=tk.N)
        
        # Dynamically create checkboxes for weapons
        weapon_row, weapon_col = 0, 0
        max_weapon_cols = 4 # Adjust as needed
        for weapon_internal_name, metadata in WEAPON_METADATA.items():
            display_name = metadata.get("display_name", weapon_internal_name.replace("_", " ").title())
            ttk.Checkbutton(weapon_select_frame, text=display_name, variable=self.selected_weapons_vars[weapon_internal_name]).grid(row=weapon_row, column=weapon_col, sticky=tk.W, padx=5, pady=2)
            weapon_col += 1
            if weapon_col >= max_weapon_cols:
                weapon_col = 0
                weapon_row += 1
        
        weapon_buttons_frame = ttk.Frame(weapon_select_frame)
        weapon_buttons_frame.grid(row=weapon_row + 1, column=0, columnspan=max_weapon_cols, pady=5)
        ttk.Button(weapon_buttons_frame, text="Select All Weapons", command=self.select_all_weapons).pack(side=tk.LEFT, padx=5)
        ttk.Button(weapon_buttons_frame, text="Deselect All Weapons", command=self.deselect_all_weapons).pack(side=tk.LEFT, padx=5)


        tasks_frame = ttk.LabelFrame(main_frame, text="Select Parts to Run", padding="10") #
        tasks_frame.pack(fill=tk.X, expand=False, pady=5, anchor=tk.N) #
        
        # Part 1 and 2
        ttk.Checkbutton(tasks_frame, text="Part 1: Download videos", variable=self.selected_parts_vars['1']).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2) #
        ttk.Checkbutton(tasks_frame, text="Part 2: Analyze videos (for selected weapons)", variable=self.selected_parts_vars['2']).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2) #

        # Part 3 - with options
        part3_outer_frame = ttk.Frame(tasks_frame) # Use a frame to group Part 3 elements
        part3_outer_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=0, pady=2)

        self.part3_enable_cb = ttk.Checkbutton(part3_outer_frame, text="Part 3: Clip Weapons ", variable=self.part3_enabled, command=self._toggle_part3_options)
        self.part3_enable_cb.pack(side=tk.LEFT, padx=(5,0)) # Align checkbox to the left
        
        self.part3_rb_individual = ttk.Radiobutton(part3_outer_frame, text="Individual", variable=self.part3_clip_mode, value="individual", state=tk.DISABLED)
        self.part3_rb_individual.pack(side=tk.LEFT, padx=(5,0))
        self.part3_rb_merged = ttk.Radiobutton(part3_outer_frame, text="Merge Close", variable=self.part3_clip_mode, value="merged", state=tk.DISABLED)
        self.part3_rb_merged.pack(side=tk.LEFT, padx=(5,0))
        
        # Part 4, 5, 6 descriptions
        part_descriptions_rest = { #
            '4': "Part 4: Clip Bow Infinite (from infinite_2.txt)", # Clarified Bow-specific, and source file
            '5': "Part 5: Merge Bow TXTs (shooting_bow.txt + infinite_3.txt)", # Clarified Bow-specific
            '6': "Part 6: Clip Bow Merged (from shooting_bow_sum.txt)" # Clarified Bow-specific
        }
        
        col_task, row_task = 0, 2 # Start remaining parts from row 2
        for part_num, desc in part_descriptions_rest.items(): #
            ttk.Checkbutton(tasks_frame, text=desc, variable=self.selected_parts_vars[part_num]).grid(row=row_task, column=col_task, sticky=tk.W, padx=5, pady=2) #
            col_task += 1 #
            if col_task >= 2: col_task = 0; row_task += 1 #
        
        task_buttons_frame = ttk.Frame(tasks_frame) #
        task_buttons_frame.grid(row=row_task+1, column=0, columnspan=2, pady=5) # Adjust row if necessary
        ttk.Button(task_buttons_frame, text="Select All Parts", command=self.select_all_parts).pack(side=tk.LEFT, padx=5) #
        ttk.Button(task_buttons_frame, text="Deselect All Parts", command=self.deselect_all_parts).pack(side=tk.LEFT, padx=5) #
        
        video_select_outer_frame = ttk.LabelFrame(main_frame, text="Select Videos for Processing (Parts 2-6)", padding="10") #
        video_select_outer_frame.pack(fill=tk.X, expand=False, pady=(10,5), anchor=tk.N) #

        self.refresh_videos_button = ttk.Button(video_select_outer_frame, text="Refresh Video List", command=self.refresh_video_checkboxes) #
        self.refresh_videos_button.pack(pady=(0,5)) #

        self.checkbox_area_interior = ttk.Frame(video_select_outer_frame) #
        self.checkbox_area_interior.pack(fill=tk.X, expand=False, pady=5) #

        self.run_button = ttk.Button(main_frame, text="Run Processing", command=self.start_processing_thread_gui) #
        self.run_button.pack(pady=(10,5)) #

        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding="10") #
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5,0)) #
        self.log_text_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state='disabled') #
        self.log_text_widget.pack(fill=tk.BOTH, expand=True) #

    def _toggle_part3_options(self):
        """Enable/disable Part 3 radio buttons based on Part 3 checkbox state."""
        if self.part3_enabled.get():
            self.part3_rb_individual.config(state=tk.NORMAL)
            self.part3_rb_merged.config(state=tk.NORMAL)
        else:
            self.part3_rb_individual.config(state=tk.DISABLED)
            self.part3_rb_merged.config(state=tk.DISABLED)

    def open_video_urls_txt(self): #
        root_dir = self.params["ROOT"].get() #
        if not root_dir: #
            messagebox.showerror("Error", "Root Project Directory is not set.") #
            return #
        urls_file_path = os.path.join(root_dir, "video_urls.txt") #
        if not os.path.exists(urls_file_path): #
            create_q = messagebox.askyesno("File Not Found", f"{urls_file_path} does not exist. Create it?") #
            if create_q: #
                try: #
                    with open(urls_file_path, 'w', encoding='utf-8') as f: #
                        f.write("# Add video URLs here, one per line\n") #
                        f.write("# Format: <URL>,[start_time],[end_time] (start/end times are optional)\n") #
                    self.gui_instance_logger.info(f"Created empty file: {urls_file_path}")
                except Exception as e: #
                    messagebox.showerror("Error", f"Could not create file: {e}") #
                    return #
            else: #
                return #
        try: #
            if sys.platform == "win32": os.startfile(urls_file_path) #
            elif sys.platform == "darwin": subprocess.run(["open", urls_file_path], check=True) #
            else: subprocess.run(["xdg-open", urls_file_path], check=True) #
            self.gui_instance_logger.info(f"Attempting to open {urls_file_path} for editing.")
        except FileNotFoundError: messagebox.showerror("Error", f"Could not find a program to open the file.\nPlease open it manually:\n{urls_file_path}") #
        except Exception as e: messagebox.showerror("Error", f"Could not open file: {e}\nPath: {urls_file_path}") #


    def refresh_video_checkboxes(self): #
        for widget in self.checkbox_area_interior.winfo_children(): #
            widget.destroy() #
        self.video_checkbox_vars.clear() #
        
        root_dir_val = self.params["ROOT"].get() #
        if not root_dir_val or not os.path.isdir(root_dir_val): #
            messagebox.showerror("Error", "Root Project Directory is not set or is invalid.") #
            return #
            
        video_download_base_dir = os.path.join(root_dir_val, "downloaded_videos") #
        if not os.path.isdir(video_download_base_dir): #
            ttk.Label(self.checkbox_area_interior, text=f"Directory not found:\n{video_download_base_dir}").pack(padx=5,pady=5, anchor=tk.W) #
            self.gui_instance_logger.info(f"Video download directory not found: {video_download_base_dir}. Cannot refresh list.")
            return #

        try: #
            video_files = [f for f in os.listdir(video_download_base_dir) if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))] #
            if not video_files: #
                ttk.Label(self.checkbox_area_interior, text="No videos found in downloaded_videos folder.").pack(padx=5, pady=5, anchor=tk.W) #
                self.gui_instance_logger.info(f"No video files found in {video_download_base_dir}.")
                return #

            max_cols = 3 #
            
            for c_idx in range(max_cols): #
                self.checkbox_area_interior.columnconfigure(c_idx, weight=1) #

            row, col = 0, 0 #
            for filename in sorted(video_files): #
                video_id = os.path.splitext(filename)[0] #
                var = tk.BooleanVar(value=False) #
                self.video_checkbox_vars[video_id] = var #
                
                cb = ttk.Checkbutton(self.checkbox_area_interior, text=filename, variable=var) #
                cb.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2) #
                
                col += 1 #
                if col >= max_cols: #
                    col = 0 #
                    row += 1 #
            self.gui_instance_logger.info(f"Refreshed video list. Found {len(video_files)} videos.")

        except Exception as e: #
            self.gui_instance_logger.error(f"Error refreshing video checkbox list: {e}")
            messagebox.showerror("Error", f"Could not read video directory: {e}") #
        
    def browse_directory(self, string_var): #
        dirname = filedialog.askdirectory(initialdir=string_var.get() if string_var.get() else os.getcwd()) #
        if dirname: string_var.set(dirname) #

    def browse_file(self, string_var, save=False): #
        initial_dir_file = string_var.get() if string_var.get() else os.getcwd() #
        if save: #
            filename = filedialog.asksaveasfilename(initialfile=initial_dir_file, defaultextension=".log", #
                                                    filetypes=[("Log files", "*.log"), ("All files", "*.*")]) #
        else: #
            filename = filedialog.askopenfilename(initialfile=initial_dir_file) #
        if filename: string_var.set(filename) #
            
    def select_all_parts(self): #
        for var in self.selected_parts_vars.values(): var.set(True) #
        self.part3_enabled.set(True) # Also enable part 3 when selecting all
        self._toggle_part3_options() # Update radio button states

    def deselect_all_parts(self): #
        for var in self.selected_parts_vars.values(): var.set(False) #
        self.part3_enabled.set(False) # Also disable part 3 when deselecting all
        self._toggle_part3_options() # Update radio button states

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
            # BOW_ROI are general weapon activation ROI, INFINITE_ROI are bow-specific
            for k_int in ["NUMBER_ROI_X1", "NUMBER_ROI_Y1", "NUMBER_ROI_X2", "NUMBER_ROI_Y2", "NUMBER_MID", #
                      "BOW_ROI_X1", "BOW_ROI_Y1", "BOW_ROI_X2", "BOW_ROI_Y2", #
                      "INFINITE_ROI_X1", "INFINITE_ROI_Y1", "INFINITE_ROI_X2", "INFINITE_ROI_Y2"]: #
                config[k_int] = int(self.params[k_int].get()) #
            # BOW_SIMILARITY_THRESHOLD is general weapon activation threshold
            for k_float in ["BOW_SIMILARITY_THRESHOLD", "SIMILARITY_THRESHOLD_INFINITE", #
                      "COARSE_SCAN_INTERVAL_SECONDS", "FINE_SCAN_INTERVAL_SECONDS"]: #
                config[k_float] = float(self.params[k_float].get()) #
        except ValueError as e: #
            messagebox.showerror("Parameter Error", f"Invalid numeric parameter: {e}") #
            self.run_button.config(state=tk.NORMAL); return #
        
        selected_parts_set = {part_num for part_num, var in self.selected_parts_vars.items() if var.get()} #
        
        # Handle Part 3 selection based on the enable checkbox and radio buttons
        if self.part3_enabled.get():
            selected_parts_set.add('3') # Mark Part 3 as selected
            config["part3_mode"] = self.part3_clip_mode.get() # Store the chosen mode ("individual" or "merged")
        else:
            config["part3_mode"] = None # Part 3 is not running

        if not selected_parts_set: #
            messagebox.showwarning("No Parts Selected", "Please select at least one part to run.") #
            self.run_button.config(state=tk.NORMAL); return #
        config["selected_parts"] = selected_parts_set #
        
        config["selected_video_ids_for_processing"] = [ #
            video_id for video_id, var in self.video_checkbox_vars.items() if var.get() #
        ]
        if any(p in selected_parts_set for p in ['2', '3', '4', '5', '6']): #
            if not config["selected_video_ids_for_processing"] and self.video_checkbox_vars: #
                messagebox.showwarning("No Videos Selected", "Please select videos from the list for Parts 2-6, or ensure the list is refreshed.") #
                self.run_button.config(state=tk.NORMAL); return #

        # Get selected weapons for analysis
        config["selected_weapons_for_analysis"] = [
            name for name, var in self.selected_weapons_vars.items() if var.get()
        ]
        if '2' in selected_parts_set and not config["selected_weapons_for_analysis"]:
            messagebox.showwarning("No Weapons Selected", "Part 2 is selected, but no weapons are chosen for analysis. Please select at least one weapon.")
            self.run_button.config(state=tk.NORMAL); return
        if '3' in selected_parts_set and not config["selected_weapons_for_analysis"]: # Check if Part 3 is selected
            messagebox.showwarning("No Weapons for Clipping", "Part 3 is selected, but no weapons were selected for analysis (Part 2). Part 3 relies on Part 2's output for those weapons.")
            self.run_button.config(state=tk.NORMAL); return


        log_file_path_for_this_run = config["LOG_FILE_PATH"]

        self.gui_instance_logger.info(f"Starting processing thread. Log file target for this run: {log_file_path_for_this_run}")
        processing_thread = threading.Thread(target=self.run_processing_logic, args=(config, log_file_path_for_this_run), daemon=True) #
        processing_thread.start() #

    def run_processing_logic(self, config, current_log_file_path): #
        self._update_file_logging(current_log_file_path)
        
        logic_logger = logging.getLogger("VideoProcessingApp.Logic")

        logic_logger.info(f"Processing logic started. Using log file: {current_log_file_path}")
        logic_logger.info(f"Application starting via GUI (v{self.master.title().split('v')[-1]})...") #
        
        ROOT = config["ROOT"] #
        URLPATH = os.path.join(ROOT, "video_urls.txt") #
        
        infinite_symbol_template_path = os.path.join(ROOT, "pic_template", "template_infinite_bow.png") # Still needed for bow
        
        output_root_folder = os.path.join(ROOT, "clips_output") #
        os.makedirs(output_root_folder, exist_ok=True) #
        video_download_base_dir = os.path.join(ROOT, "downloaded_videos") #
        os.makedirs(video_download_base_dir, exist_ok=True) #
        
        selected_parts = config["selected_parts"] #
        selected_video_ids_to_process = config.get("selected_video_ids_for_processing", []) #
        selected_weapons_for_analysis = config.get("selected_weapons_for_analysis", []) #
        part3_clip_mode_selected = config.get("part3_mode") # Get the clipping mode for Part 3
        
        logic_logger.info(f"User selected Parts: {sorted(list(selected_parts))}") #
        if '3' in selected_parts:
            logic_logger.info(f"Part 3 clipping mode: {part3_clip_mode_selected}")
        if selected_weapons_for_analysis and '2' in selected_parts:
             logic_logger.info(f"User selected Weapons for Analysis (Part 2): {selected_weapons_for_analysis}")
        if selected_video_ids_to_process and any(p in selected_parts for p in ['2','3','4','5','6']): #
            logic_logger.info(f"User selected Video IDs for processing (Parts 2-6): {selected_video_ids_to_process}") #
        
        if '1' in selected_parts: #
            downloaded_video_files_info = [] #
            if os.path.exists(URLPATH): #
                with open(URLPATH, 'r', encoding='utf-8') as f: #
                    for line_num, line in enumerate(f, 1): #
                        line = line.strip() #
                        if not line or line.startswith('#'): continue #
                        try: #
                            parts = line.split(',') #
                            video_url = parts[0].strip() #
                            parsed_video_id = urlparse(video_url).path.split('/')[-1] or f"unknown_video_{line_num}" #
                            start_time_str, end_time_str = (parts[1].strip(), parts[2].strip()) if len(parts) == 3 else (None, None) #
                            if start_time_str and end_time_str: #
                                logic_logger.info(f"准备下载视频片段: {video_url} 从 {start_time_str} 到 {end_time_str}") #
                                downloaded_file_path = download_twitch(video_url, video_download_base_dir, start_time_str, end_time_str) #
                            elif len(parts) == 1: #
                                logic_logger.info(f"准备下载完整视频: {video_url}") #
                                downloaded_file_path = download_twitch(video_url, video_download_base_dir) #
                            else: #
                                logic_logger.warning(f"URL文件行格式错误: {line}，跳过。"); continue #
                            if downloaded_file_path and os.path.exists(downloaded_file_path): #
                                actual_filename = os.path.basename(downloaded_file_path) #
                                downloaded_video_files_info.append({"parsed_id": parsed_video_id, "filename": actual_filename, "path": downloaded_file_path}) #
                                logic_logger.info(f"视频 {parsed_video_id} (文件: {actual_filename}) 已下载或存在: {downloaded_file_path}") #
                            else: logic_logger.error(f"视频 {video_url} 未能成功下载或找到。") #
                        except Exception as e: logic_logger.error(f"处理URL文件行 '{line}' 时出错: {e}") #
            else: logic_logger.error(f"错误: video_urls.txt 文件未找到于 {URLPATH}") #
            logic_logger.info("--- Part 1 完成 ---") #
            self.master.after(0, self.refresh_video_checkboxes) #
        else: logic_logger.info("--- 跳过 Part 1: 下载视频 ---") #
        
        def get_filename_for_id(video_id, base_dir): #
            if not os.path.isdir(base_dir): return None #
            for item in os.listdir(base_dir): #
                if os.path.isfile(os.path.join(base_dir, item)) and item.startswith(video_id): #
                    name_part, ext_part = os.path.splitext(item) #
                    if name_part == video_id and ext_part.lower() in ['.mp4', '.mkv', '.avi', '.mov']: return item #
            return None #
            
        if '2' in selected_parts: #
            if not selected_video_ids_to_process: logic_logger.warning("Part 2: No videos selected. Skipping Part 2 as it depends on selection.") #
            elif not selected_weapons_for_analysis: logic_logger.warning("Part 2: No weapons selected for analysis. Skipping Part 2.")
            else: #
                if "bow" in selected_weapons_for_analysis and not os.path.exists(infinite_symbol_template_path):
                     logic_logger.error(f"错误: 无穷大符号模板图片 {infinite_symbol_template_path} 未找到 (required for Bow analysis).");
                
                logic_logger.info(f"开始分析选定的 {len(selected_video_ids_to_process)} 个视频, 针对武器: {selected_weapons_for_analysis}...") #
                processed_videos_in_part2 = 0 #
                for video_id in selected_video_ids_to_process: #
                    filename_in_dir = get_filename_for_id(video_id, video_download_base_dir) #
                    if not filename_in_dir: logic_logger.warning(f"Part 2: Video file for ID '{video_id}' not found. Skipping."); continue #
                    video_path_for_analysis = os.path.join(video_download_base_dir, filename_in_dir) #
                    logic_logger.info(f"\n[Part 2] 分析视频文件: {filename_in_dir} (ID: {video_id})") #
                    video_specific_output_dir_part2 = os.path.join(output_root_folder, video_id) #
                    os.makedirs(video_specific_output_dir_part2, exist_ok=True) #
                    
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
                    processed_videos_in_part2 += 1 #
                if processed_videos_in_part2 == 0 and selected_video_ids_to_process : logic_logger.info(f"Part 2: 没有选定视频被成功分析。") #
            logic_logger.info("--- Part 2 (分析) 完成 ---") #
        else: logic_logger.info("--- 跳过 Part 2: 分析视频 ---") #
        
        if '3' in selected_parts: #
            if not selected_video_ids_to_process:
                logic_logger.warning("Part 3: No videos selected. Skipping.")
            elif not selected_weapons_for_analysis:
                logic_logger.warning("Part 3: No weapons were selected for analysis (Part 2), "
                                     "so no weapon-specific TXT files to clip from. Skipping.")
            elif not part3_clip_mode_selected: # Should be caught by GUI checks, but defensive
                logic_logger.error("Part 3: Clipping mode not specified. Skipping.")
            else:
                logic_logger.info(f"开始为选定的 {len(selected_video_ids_to_process)} 个视频, "
                                 f"针对分析过的武器 {selected_weapons_for_analysis} 进行剪辑 (Part 3 - Mode: {part3_clip_mode_selected})...")

                for video_id in selected_video_ids_to_process:
                    if not os.path.isdir(video_download_base_dir):
                        logic_logger.error(f"Video dir not found for Part 3: {video_download_base_dir}. Breaking Part 3.")
                        break 

                    filename_in_dir_p3 = get_filename_for_id(video_id, video_download_base_dir)
                    if not filename_in_dir_p3:
                        logic_logger.warning(f"Part 3: Video file for ID '{video_id}' not found in "
                                             f"{video_download_base_dir}. Skipping video for Part 3.")
                        continue

                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p3)
                    video_specific_output_dir_p3_base = os.path.join(output_root_folder, video_id) # Base output dir for this video

                    if not os.path.exists(video_specific_output_dir_p3_base):
                        logic_logger.warning(f"Part 3: Base output directory '{video_specific_output_dir_p3_base}' "
                                             f"for video ID '{video_id}' not found (expected from Part 2). Skipping video for Part 3.")
                        continue

                    weapon_time_sources_for_this_video = []
                    for weapon_name_to_clip in selected_weapons_for_analysis:
                        weapon_times_txt_filename = f"shooting_{weapon_name_to_clip}.txt" # Assuming internal name is used for txt
                        weapon_shooting_times_txt_path = os.path.join(video_specific_output_dir_p3_base, weapon_times_txt_filename)

                        if os.path.exists(weapon_shooting_times_txt_path) and os.path.getsize(weapon_shooting_times_txt_path) > 0:
                            weapon_time_sources_for_this_video.append({
                                'file_path': weapon_shooting_times_txt_path,
                                'weapon_name': weapon_name_to_clip 
                            })
                        else:
                            logic_logger.info(f"Part 3: 时间文件 {weapon_times_txt_filename} for video {video_id} "
                                             f"(武器: {weapon_name_to_clip}) 不存在或为空. ")
                    
                    if weapon_time_sources_for_this_video:
                        logic_logger.info(f"Part 3 (Mode: {part3_clip_mode_selected}): 为视频 ID '{video_id}' 准备从 "
                                         f"{len(weapon_time_sources_for_this_video)} 个武器时间文件中收集时间戳进行剪辑.")
                        
                        # Create a subfolder for the specific clipping mode
                        clips_subfolder_name = f"clips_{part3_clip_mode_selected}" # e.g., "clips_individual" or "clips_merged"
                        final_clips_output_path = os.path.join(video_specific_output_dir_p3_base, clips_subfolder_name)
                        os.makedirs(final_clips_output_path, exist_ok=True)

                        if part3_clip_mode_selected == "individual":
                            generate_clips_from_multiple_weapon_times(
                                input_video_path=video_path_for_clipping,
                                weapon_time_sources=weapon_time_sources_for_this_video,
                                output_folder=final_clips_output_path, # Use the mode-specific subfolder
                                clip_duration=0.9 # Default duration, or make it a config
                            )
                        elif part3_clip_mode_selected == "merged":
                            generate_clips_from_multiple_weapon_times_merge(
                                input_video_path=video_path_for_clipping,
                                weapon_time_sources=weapon_time_sources_for_this_video,
                                output_folder=final_clips_output_path, # Use the mode-specific subfolder
                                clip_duration=0.9, # Base duration for individual events within merge
                                merge_threshold_factor=1.0 # Default factor, can be tuned
                            )
                    else:
                        logic_logger.info(f"Part 3: 没有找到有效的武器时间文件为视频 ID '{video_id}' 进行剪辑 (模式: {part3_clip_mode_selected}).")
                logic_logger.info(f"--- Part 3 (剪辑 - Mode: {part3_clip_mode_selected}) 完成 ---")
        else:
            logic_logger.info("--- 跳过 Part 3: 合并排序武器剪辑 ---")
        
        # Parts 4, 5, 6 remain Bow-specific as per interpretation
        if '4' in selected_parts: # BOW SPECIFIC
            if not selected_video_ids_to_process: logic_logger.warning("Part 4 (Bow Infinite Clip): No videos selected. Skipping.") #
            else: #
                logic_logger.info(f"开始为选定的 {len(selected_video_ids_to_process)} 个视频BOW INFINITE剪辑 (Part 4)...") #
                processed_clips_in_part4 = 0 #
                for video_id in selected_video_ids_to_process: #
                    if not os.path.isdir(video_download_base_dir): logic_logger.error(f"Video dir not found for Part 4."); break #
                    filename_in_dir_p4 = get_filename_for_id(video_id, video_download_base_dir) #
                    if not filename_in_dir_p4: logic_logger.warning(f"Part 4: File for '{video_id}' not found. Skipping."); continue #
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p4) #
                    video_specific_output_dir_p4 = os.path.join(output_root_folder, video_id) #
                    infinite_txt_path_for_clipping = os.path.join(video_specific_output_dir_p4, "infinite_2.txt") #  <-- infinite_2.txt as per existing code
                    if not os.path.exists(video_specific_output_dir_p4): #
                        logic_logger.warning(f"Part 4: Output directory '{video_specific_output_dir_p4}' for video ID '{video_id}' not found. Skipping.")
                        continue
                    if not (os.path.exists(infinite_txt_path_for_clipping) and os.path.getsize(infinite_txt_path_for_clipping) > 0): #
                        logic_logger.warning(f"Part 4: infinite_2.txt for {video_id} (Bow) at '{infinite_txt_path_for_clipping}' missing or empty. Skipping.")
                        continue #
                    # Ensure clip_video_ffmpeg_with_duration is correctly creating subfolders or if output_folder is the final one.
                    # Current structure passes video_specific_output_dir_p4, which implies clips go directly into ".../videoid/"
                    # If Part 4 clips need their own subfolder (e.g., "clips_bow_infinite"), this needs adjustment here or in the function.
                    # For now, assuming clips go into video_specific_output_dir_p4 directly.
                    clip_video_ffmpeg_with_duration(video_path_for_clipping, infinite_txt_path_for_clipping, video_specific_output_dir_p4) #
                    processed_clips_in_part4 +=1 #
                if processed_clips_in_part4 == 0 and selected_video_ids_to_process: logic_logger.info(f"Part 4: 没有选定视频被剪辑 (Bow Infinite)。") #
            logic_logger.info("--- Part 4 (BOW INFINITE剪辑) 完成 ---") #
        else: logic_logger.info("--- 跳过 Part 4: BOW INFINITE剪辑 ---") #
        
        if '5' in selected_parts: # BOW SPECIFIC
            if not selected_video_ids_to_process: logic_logger.warning("Part 5 (Merge Bow TXTs): No videos for TXT merge. Skipping.") #
            else: #
                logic_logger.info(f"开始为选定的 {len(selected_video_ids_to_process)} 个视频ID合并BOW TXT (Part 5)...") #
                processed_merges_in_part5 = 0 #
                for video_id in selected_video_ids_to_process: #
                    video_specific_output_dir_p5 = os.path.join(output_root_folder, video_id) #
                    if not os.path.isdir(video_specific_output_dir_p5): logic_logger.warning(f"Part 5: Output dir for {video_id} ('{video_specific_output_dir_p5}') not found. Skipping."); continue #
                    logic_logger.info(f"\n[Part 5] 为视频ID {video_id} 合并两个Bow txt") #
                    shooting_bow_file = os.path.join(video_specific_output_dir_p5, "shooting_bow.txt") # Assumes Part 2 created this if bow was selected
                    infinite_file_to_merge = os.path.join(video_specific_output_dir_p5, "infinite_3.txt") # Assumes this is created if bow analysis ran / or refers to infinite.txt
                    
                    if not os.path.exists(shooting_bow_file): #
                        logic_logger.warning(f"Part 5: shooting_bow.txt for {video_id} at '{shooting_bow_file}' missing. Skipping merge for this ID.")
                        continue #
                    # infinite_3.txt might not exist if no infinite moments, process_and_merge_times should handle this
                    process_and_merge_times(shooting_bow_file, infinite_file_to_merge) #
                    processed_merges_in_part5 +=1 #
                if processed_merges_in_part5 == 0 and selected_video_ids_to_process: logic_logger.info(f"Part 5: 没有选定视频的Bow TXT文件被成功启动合并（或源文件缺失）。") #
            logic_logger.info("--- Part 5 (合并BOW TXT) 完成 ---") #
        else: logic_logger.info("--- 跳过 Part 5: 合并 BOW TXT ---") #
        
        if '6' in selected_parts: # BOW SPECIFIC
            if not selected_video_ids_to_process: logic_logger.warning("Part 6 (Clip Bow Merged): No videos selected. Skipping.") #
            else: #
                logic_logger.info(f"开始为选定的 {len(selected_video_ids_to_process)} 个视频BOW SUM剪辑 (Part 6)...") #
                processed_clips_in_part6 = 0 #
                for video_id in selected_video_ids_to_process: #
                    if not os.path.isdir(video_download_base_dir): logic_logger.error(f"Video dir not found for Part 6."); break #
                    filename_in_dir_p6 = get_filename_for_id(video_id, video_download_base_dir) #
                    if not filename_in_dir_p6: logic_logger.warning(f"Part 6: File for '{video_id}' not found. Skipping."); continue #
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p6) #
                    video_specific_output_dir_p6 = os.path.join(output_root_folder, video_id) #
                    sum_txt_path_for_clipping = os.path.join(video_specific_output_dir_p6, "shooting_bow_sum.txt") #
                    if not os.path.exists(video_specific_output_dir_p6): #
                        logic_logger.warning(f"Part 6: Output directory '{video_specific_output_dir_p6}' for video ID '{video_id}' not found. Skipping.")
                        continue
                    if not (os.path.exists(sum_txt_path_for_clipping) and os.path.getsize(sum_txt_path_for_clipping) > 0): #
                        logic_logger.warning(f"Part 6: shooting_bow_sum.txt for {video_id} at '{sum_txt_path_for_clipping}' missing or empty. Skipping.")
                        continue #
                    # Your original code used clip_video_ffmpeg with weapon_name="bow_sum"
                    # clip_video_ffmpeg_merged is also an option if sum.txt can have overlapping times from its merge process.
                    # Sticking to original use of clip_video_ffmpeg for sum.txt.
                    # If subfolders are desired for Part 6 clips, similar logic as Part 3 would be needed.
                    # For now, clips go directly into video_specific_output_dir_p6.
                    clip_video_ffmpeg(video_path_for_clipping, sum_txt_path_for_clipping, video_specific_output_dir_p6, clip_duration=0.9, weapon_name="bow_sum") # Added weapon_name argument to match definition if using it
                    processed_clips_in_part6 +=1 #
                if processed_clips_in_part6 == 0 and selected_video_ids_to_process: logic_logger.info(f"Part 6: 没有选定视频被剪辑 (Bow Merged)。") #
            logic_logger.info("--- Part 6 (BOW SUM剪辑) 完成 ---") #
        else: logic_logger.info("--- 跳过 Part 6: BOW SUM剪辑 ---") #
        
        logic_logger.info(f"\n脚本运行结束。选择运行的Parts: {sorted(list(selected_parts))}") #
        self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL)) #

if __name__ == "__main__": #
    root = tk.Tk() #
    app = VideoProcessingGUI(root) #
    root.mainloop() #