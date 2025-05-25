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
        '-o', final_file_mp4, # 直接使用最终的mp4文件名
        '--merge-output-format', 'mp4',
    ]
    if start_time and end_time:
        command += ['--download-sections', f"*{start_time}-{end_time}"]

    try:
        logger.info(f"执行下载命令: {' '.join(command)}")
        result = subprocess.run(command, check=True, text=True, capture_output=True, encoding='utf-8')
        if result.stdout: # 记录 yt-dlp 的标准输出
            logger.info(f"yt-dlp STDOUT:\n{result.stdout}") #只记录不打印冗余信息
        logger.info(f"下载成功： {final_file_mp4}\n --------------------\n ")
        return final_file_mp4
    except subprocess.CalledProcessError as e:
        logger.error(f"下载出错: {e}")
        logger.error(f"命令: {' '.join(e.cmd)}")
        logger.error(f"返回码: {e.returncode}")
        if e.stdout: logger.error(f"输出: {e.stdout[:1000]}")
        if e.stderr: logger.error(f"错误输出: {e.stderr[:1000]}")
    except FileNotFoundError:
        logger.error("错误：未找到 yt-dlp，请确保已安装并配置环境变量")
    return None

def seconds_to_hms(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs_val = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs_val:06.3f}"

def hms_to_seconds(time_str):
    parts = time_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"时间格式错误: '{time_str}'. 需要 HH:MM:SS.mmm 格式。")
    hours = int(parts[0])
    minutes = int(parts[1])
    if '.' in parts[2]:
        seconds_part_str, milliseconds_str = parts[2].split('.')
        seconds_part = int(seconds_part_str)
        milliseconds = int(milliseconds_str.ljust(3, '0')[:3]) # 保证3位毫秒
        total_seconds = hours * 3600 + minutes * 60 + seconds_part + milliseconds / 1000.0
    else:
        total_seconds = hours * 3600 + minutes * 60 + int(parts[2])
    return total_seconds

def hmsff_to_seconds(hmsff_str):
    if not isinstance(hmsff_str, str):
        raise ValueError(f"Invalid input type for hmsff_str: {type(hmsff_str)}. Expected string.")

    parts = hmsff_str.split(':')
    if len(parts) != 4:
        raise ValueError(f"Time string '{hmsff_str}' is not in HH:MM:SS:ff format (Expected 4 parts, got {len(parts)}).")

    try:
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2])
        ff = int(parts[3])

        if not (0 <= h):
             raise ValueError(f"Hours '{h}' in '{hmsff_str}' is invalid (must be non-negative).")
        if not (0 <= m <= 59):
            raise ValueError(f"Minutes '{m}' in '{hmsff_str}' is invalid (must be 0-59).")
        if not (0 <= s <= 59):
            raise ValueError(f"Seconds '{s}' in '{hmsff_str}' is invalid (must be 0-59).")
        if not (0 <= ff <= 59): # Assuming ff is also base 60 (0-59)
            raise ValueError(f"FF component '{ff}' in '{hmsff_str}' is invalid (must be 0-59).")

        return h * 3600 + m * 60 + s + ff / 60.0
    except ValueError as e:
        if "in '{hmsff_str}'" in str(e) or "Time string" in str(e): raise
        raise ValueError(f"Error parsing components of time string '{hmsff_str}': {e}")
    except Exception as e:
        raise ValueError(f"Unexpected error parsing time string '{hmsff_str}': {e}")