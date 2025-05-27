import os
import logging
import subprocess
from general_function import (
    seconds_to_hms,hms_to_seconds,hmsff_to_seconds
)

logger = logging.getLogger(__name__)

def generate_clips_from_multiple_weapon_times(input_video_path, weapon_time_sources, output_folder, clip_duration=0.8):
    """
    Generates clips from multiple weapon timestamp files, sorted chronologically with a global clip index.

    Args:
        input_video_path (str): Path to the input video.
        weapon_time_sources (list): A list of dictionaries, where each dict is
                                    {'file_path': str, 'weapon_name': str}.
        output_folder (str): Folder to save the clips.
        clip_duration (float): Duration of each clip in seconds.
    """
    if not os.path.exists(input_video_path):
        logger.error(f"错误: 输入视频文件未找到 {input_video_path}")
        return

    all_timestamps_info = [] # Will store dicts: {'time_sec': float, 'weapon_name': str, 'original_hms': str}
    
    for source_info in weapon_time_sources:
        file_path = source_info['file_path']
        weapon_name = source_info['weapon_name']
        
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            logger.info(f"时间文件 {os.path.basename(file_path)} (武器: {weapon_name}) 不存在或为空，跳过。")
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                logger.info(f"读取时间文件: {file_path} (武器: {weapon_name})")
                for line_num, line_content in enumerate(f, 1):
                    start_hms = line_content.strip()
                    if not start_hms:
                        continue
                    try:
                        start_sec = hms_to_seconds(start_hms)
                        all_timestamps_info.append({
                            'time_sec': start_sec,
                            'weapon_name': weapon_name,
                            'original_hms': start_hms 
                        })
                    except ValueError as e:
                        logger.warning(f"解析时间戳 '{start_hms}' 错误 (来自 {os.path.basename(file_path)}, 行 {line_num}, 武器: {weapon_name}): {e}。跳过此时间戳。")
        except Exception as e:
            logger.error(f"读取时间文件 {file_path} (武器: {weapon_name}) 时出错: {e}")

    if not all_timestamps_info:
        logger.info(f"没有从提供的源文件中收集到有效的时间戳进行剪辑。视频: {os.path.basename(input_video_path)}")
        return

    # 按时间顺序对所有收集到的时间戳进行排序
    all_timestamps_info.sort(key=lambda x: x['time_sec'])
    
    # 可选：去重逻辑。如果多个武器在完全相同的时间（精确到毫秒）有记录，
    # 当前逻辑会为每个记录创建一个片段，文件名中包含各自的武器名。
    # 如果需要基于时间戳去重，则需决定哪个武器优先，或如何处理。
    # 例如，可以创建一个set of tuples (time_sec, weapon_name) 来确保唯一性，
    # 但这可能会丢失来自不同武器的相同时间戳。目前保持原样，按排序处理。

    os.makedirs(output_folder, exist_ok=True)
    video_name_no_ext = os.path.splitext(os.path.basename(input_video_path))[0]
    input_video_extension = os.path.splitext(input_video_path)[1]
    if not input_video_extension: 
        logger.warning(f"警告: 输入视频 {input_video_path} 没有文件扩展名。默认使用 .mp4 输出。")
        input_video_extension = ".mp4"

    logger.info(f"开始合并剪辑视频: {os.path.basename(input_video_path)}, "
                  f"共 {len(all_timestamps_info)} 个候选片段 (来自所有选定武器, 已排序), "
                  f"片段时长: {clip_duration}s")
    
    clips_created_count = 0
    for i, ts_info in enumerate(all_timestamps_info):
        start_sec_float = ts_info['time_sec']
        current_weapon_name = ts_info['weapon_name']
        original_hms_for_log = ts_info['original_hms'] # 用于日志记录
        
        formatted_start_time_for_ffmpeg = seconds_to_hms(start_sec_float)
        safe_time_str_for_filename = formatted_start_time_for_ffmpeg.replace(':', '').replace('.', '')

        # 使用全局索引 i+1 来命名片段序号
        output_clip_name = f"{video_name_no_ext}_{safe_time_str_for_filename}_clip_{i+1}_{current_weapon_name}{input_video_extension}"
        output_clip_path = os.path.join(output_folder, output_clip_name)

        if os.path.exists(output_clip_path):
            logger.info(f"片段 {output_clip_path} 已存在，跳过。")
            continue
        
        command = [
            'ffmpeg',
            '-ss', formatted_start_time_for_ffmpeg, 
            '-i', input_video_path,                 
            '-t', str(clip_duration),               
            '-codec', 'copy',                       
            '-y',                                   
            output_clip_path
        ]
        
        try:
            logger.info(f"执行剪辑命令 ({i+1}/{len(all_timestamps_info)} for {current_weapon_name} @ {original_hms_for_log}): {' '.join(command)}") 
            process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if process.stdout and process.stdout.strip():
                logger.debug(f"FFmpeg STDOUT for {output_clip_name}:\n{process.stdout.strip()}")
            if process.stderr and process.stderr.strip():
                logger.debug(f"FFmpeg STDERR for {output_clip_name}:\n{process.stderr.strip()}") # FFmpeg info often goes to stderr
            logger.info(f"成功剪辑并保存: {output_clip_path}")
            clips_created_count += 1
        except subprocess.CalledProcessError as e:
            logger.error(f"剪辑视频时出错 (片段 {i+1}, 起始: {formatted_start_time_for_ffmpeg}, 武器: {current_weapon_name}): {e}")
            logger.error(f"命令: {' '.join(e.cmd)}")
            if e.stderr: logger.error(f"FFmpeg错误输出: {e.stderr.strip()}")
            if e.stdout: logger.error(f"FFmpeg输出: {e.stdout.strip()}") # Log stdout on error too
        except Exception as e: 
            logger.error(f"处理片段 {i+1} (起始: {formatted_start_time_for_ffmpeg}, 武器: {current_weapon_name}) 时发生未知错误: {e}")

    if clips_created_count > 0:
        logger.info(f"合并剪辑完成。共创建 {clips_created_count} 个新片段。")
    elif all_timestamps_info: # Timestamps were present, but no clips made
        logger.info(f"未创建新片段 (可能所有目标片段已存在或在处理过程中发生错误)。")
    # No specific message if all_timestamps_info was empty, already logged above.


