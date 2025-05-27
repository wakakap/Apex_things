import os
import subprocess
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

def download_twitch(video_url, outputfile, start_time=None, end_time=None, stream='bestvideo+bestaudio/best'):
    parsed_url = urlparse(video_url)
    video_code = parsed_url.path.split('/')[-1]
    # 文件名模板的确定逻辑保持不变
    if start_time and end_time:
        # For partial downloads, it might be good to reflect this in filename, but current logic doesn't.
        output_path_template = os.path.join(outputfile, f"{video_code}.%(ext)s")
    else:
        output_path_template = os.path.join(outputfile, f"{video_code}.%(ext)s")

    os.makedirs(outputfile, exist_ok=True)
    # 确定最终的 .mp4 文件名
    final_file_mp4 = output_path_template.replace('.%(ext)s', '.mp4')


    if os.path.exists(final_file_mp4):
        logger.info(f"{final_file_mp4} 已存在，跳过下载。")
        return final_file_mp4

    command = [
        'yt-dlp', video_url,
        '-f', stream,
        # '--remux-video', 'mp4', # Alternative to --merge-output-format if issues
        '-o', final_file_mp4, # 直接使用最终的mp4文件名
        '--merge-output-format', 'mp4', # Ensures output is mp4 after download and merge
    ]
    if start_time and end_time:
        command += ['--download-sections', f"*{start_time}-{end_time}"]
        # If using --download-sections, yt-dlp might output to a temp name then rename.
        # The -o template should still work for the final name.

    try:
        logger.info(f"执行下载命令: {' '.join(command)}")
        # Using errors='replace' for wider compatibility with yt-dlp output.
        result = subprocess.run(command, check=True, text=True, capture_output=True, encoding='utf-8', errors='replace')
        if result.stdout: 
            logger.debug(f"yt-dlp STDOUT:\n{result.stdout.strip()}") # Changed to debug
        if result.stderr and result.stderr.strip(): # yt-dlp often puts progress here
             logger.debug(f"yt-dlp STDERR:\n{result.stderr.strip()}") # Changed to debug
        logger.info(f"下载成功： {final_file_mp4}\n --------------------\n ")
        return final_file_mp4
    except subprocess.CalledProcessError as e:
        logger.error(f"下载出错: {e}")
        logger.error(f"命令: {' '.join(e.cmd)}")
        logger.error(f"返回码: {e.returncode}")
        if e.stdout: logger.error(f"输出: {e.stdout[:1000].strip()}")
        if e.stderr: logger.error(f"错误输出: {e.stderr[:1000].strip()}")
    except FileNotFoundError:
        logger.error("错误：未找到 yt-dlp，请确保已安装并配置环境变量")
    return None

def seconds_to_hms(seconds):
    if not isinstance(seconds, (int, float)):
        raise TypeError(f"Input 'seconds' must be a number, got {type(seconds)}")
    if seconds < 0:
        # Handle negative seconds if necessary, or raise error
        # For now, let's assume non-negative, or format it with a sign
        sign = "-"
        seconds = abs(seconds)
    else:
        sign = ""

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs_val = seconds % 60
    # Ensure milliseconds are exactly 3 digits, handling potential floating point inaccuracies
    # Format seconds to have 3 decimal places, then split
    secs_str = f"{secs_val:.3f}" 
    if '.' not in secs_str: # if it's a whole number like 5.000 -> 5
        secs_formatted = f"{int(secs_val):02d}.000"
    else:
        main_secs, milli_secs = secs_str.split('.')
        secs_formatted = f"{int(main_secs):02d}.{milli_secs.ljust(3,'0')[:3]}"
        
    return f"{sign}{hours:02d}:{minutes:02d}:{secs_formatted}"


