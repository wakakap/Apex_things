import os
import subprocess
import datetime

# --- Configuration (Adjust these paths to match your setup) ---
# These should ideally be consistent with your main.py settings
ROOT_PROJECT_DIR = "E:\\mande\\0_PLAN"  # Your main project root
CLIPS_OUTPUT_ROOT_FOLDER = os.path.join(ROOT_PROJECT_DIR, "clips_output")
ORIGINAL_VIDEOS_DIR = os.path.join(ROOT_PROJECT_DIR, "downloaded_videos")

LOG_FILE_NAME = "clip_infinite_segments.log"
INFINITE_TIMESTAMP_FILENAME = "infinite_2.txt"
OUTPUT_SUBFOLDER_FOR_CLIPS = "infinite_clips" # Clips will be saved here within each video's folder

# --- Logging Function (Consistent with previous scripts) ---
def print_and_log(message, log_file=LOG_FILE_NAME):
    """Prints message to console and appends to log file with timestamp."""
    print(message)
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Fatal Error: Could not write to log file {log_file}: {e}")

# --- Timestamp Conversion Functions (Copied from analysis_functions.py for standalone use) ---
def hms_to_seconds(time_str):
    """Converts HH:MM:SS.mmm or HH:MM:SS to seconds."""
    parts = time_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"时间格式错误: '{time_str}'. 需要 HH:MM:SS.mmm 或 HH:MM:SS 格式。")
    hours = int(parts[0])
    minutes = int(parts[1])
    if '.' in parts[2]:
        seconds_part_str, milliseconds_str = parts[2].split('.')
        seconds_part = int(seconds_part_str)
        # Pad milliseconds if necessary, e.g., "1" becomes "100"
        milliseconds = int(milliseconds_str.ljust(3, '0')[:3])
        total_seconds = hours * 3600 + minutes * 60 + seconds_part + milliseconds / 1000.0
    else:
        total_seconds = hours * 3600 + minutes * 60 + float(parts[2]) # Allow float seconds here
    return total_seconds