def clip_video_ffmpeg(input_video_path, shooting_times_file, output_folder, clip_duration=0.8):
    if not os.path.exists(shooting_times_file):
        logger.info(f"错误: shooting_bow.txt 文件未找到 {shooting_times_file}")
        return
    if os.path.getsize(shooting_times_file) == 0:
        logger.info(f"提示: {shooting_times_file} 为空，没有片段可剪辑。")
        return

    os.makedirs(output_folder, exist_ok=True)
    video_name_no_ext = os.path.splitext(os.path.basename(input_video_path))[0]
    # Get the extension of the input video to use for the output clips
    input_video_extension = os.path.splitext(input_video_path)[1]
    if not input_video_extension: # Fallback if no extension
        logger.info(f"警告: 输入视频 {input_video_path} 没有文件扩展名。默认使用 .mp4 输出。")
        input_video_extension = ".mp4"


    try:
        with open(shooting_times_file, 'r', encoding='utf-8') as f:
            start_times_hms_list = f.readlines()
    except Exception as e:
        logger.error(f"读取时间戳文件 {shooting_times_file} 时出错: {e}")
        return

    if not start_times_hms_list:
        logger.info(f"没有在 {shooting_times_file} 中找到射击时刻。")
        return

    logger.info(f"开始剪辑视频: {input_video_path}, 共 {len(start_times_hms_list)} 个片段, 片段时长: {clip_duration}s, 尝试保持原格式")
    for i, start_hms_str_line in enumerate(start_times_hms_list):
        start_hms = start_hms_str_line.strip()
        if not start_hms: continue

        try:
            start_sec_float = hms_to_seconds(start_hms) # Conversion might throw ValueError
            formatted_start_time_for_ffmpeg = seconds_to_hms(start_sec_float) # Ensure HH:MM:SS.mmm format
            safe_time_str_for_filename = formatted_start_time_for_ffmpeg.replace(':', '').replace('.', '')

            # Use the input video's extension for the output clip
            output_clip_name = f"{video_name_no_ext}_{safe_time_str_for_filename}_clip_{i+1}{input_video_extension}"
            output_clip_path = os.path.join(output_folder, output_clip_name)

            if os.path.exists(output_clip_path):
                logger.info(f"片段 {output_clip_path} 已存在，跳过。")
                continue

            # Modified ffmpeg command
            command = [
                'ffmpeg',
                '-ss', formatted_start_time_for_ffmpeg, # Seek to start time
                '-i', input_video_path,                 # Input file
                '-t', str(clip_duration),               # Duration of the clip
                '-codec', 'copy',                       # Copy video and audio codecs (same format)
                # '-avoid_negative_ts', 'make_zero',    # May be useful if timestamps are problematic with copy
                '-y',                                   # Overwrite output file if it exists
                output_clip_path
            ]
            # Removed: '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac', '-strict', '-2'

            logger.info(f"执行剪辑命令: {' '.join(command)}") # Log command for debugging
            process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
            # FFmpeg often outputs info to stderr, so logging both stdout and stderr can be useful
            if process.stdout:
                logger.info(f"FFmpeg STDOUT for {output_clip_name}:\n{process.stdout.strip()}")
            if process.stderr:
                logger.info(f"FFmpeg STDERR for {output_clip_name}:\n{process.stderr.strip()}")
            logger.info(f"成功剪辑并保存: {output_clip_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"剪辑视频时出错 (片段起始: {start_hms}): {e}")
            logger.error(f"命令: {' '.join(e.cmd)}")
            if e.stderr: logger.error(f"FFmpeg错误输出: {e.stderr}")
        except ValueError as e: # Catch errors from hms_to_seconds or seconds_to_hms
            logger.error(f"处理时间戳 {start_hms} 转换错误: {e}")
        except Exception as e: # Catch any other unforeseen errors during loop
            logger.error(f"处理片段 {i+1} (起始: {start_hms}) 时发生未知错误: {e}")

def _process_merged_clip_group(
    group_info_list, # List of dicts: {'time_sec': ..., 'original_hms': ..., 'original_line_num': ...}
    input_video_path,
    video_name_no_ext,
    input_video_extension,
    output_folder,
    base_clip_duration # This is the `clip_duration` parameter from the main function
):
    """
    Processes a group of timestamps to create a single merged video clip.
    Returns True if a clip was successfully created, False otherwise.
    """
    if not group_info_list:
        return False

    group_start_time_sec = group_info_list[0]['time_sec']
    # The effective end time of the merged clip is the start time of the *last* # timestamp in the group PLUS the base_clip_duration.
    group_effective_end_time_sec = group_info_list[-1]['time_sec'] + base_clip_duration
    
    merged_duration_sec = group_effective_end_time_sec - group_start_time_sec

    # Use a small epsilon for duration check to avoid issues with floating point arithmetic
    if merged_duration_sec <= 0.001: 
        original_indices = [str(info['original_line_num']) for info in group_info_list]
        logger.info(f"警告: 计算出的合并片段时长过短或为零/负数 ({merged_duration_sec:.3f}s)。"
                      f"起始: {seconds_to_hms(group_start_time_sec)}, "
                      f"原始行号: {', '.join(original_indices)}. 跳过此组。")
        return False

    formatted_start_time_for_ffmpeg = seconds_to_hms(group_start_time_sec)
    safe_time_str_for_filename = formatted_start_time_for_ffmpeg.replace(':', '').replace('.', '')

    # Create filename part from original line numbers (indices)
    indices_str_parts = [str(info['original_line_num']) for info in group_info_list]
    indices_filename_part = "_".join(indices_str_parts)
    
    output_clip_name = f"{video_name_no_ext}_{safe_time_str_for_filename}_clip_{indices_filename_part}{input_video_extension}"
    output_clip_path = os.path.join(output_folder, output_clip_name)

    if os.path.exists(output_clip_path):
        logger.info(f"片段 {output_clip_path} 已存在，跳过。")
        return False # Clip already exists, not processed in this run

    # FFmpeg command using 'copy' codec to preserve quality and ensure speed
    command = [
        'ffmpeg',
        '-ss', formatted_start_time_for_ffmpeg, # Seek to start time
        '-i', input_video_path,                 # Input file
        '-t', str(merged_duration_sec),         # Duration of the clip
        '-codec', 'copy',                       # Copy video and audio codecs
        # '-avoid_negative_ts', 'make_zero',    # Consider if timestamp issues arise with 'copy'
        '-y',                                   # Overwrite output file (though we check existence above)
        output_clip_path
    ]

    try:
        logger.info(f"执行合并剪辑命令: {' '.join(command)}")
        # Use errors='replace' for text output from subprocess
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        # FFmpeg often outputs informational messages to stderr.
        # Log stderr if it contains anything significant.
        if process.stderr and process.stderr.strip():
             logger.info(f"FFmpeg STDERR for {output_clip_name}:\n{process.stderr.strip()}")
        # If stderr is empty but stdout has content, log stdout.
        elif process.stdout and process.stdout.strip():
             logger.info(f"FFmpeg STDOUT for {output_clip_name}:\n{process.stdout.strip()}")

        logger.info(f"成功合并剪辑并保存: {output_clip_path}")
        return True # Clip processed successfully
    except subprocess.CalledProcessError as e:
        logger.error(f"合并剪辑视频时出错 (片段组起始: {formatted_start_time_for_ffmpeg}, 原始行号: {', '.join(indices_str_parts)}): {e}")
        logger.error(f"命令: {' '.join(e.cmd)}")
        if e.stdout and e.stdout.strip(): logger.info(f"FFmpeg STDOUT: {e.stdout.strip()}")
        if e.stderr and e.stderr.strip(): logger.info(f"FFmpeg STDERR: {e.stderr.strip()}")
    except Exception as e: # Catch any other unforeseen errors
        logger.error(f"处理片段组 {', '.join(indices_str_parts)} (起始: {formatted_start_time_for_ffmpeg}) 时发生未知错误: {e}")
    
    return False # Failed to process this group

def clip_video_ffmpeg_merged(input_video_path, shooting_times_file, output_folder, clip_duration=0.8):
    if not os.path.exists(input_video_path):
        logger.info(f"错误: 输入视频文件未找到 {input_video_path}")
        return
    if not os.path.exists(shooting_times_file):
        # Message from original: "错误: shooting_bow.txt 文件未找到 {shooting_times_file}"
        # Using the variable name for consistency in the message:
        logger.info(f"错误: 时间戳文件未找到 {shooting_times_file}")
        return
    if os.path.getsize(shooting_times_file) == 0:
        logger.info(f"提示: {shooting_times_file} 为空，没有片段可剪辑。")
        return

    os.makedirs(output_folder, exist_ok=True)
    video_name_no_ext = os.path.splitext(os.path.basename(input_video_path))[0]
    input_video_extension = os.path.splitext(input_video_path)[1]
    if not input_video_extension: # Fallback if no extension
        logger.info(f"警告: 输入视频 {input_video_path} 没有文件扩展名。默认使用 .mp4 输出。")
        input_video_extension = ".mp4"

    # Read and parse timestamps
    valid_timestamps_with_indices = []
    try:
        with open(shooting_times_file, 'r', encoding='utf-8') as f:
            raw_lines = f.readlines()
        
        for original_line_idx, line_content in enumerate(raw_lines):
            start_hms = line_content.strip()
            if not start_hms: # Skip empty or whitespace-only lines
                continue
            try:
                start_sec = hms_to_seconds(start_hms)
                valid_timestamps_with_indices.append({
                    'time_sec': start_sec,
                    'original_hms': start_hms,
                    'original_line_num': original_line_idx + 1 # 1-based line number
                })
            except ValueError as e: # Catch errors from hms_to_seconds
                logger.error(f"警告: 解析时间戳 '{start_hms}' (原始行 {original_line_idx + 1}) 错误: {e}。跳过此行。")
                continue
    except Exception as e:
        logger.error(f"读取或解析时间戳文件 {shooting_times_file} 时出错: {e}")
        return
    
    if not valid_timestamps_with_indices:
        logger.info(f"在 {shooting_times_file} 中没有找到有效的射击时刻进行处理 (所有行均为空、格式错误或转换失败)。")
        return
    
    logger.info(f"开始处理视频: {input_video_path}")
    logger.info(f"共找到 {len(valid_timestamps_with_indices)} 个有效标记点。片段基础时长: {clip_duration}s。")
    logger.info(f"尝试合并时间差小于等于 {clip_duration}s 的连续片段，并保持原视频格式。")

    processed_groups_count = 0
    current_group_infos = [] # Stores dicts for the current group being formed

    for i in range(len(valid_timestamps_with_indices)):
        current_ts_info = valid_timestamps_with_indices[i]

        if not current_group_infos:
            # This is the first timestamp for a new potential group
            current_group_infos.append(current_ts_info)
        else:
            # A group is already started. Compare current_ts_info with the *previous timestamp in the file list*.
            # previous_ts_in_file is valid_timestamps_with_indices[i-1]
            # This is safe because if current_group_infos is not empty, it implies i > 0.
            previous_ts_in_file = valid_timestamps_with_indices[i-1] 
            
            time_diff_with_prev_in_file = current_ts_info['time_sec'] - previous_ts_in_file['time_sec']

            if time_diff_with_prev_in_file <= clip_duration and time_diff_with_prev_in_file >= 0: # also ensure time moves forward
                # Merge: Add current timestamp to the ongoing group
                current_group_infos.append(current_ts_info)
            else:
                # Time difference is too large, or time moved backward (anomalous data).
                # End of current group: Process it.
                if time_diff_with_prev_in_file < 0:
                     logger.info(f"警告: 时间戳顺序错乱或重复。当前时间 {current_ts_info['original_hms']} (行 {current_ts_info['original_line_num']}) "
                                   f"早于或等于前一时间 {previous_ts_in_file['original_hms']} (行 {previous_ts_in_file['original_line_num']})。"
                                   f"将结束当前片段组并开始新组。")

                if _process_merged_clip_group(
                    current_group_infos, input_video_path, video_name_no_ext,
                    input_video_extension, output_folder, clip_duration
                ):
                    processed_groups_count += 1
                
                # Start a new group with the current timestamp
                current_group_infos = [current_ts_info]
    
    # After the loop, process any remaining group in current_group_infos
    if current_group_infos:
        if _process_merged_clip_group(
            current_group_infos, input_video_path, video_name_no_ext,
            input_video_extension, output_folder, clip_duration
        ):
            processed_groups_count += 1

    if processed_groups_count == 0:
        logger.info(f"在 {shooting_times_file} 中没有符合条件的片段可剪辑，或者所有符合条件的片段已存在于输出文件夹。")
    else:
        logger.info(f"视频剪辑完成。共生成 {processed_groups_count} 个（合并后）片段。")

def clip_video_ffmpeg_with_duration(input_video_path, shooting_times_file, output_folder):
    if not os.path.exists(input_video_path):
        logger.error(f"错误: 输入视频文件未找到 {input_video_path}")
        return
    if not os.path.exists(shooting_times_file):
        logger.error(f"错误: 时间戳文件未找到 {shooting_times_file}")
        return
    if os.path.getsize(shooting_times_file) == 0:
        logger.info(f"提示: {shooting_times_file} 为空，没有片段可剪辑。")
        return

    os.makedirs(output_folder, exist_ok=True)
    video_name_no_ext = os.path.splitext(os.path.basename(input_video_path))[0]
    input_video_extension = os.path.splitext(input_video_path)[1]
    if not input_video_extension:
        logger.warning(f"警告: 输入视频 {input_video_path} 没有文件扩展名。默认使用 .mp4 输出。")
        input_video_extension = ".mp4"

    try:
        with open(shooting_times_file, 'r', encoding='utf-8') as f:
            time_range_lines = f.readlines()
    except Exception as e:
        logger.error(f"读取时间戳文件 {shooting_times_file} 时出错: {e}")
        return

    if not time_range_lines:
        logger.info(f"没有在 {shooting_times_file} 中找到射击时刻范围。")
        return

    logger.info(f"开始剪辑视频: {input_video_path}, 共 {len(time_range_lines)} 个片段候选, 尝试保持原格式")
    
    successful_clips = 0
    failed_clips = 0

    for i, line in enumerate(time_range_lines):
        line_content = line.strip()
        if not line_content:
            # logger.debug(f"Skipping empty line {i+1} in {shooting_times_file}")
            continue

        try:
            parts = line_content.split(' - ')
            if len(parts) != 2:
                logger.error(f"时间戳格式错误 (行 {i+1}: '{line_content}'). 需要 'HH:MM:SS.mmm - HH:MM:SS.mmm' 格式。跳过此行。")
                failed_clips += 1
                continue
            
            start_hms_str, end_hms_str = parts[0].strip(), parts[1].strip()

            # Validate format before conversion (basic check)
            if not (len(start_hms_str.split(':')) == 3 and '.' in start_hms_str.split(':')[2] and \
                    len(end_hms_str.split(':')) == 3 and '.' in end_hms_str.split(':')[2]):
                logger.error(f"时间戳详细格式错误 (行 {i+1}: '{line_content}'). 确保时间为 HH:MM:SS.mmm。跳过此行。")
                failed_clips += 1
                continue

            start_sec_float = hms_to_seconds(start_hms_str)
            end_sec_float = hms_to_seconds(end_hms_str)

            if start_sec_float > end_sec_float:
                logger.error(f"错误: 结束时间 {end_hms_str} (在 {end_sec_float:.3f}s) 在开始时间 {start_hms_str} (在 {start_sec_float:.3f}s) 之前 (行 {i+1})。跳过此片段。")
                failed_clips += 1
                continue
            
            # Calculate duration, ensuring it's not negative due to precision.
            clip_duration_seconds = max(0.0, end_sec_float - start_sec_float)

            formatted_start_time_for_ffmpeg = seconds_to_hms(start_sec_float) # HH:MM:SS.mmm
            # Create a filename-safe version of the start time
            safe_time_str_for_filename = formatted_start_time_for_ffmpeg.replace(':', '').replace('.', '').replace('-', '')


            output_clip_name = f"{video_name_no_ext}_{safe_time_str_for_filename}_infinite_clip_{i+1}{input_video_extension}"
            output_clip_path = os.path.join(output_folder, output_clip_name)

            if os.path.exists(output_clip_path):
                logger.info(f"片段 {output_clip_path} 已存在，跳过。")
                continue

            command = [
                'ffmpeg',
                '-ss', formatted_start_time_for_ffmpeg,   # Seek to start time (input seeking)
                '-i', input_video_path,                   # Input file
                '-t', str(clip_duration_seconds),         # Duration of the clip
                '-codec', 'copy',                         # Copy video and audio codecs (same format)
                # '-avoid_negative_ts', 'make_zero',      # May be useful if timestamps are problematic
                '-y',                                     # Overwrite output file if it exists
                output_clip_path
            ]
            
            if clip_duration_seconds == 0:
                 logger.warning(f"注意: 片段 {i+1} (起始: {start_hms_str}, 结束: {end_hms_str}) 计算时长为0。FFmpeg 将尝试剪辑。")

            logger.info(f"执行剪辑命令 (片段 {i+1}/{len(time_range_lines)}): {' '.join(command)}")
            # Using check=False to manually inspect returncode and stderr/stdout
            process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=False)

            if process.returncode == 0:
                # Even with returncode 0, FFmpeg might have warnings in stderr.
                # Log stderr as info or debug if it's not empty.
                logger.info(f"成功剪辑并保存: {output_clip_path}")
                if process.stdout and process.stdout.strip():
                    logger.debug(f"FFmpeg STDOUT for {output_clip_name}:\n{process.stdout.strip()}")
                if process.stderr and process.stderr.strip():
                    # FFmpeg often puts informational messages in stderr
                    logger.debug(f"FFmpeg STDERR for {output_clip_name} (Info/Warnings):\n{process.stderr.strip()}")
                successful_clips += 1
            else:
                logger.error(f"剪辑视频时出错 (片段 {i+1}, 起始: {start_hms_str}, 时长: {clip_duration_seconds:.3f}s)。FFmpeg 返回码: {process.returncode}")
                logger.error(f"命令: {' '.join(command)}")
                if process.stdout and process.stdout.strip(): 
                    logger.error(f"FFmpeg STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip(): 
                    logger.error(f"FFmpeg STDERR: {process.stderr.strip()}")
                failed_clips += 1

        except ValueError as e: 
            logger.error(f"处理时间戳 (行 {i+1}: '{line_content}') 转换错误: {e}。跳过此片段。")
            failed_clips += 1
        except Exception as e: 
            logger.error(f"处理片段 {i+1} (行: '{line_content}') 时发生未知错误: {e}")
            failed_clips += 1
            
    logger.info(f"剪辑处理完成。成功剪辑 {successful_clips} 个片段，失败 {failed_clips} 个片段。")

def process_and_merge_times(shooting_times_file, infinite_file2):

    lista = []
    list_b_internal = []

    # 1. Process shooting_times_file
    if not os.path.exists(shooting_times_file):
        logger.warning(f"File not found: {shooting_times_file}. 'shootingfile' will be empty.")
    else:
        try:
            with open(shooting_times_file, 'r', encoding='utf-8') as f:
                logger.info(f"Processing file: {shooting_times_file}")
                for line_num, line_content in enumerate(f, 1):
                    line_content = line_content.strip()
                    if not line_content:
                        continue
                    
                    # Split by " - " to handle "T1" or "T1 - T2"
                    parts_from_line = [p.strip() for p in line_content.split(' - ')]
                    
                    timestamps_to_add_from_line = []
                    if len(parts_from_line) == 1:
                        timestamps_to_add_from_line.append(parts_from_line[0])
                    elif len(parts_from_line) == 2:
                        timestamps_to_add_from_line.append(parts_from_line[0])
                        timestamps_to_add_from_line.append(parts_from_line[1])
                    else:
                        logger.warning(f"Line {line_num} in {shooting_times_file} ('{line_content}') has an unexpected structure (more than one ' - ' separator). Skipping.")
                        continue

                    for ts_str in timestamps_to_add_from_line:
                        try:
                            hms_to_seconds(ts_str) # Validate format by attempting conversion
                            lista.append(ts_str)
                        except ValueError as e:
                            logger.warning(f"Invalid timestamp format for '{ts_str}' from line {line_num} in {shooting_times_file}: {e}. Skipping this timestamp.")
        except Exception as e:
            logger.error(f"Error reading {shooting_times_file}: {e}")

    # 2. Process infinite_file2
    if not os.path.exists(infinite_file2):
        logger.warning(f"File not found: {infinite_file2}. No new times will be generated from it.")
    else:
        try:
            with open(infinite_file2, 'r', encoding='utf-8') as f:
                logger.info(f"Processing file: {infinite_file2}")
                for line_num, line_content in enumerate(f, 1):
                    line_content = line_content.strip()
                    if not line_content:
                        continue

                    main_parts = line_content.split(' - ', 1) # Split only on the first " - "
                    if len(main_parts) != 2:
                        logger.warning(f"Line {line_num} in {infinite_file2} ('{line_content}') does not contain 'BASE_TIME - OFFSETS' structure. Skipping.")
                        continue
                    
                    base_time_str = main_parts[0].strip()
                    offset_times_block = main_parts[1].strip()
                    individual_offset_strs = offset_times_block.split() # Split by space

                    try:
                        base_seconds = hms_to_seconds(base_time_str)
                    except ValueError as e:
                        logger.warning(f"Invalid base time format '{base_time_str}' on line {line_num} in {infinite_file2}: {e}. Skipping line.")
                        continue

                    for offset_str in individual_offset_strs:
                        try:
                            offset_seconds = hmsff_to_seconds(offset_str)
                            total_seconds = base_seconds + offset_seconds
                            new_hms_time = seconds_to_hms(total_seconds)
                            list_b_internal.append(new_hms_time)
                        except ValueError as e:
                            logger.warning(f"Invalid offset time ('{offset_str}', base: '{base_time_str}') on line {line_num} in {infinite_file2}: {e}. Skipping this offset.")
        except Exception as e:
            logger.error(f"Error reading {infinite_file2}: {e}")

    # 3. Merge, Deduplicate, and Sort
    combined_list = lista + list_b_internal
    
    if not combined_list:
        logger.info("No time data collected from any file. Output file will not be created/modified.")
        return

    # Deduplicate by converting to a set and back to a list, then sort.
    unique_sorted_times = sorted(list(set(combined_list)))

    # 4. Write to output file
    output_dir = os.path.dirname(shooting_times_file)
    if not output_dir and shooting_times_file: # If shooting_times_file is a relative path like "file.txt"
        output_dir = "." 
    elif not shooting_times_file: # Should not happen if file existence is checked, but as a fallback
        output_dir = "."
        logger.warning("shooting_times_file path was empty or invalid; outputting 'shooting_bow_sum.txt' to current directory.")


    output_filename = "shooting_bow_sum.txt"
    output_path = os.path.join(output_dir, output_filename)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for time_str in unique_sorted_times:
                f.write(time_str + "\n")
        logger.info(f"Successfully processed files. Wrote {len(unique_sorted_times)} unique sorted time strings to {output_path}")
    except Exception as e:
        logger.error(f"Error writing to output file {output_path}: {e}")

def _generate_merged_clip_ffmpeg_command(
    input_video_path, 
    group_start_time_sec, 
    merged_duration_sec, 
    output_clip_path
):
    """Helper function to create and run the ffmpeg command for a merged clip."""
    formatted_start_time_for_ffmpeg = seconds_to_hms(group_start_time_sec)
    command = [
        'ffmpeg',
        '-ss', formatted_start_time_for_ffmpeg,
        '-i', input_video_path,
        '-t', str(merged_duration_sec),
        '-codec', 'copy',
        '-y',
        output_clip_path
    ]
    try:
        logger.info(f"Executing merged clip command: {' '.join(command)}")
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if process.stderr and process.stderr.strip():
            logger.info(f"FFmpeg STDERR for {os.path.basename(output_clip_path)}:\n{process.stderr.strip()}")
        elif process.stdout and process.stdout.strip(): # Log stdout if stderr is empty
            logger.info(f"FFmpeg STDOUT for {os.path.basename(output_clip_path)}:\n{process.stdout.strip()}")
        logger.info(f"Successfully merged and saved: {output_clip_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error merging clip (start: {formatted_start_time_for_ffmpeg}, duration: {merged_duration_sec}s): {e}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        if e.stdout and e.stdout.strip(): logger.error(f"FFmpeg STDOUT: {e.stdout.strip()}")
        if e.stderr and e.stderr.strip(): logger.error(f"FFmpeg STDERR: {e.stderr.strip()}")
    except Exception as e:
        logger.error(f"Unknown error processing merged clip (start: {formatted_start_time_for_ffmpeg}): {e}")
    return False

def generate_clips_from_multiple_weapon_times_merge(input_video_path, weapon_time_sources, output_folder, clip_duration=0.8, merge_threshold_factor=1.0):
    """
    Generates clips from multiple weapon timestamp files, merging close timestamps
    chronologically with a global clip index for merged groups.

    Args:
        input_video_path (str): Path to the input video.
        weapon_time_sources (list): A list of dictionaries, where each dict is
                                    {'file_path': str, 'weapon_name': str}.
        output_folder (str): Folder to save the clips.
        clip_duration (float): Base duration of each individual clip event in seconds.
                               Timestamps will be merged if the current one starts
                               within 'clip_duration * merge_threshold_factor' seconds
                               after the *previous one started*.
        merge_threshold_factor (float): Multiplier for clip_duration to determine merge window.
                                        Default 1.0 means timestamps are merged if the next starts
                                        before the previous one would have ended.
    """
    if not os.path.exists(input_video_path):
        logger.error(f"错误: 输入视频文件未找到 {input_video_path}")
        return

    all_timestamps_info = [] # Will store dicts: {'time_sec': float, 'weapon_name': str, 'original_hms': str}
    
    for source_info in weapon_time_sources:
        file_path = source_info['file_path']
        weapon_name = source_info['weapon_name']
        
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            logger.info(f"时间文件 {os.path.basename(file_path)} (武器: {weapon_name}) 不存在或为空，跳过。")
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                logger.info(f"读取时间文件: {file_path} (武器: {weapon_name})")
                for line_num, line_content in enumerate(f, 1):
                    start_hms = line_content.strip()
                    if not start_hms:
                        continue
                    try:
                        start_sec = hms_to_seconds(start_hms)
                        all_timestamps_info.append({
                            'time_sec': start_sec,
                            'weapon_name': weapon_name,
                            'original_hms': start_hms 
                        })
                    except ValueError as e:
                        logger.warning(f"解析时间戳 '{start_hms}' 错误 (来自 {os.path.basename(file_path)}, 行 {line_num}, 武器: {weapon_name}): {e}。跳过此时间戳。")
        except Exception as e:
            logger.error(f"读取时间文件 {file_path} (武器: {weapon_name}) 时出错: {e}")

    if not all_timestamps_info:
        logger.info(f"没有从提供的源文件中收集到有效的时间戳进行剪辑。视频: {os.path.basename(input_video_path)}")
        return

    all_timestamps_info.sort(key=lambda x: x['time_sec'])
    
    os.makedirs(output_folder, exist_ok=True)
    video_name_no_ext = os.path.splitext(os.path.basename(input_video_path))[0]
    input_video_extension = os.path.splitext(input_video_path)[1]
    if not input_video_extension: 
        logger.warning(f"警告: 输入视频 {input_video_path} 没有文件扩展名。默认使用 .mp4 输出。")
        input_video_extension = ".mp4"

    effective_merge_threshold = clip_duration * merge_threshold_factor
    logger.info(f"开始合并剪辑视频: {os.path.basename(input_video_path)}, "
                  f"共 {len(all_timestamps_info)} 个原始时间点 (来自所有选定武器, 已排序). "
                  f"基础片段时长: {clip_duration}s. 合并时间阈值 (从上个片段开始算): {effective_merge_threshold}s.")
    
    clips_created_count = 0
    merged_group_global_idx = 0 # Global index for the output merged clips
    
    i = 0
    while i < len(all_timestamps_info):
        current_group_timestamps_info = [all_timestamps_info[i]] # Start a new group with the current timestamp
        group_start_time_sec = all_timestamps_info[i]['time_sec']
        
        # Look ahead to merge subsequent timestamps
        j = i + 1
        while j < len(all_timestamps_info):
            next_ts_info = all_timestamps_info[j]
            # Merge if the next timestamp starts within `effective_merge_threshold` 
            # SECONDS AFTER THE *PREVIOUS TIMESTAMP IN THE FILE LIST* started.
            # Or, more simply, if next_ts_info['time_sec'] is close to current_group_timestamps_info[-1]['time_sec']
            
            # The condition for merging is:
            # The start time of the 'next_ts_info' must be BEFORE
            # the start time of the *last timestamp currently in the group* PLUS clip_duration.
            # time_diff_with_last_in_group_start = next_ts_info['time_sec'] - current_group_timestamps_info[-1]['time_sec']

            # Merge if the next timestamp starts before the "effective end" of the previous event in the group.
            # Effective end of previous event = current_group_timestamps_info[-1]['time_sec'] + clip_duration
            if next_ts_info['time_sec'] < (current_group_timestamps_info[-1]['time_sec'] + clip_duration) and \
               next_ts_info['time_sec'] >= current_group_timestamps_info[-1]['time_sec']: # Must be after or at same time
                current_group_timestamps_info.append(next_ts_info)
                j += 1
            else:
                break # End of current merge group
        
        # Process the collected group
        merged_group_global_idx += 1 # Increment for each group processed (even if it's a single event)
        
        # Determine the actual duration of this merged clip
        # It starts at the first timestamp in the group.
        # It ends `clip_duration` seconds AFTER the LAST timestamp in the group started.
        merged_clip_actual_end_time_sec = current_group_timestamps_info[-1]['time_sec'] + clip_duration
        merged_clip_actual_duration_sec = merged_clip_actual_end_time_sec - group_start_time_sec

        if merged_clip_actual_duration_sec <= 0.001:
            original_hms_list = [ts['original_hms'] for ts in current_group_timestamps_info]
            logger.warning(f"计算出的合并片段时长过短或为零/负数 ({merged_clip_actual_duration_sec:.3f}s) for group starting {seconds_to_hms(group_start_time_sec)} "
                           f"(Orig HMS: {', '.join(original_hms_list)}). 跳过此组。")
            i = j # Move to the start of the next potential group
            continue

        # Create filename
        formatted_start_time_for_ffmpeg = seconds_to_hms(group_start_time_sec)
        safe_time_str_for_filename = formatted_start_time_for_ffmpeg.replace(':', '').replace('.', '')
        
        # Collect weapon names for the filename, abbreviate, ensure uniqueness
        weapon_names_in_group = sorted(list(set([ts['weapon_name'][:3].lower() for ts in current_group_timestamps_info]))) # first 3 chars, lowercase, unique
        weapons_str_part = "_".join(weapon_names_in_group)
        if not weapons_str_part: weapons_str_part = "multiw" # Fallback

        output_clip_name = f"{video_name_no_ext}_{safe_time_str_for_filename}_mclip_{merged_group_global_idx}_{weapons_str_part}{input_video_extension}"
        output_clip_path = os.path.join(output_folder, output_clip_name)

        if os.path.exists(output_clip_path):
            logger.info(f"合并片段 {output_clip_path} 已存在，跳过。")
        elif _generate_merged_clip_ffmpeg_command(
            input_video_path, 
            group_start_time_sec, 
            merged_clip_actual_duration_sec, 
            output_clip_path
        ):
            clips_created_count += 1
            
        i = j # Move to the start of the next potential group

    if clips_created_count > 0:
        logger.info(f"合并剪辑完成。共创建 {clips_created_count} 个新片段。")
    elif all_timestamps_info :
        logger.info(f"未创建新片段 (可能所有目标片段已存在或在处理过程中发生错误)。")
    # No specific message if all_timestamps_info was empty, already logged above.