def hms_to_seconds(time_str):
    if not isinstance(time_str, str):
        raise ValueError(f"时间格式错误: Input must be a string, got {type(time_str)}")
    
    parts = time_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"时间格式错误: '{time_str}'. 需要 HH:MM:SS.mmm 格式。")
    
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        
        sec_part_str = parts[2]
        if '.' in sec_part_str:
            main_seconds_str, milliseconds_str = sec_part_str.split('.', 1)
            seconds_part = int(main_seconds_str)
            # Ensure milliseconds_str is treated correctly (e.g., "1" -> 100, "12" -> 120, "123" -> 123)
            milliseconds = int(milliseconds_str.ljust(3, '0')[:3])
            total_seconds = hours * 3600 + minutes * 60 + seconds_part + milliseconds / 1000.0
        else:
            seconds_part = int(sec_part_str)
            total_seconds = hours * 3600 + minutes * 60 + seconds_part

        if hours < 0 : # Allow negative hours if time_str starts with "-", but ensure other parts are positive magnitude
             raise ValueError(f"时间格式中的小时部分 '{parts[0]}' 不能为负数，除非整个时间表示负时长，但这通常不由hms_to_seconds处理。")
        if not (0 <= minutes <= 59):
             raise ValueError(f"时间格式中的分钟部分 '{parts[1]}' 无效 (必须是 0-59)。")
        if not (0 <= seconds_part <= 59 if '.' not in sec_part_str else 0 <= int(main_seconds_str) <= 59 ): # Check seconds part
             raise ValueError(f"时间格式中的秒部分 '{sec_part_str}' 无效 (必须是 0-59)。")

        return total_seconds
    except ValueError as e: # Catch int conversion errors or custom ValueErrors
        # Re-raise with more context or the original error if it's already descriptive
        if "时间格式错误" in str(e) or "无效" in str(e): raise
        raise ValueError(f"解析时间字符串 '{time_str}' 时出错: {e}")


def hmsff_to_seconds(hmsff_str):
    # This function expects HH:MM:SS:FF where FF might be frames or another unit.
    # The original implementation assumed FF was /60.0, which is like seconds.
    # If FF represents frames at a certain FPS, this would need adjustment.
    # For now, keeping it as /60.0 as per original structure.
    if not isinstance(hmsff_str, str):
        raise ValueError(f"Invalid input type for hmsff_str: {type(hmsff_str)}. Expected string.")

    parts = hmsff_str.split(':')
    if len(parts) != 4: # HH:MM:SS:FF
        raise ValueError(f"Time string '{hmsff_str}' is not in HH:MM:SS:ff format (Expected 4 parts, got {len(parts)}).")

    try:
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2])
        ff = int(parts[3]) # Assuming ff is the 'fractional' part, treated like 1/60th of a second here

        if not (0 <= h): # Hours can be large
             raise ValueError(f"Hours '{h}' in '{hmsff_str}' is invalid (must be non-negative).")
        if not (0 <= m <= 59):
            raise ValueError(f"Minutes '{m}' in '{hmsff_str}' is invalid (must be 0-59).")
        if not (0 <= s <= 59):
            raise ValueError(f"Seconds '{s}' in '{hmsff_str}' is invalid (must be 0-59).")
        # Assuming ff is also base 60 like here (0-59). If ff is frames, e.g. 0-29 for 30fps, this check might change.
        if not (0 <= ff <= 59): 
            # If ff represents frames at a different base (e.g. 30 FPS, 60 FPS), the upper bound and division would change.
            # For example, if ff is frames at 30 FPS, it would be ff / 30.0.
            # The original code used ff / 60.0, implying it's treated like another second unit.
            logger.warning(f"FF component '{ff}' in '{hmsff_str}' is {ff}. Original code treats this as base 60 (0-59).")
            # For robustness, let's allow it but log if it's outside typical 0-59 unless it's explicitly frames at a certain rate.
            # If it's truly a frame number that can exceed 59, the interpretation of ff/60.0 needs review.

        return h * 3600 + m * 60 + s + (ff / 60.0) # Original logic: ff is divided by 60
    except ValueError as e: # Catch int conversion errors
        if "in '{hmsff_str}'" in str(e) or "Time string" in str(e): raise # If it's one of our custom messages
        raise ValueError(f"Error parsing components of time string '{hmsff_str}': {e}") # General parsing error
    except Exception as e: # Catch any other unexpected error
        raise ValueError(f"Unexpected error parsing time string '{hmsff_str}': {e}")