def seconds_to_hms(seconds_float):
    """Converts seconds (float) to HH:MM:SS.mmm format string."""
    if not isinstance(seconds_float, (int, float)) or seconds_float < 0:
        raise ValueError("Input must be a non-negative number.")
    hours = int(seconds_float // 3600)
    minutes = int((seconds_float % 3600) // 60)
    secs = seconds_float % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


# --- FFmpeg Clipping Function for Segments (Start and End Time) ---
def create_clip_ffmpeg_segment(input_video_path, start_time_hms, end_time_hms, output_clip_path):
    """
    Clips a video segment using ffmpeg given start and end timestamps.
    Returns True on success, False on failure.
    """
    output_dir = os.path.dirname(output_clip_path)
    os.makedirs(output_dir, exist_ok=True)

    if os.path.exists(output_clip_path):
        print_and_log(f"片段 {output_clip_path} 已存在，跳过。", LOG_FILE_NAME)
        return True # Or False if you prefer to indicate no new action was taken

    try:
        # Validate timestamps before passing to ffmpeg
        start_s = hms_to_seconds(start_time_hms)
        end_s = hms_to_seconds(end_time_hms)
        if start_s >= end_s:
            print_and_log(f"错误: 开始时间 ({start_time_hms}) 大于或等于结束时间 ({end_time_hms}). 跳过片段: {output_clip_path}", LOG_FILE_NAME)
            return False
    except ValueError as e:
        print_and_log(f"错误: 无效的时间戳格式在转换时发生错误. 开始: '{start_time_hms}', 结束: '{end_time_hms}'. 错误: {e}", LOG_FILE_NAME)
        return False

    command = [
        'ffmpeg',
        '-ss', str(start_time_hms),  # Start time
        '-i', input_video_path,
        '-to', str(end_time_hms),    # End time
        '-c:v', 'libx264',         # Or your preferred video codec
        '-preset', 'fast',         # Encoding preset
        '-c:a', 'aac',             # Or your preferred audio codec
        '-strict', '-2',           # For older ffmpeg versions if using experimental aac
        '-y',                      # Overwrite output file if it exists (safety, though we check above)
        output_clip_path
    ]

    try:
        print_and_log(f"执行剪辑命令: {' '.join(command)}", LOG_FILE_NAME)
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        if result.stdout:
             print_and_log(f"FFmpeg STDOUT for {os.path.basename(output_clip_path)}:\n{result.stdout}", LOG_FILE_NAME)
        if result.stderr: # FFmpeg often uses stderr for info too
             print_and_log(f"FFmpeg STDERR for {os.path.basename(output_clip_path)}:\n{result.stderr}", LOG_FILE_NAME)
        print_and_log(f"成功剪辑并保存: {output_clip_path}", LOG_FILE_NAME)
        return True
    except subprocess.CalledProcessError as e:
        print_and_log(f"FFmpeg剪辑视频时出错 (片段: {start_time_hms}-{end_time_hms}): {e}", LOG_FILE_NAME)
        print_and_log(f"FFmpeg 命令: {' '.join(e.cmd)}", LOG_FILE_NAME)
        if e.stdout: print_and_log(f"FFmpeg 输出: {e.stdout}", LOG_FILE_NAME)
        if e.stderr: print_and_log(f"FFmpeg 错误输出: {e.stderr}", LOG_FILE_NAME)
        return False
    except FileNotFoundError:
        print_and_log("错误：未找到 ffmpeg。请确保已安装并配置在系统路径中。", LOG_FILE_NAME)
        return False
    except Exception as e:
        print_and_log(f"剪辑时发生未知错误: {e}", LOG_FILE_NAME)
        return False

# --- Main Processing Logic ---
def process_infinite_txt_files():
    print_and_log(f"脚本开始: 处理 '{INFINITE_TIMESTAMP_FILENAME}' 文件进行剪辑.", LOG_FILE_NAME)
    print_and_log(f"扫描视频分析输出目录: {CLIPS_OUTPUT_ROOT_FOLDER}", LOG_FILE_NAME)
    print_and_log(f"原始视频来源目录: {ORIGINAL_VIDEOS_DIR}", LOG_FILE_NAME)

    if not os.path.isdir(CLIPS_OUTPUT_ROOT_FOLDER):
        print_and_log(f"错误: clips_output 根目录 '{CLIPS_OUTPUT_ROOT_FOLDER}' 未找到。脚本终止。", LOG_FILE_NAME)
        return
    if not os.path.isdir(ORIGINAL_VIDEOS_DIR):
        print_and_log(f"错误: 原始视频目录 '{ORIGINAL_VIDEOS_DIR}' 未找到。脚本终止。", LOG_FILE_NAME)
        return

    processed_video_folders = 0
    total_clips_generated = 0

    for video_id_folder_name in os.listdir(CLIPS_OUTPUT_ROOT_FOLDER):
        video_specific_output_dir = os.path.join(CLIPS_OUTPUT_ROOT_FOLDER, video_id_folder_name)

        if not os.path.isdir(video_specific_output_dir):
            continue # Skip files, only process directories

        timestamp_txt_path = os.path.join(video_specific_output_dir, INFINITE_TIMESTAMP_FILENAME)

        if os.path.exists(timestamp_txt_path):
            print_and_log(f"\n找到 '{INFINITE_TIMESTAMP_FILENAME}' 对于视频文件夹: {video_id_folder_name}", LOG_FILE_NAME)
            processed_video_folders += 1

            # Attempt to find the original video file.
            # Assumes video_id_folder_name is the video ID (e.g., '1234567890')
            # and original videos are .mp4, .mkv etc.
            original_video_file_path = None
            possible_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.ts'] # Add more if needed
            for ext in possible_extensions:
                path_candidate = os.path.join(ORIGINAL_VIDEOS_DIR, video_id_folder_name + ext)
                if os.path.exists(path_candidate):
                    original_video_file_path = path_candidate
                    break

            if not original_video_file_path:
                print_and_log(f"警告: 原始视频文件 '{video_id_folder_name + ext}' 未在 '{ORIGINAL_VIDEOS_DIR}' 找到. 跳过此文件夹的剪辑.", LOG_FILE_NAME)
                continue

            print_and_log(f"使用原始视频: {original_video_file_path}", LOG_FILE_NAME)

            clips_for_this_video = 0
            with open(timestamp_txt_path, 'r', encoding='utf-8') as f_times:
                for line_num, line in enumerate(f_times, 1):
                    line = line.strip()
                    if not line or line.startswith('#'): # Skip empty lines or comments
                        continue

                    parts = line.split(',')
                    if len(parts) != 2:
                        print_and_log(f"警告: 在文件 '{timestamp_txt_path}' 第 {line_num} 行格式错误: '{line}'. 需要两个逗号分隔的时间戳. 跳过此行.", LOG_FILE_NAME)
                        continue

                    start_time_str = parts[0].strip()
                    end_time_str = parts[1].strip()

                    # Sanitize timestamps for filename
                    start_safe = start_time_str.replace(":", "").replace(".", "")
                    end_safe = end_time_str.replace(":", "").replace(".", "")

                    # Define output path for the clip
                    clip_output_folder = os.path.join(video_specific_output_dir, OUTPUT_SUBFOLDER_FOR_CLIPS)
                    # os.makedirs(clip_output_folder, exist_ok=True) # create_clip_ffmpeg_segment will do this

                    output_clip_filename = f"{video_id_folder_name}_infinite_{line_num}_{start_safe}_to_{end_safe}.mp4"
                    output_clip_full_path = os.path.join(clip_output_folder, output_clip_filename)

                    if create_clip_ffmpeg_segment(original_video_file_path, start_time_str, end_time_str, output_clip_full_path):
                        clips_for_this_video += 1
                        total_clips_generated +=1

            if clips_for_this_video > 0:
                print_and_log(f"为视频 '{video_id_folder_name}' 生成了 {clips_for_this_video} 个片段。", LOG_FILE_NAME)
            else:
                print_and_log(f"视频 '{video_id_folder_name}' 没有生成新的片段 (可能已存在或时间戳文件为空/无效)。", LOG_FILE_NAME)
        # else:
            # print_and_log(f"在文件夹 '{video_id_folder_name}' 未找到 '{INFINITE_TIMESTAMP_FILENAME}'.", LOG_FILE_NAME) # Optional: log if file not found


    print_and_log(f"\n--- 处理完成 ---", LOG_FILE_NAME)
    print_and_log(f"扫描了 {processed_video_folders} 个包含 '{INFINITE_TIMESTAMP_FILENAME}' 的视频文件夹。", LOG_FILE_NAME)
    print_and_log(f"总共生成了 {total_clips_generated} 个新片段。", LOG_FILE_NAME)
    print_and_log(f"脚本结束。日志保存在: {os.path.abspath(LOG_FILE_NAME)}", LOG_FILE_NAME)

if __name__ == "__main__":
    # Optional: Clear or backup old log file at the start of a new run
    # if os.path.exists(LOG_FILE_NAME):
    #     os.rename(LOG_FILE_NAME, LOG_FILE_NAME + "." + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + ".bak")
    # Or simply append:
    with open(LOG_FILE_NAME, 'a', encoding='utf-8') as f:
        f.write(f"\n\n--- Script run started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    process_infinite_txt_files()