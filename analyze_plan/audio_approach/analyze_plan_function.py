import subprocess
import os
from urllib.parse import urlparse
import librosa
import numpy as np
from scipy.signal import correlate, find_peaks

def download_twitch(video_url, outputfile, start_time=None, end_time=None, stream='bestvideo+bestaudio/best'):#默认下载最佳视频和音频
    parsed_url = urlparse(video_url)
    video_code = parsed_url.path.split('/')[-1]
    # 命名
    if start_time and end_time:
        output_path = os.path.join(
            outputfile,
            f"{video_code}_{start_time.replace(':', '')}_{end_time.replace(':', '')}.%(ext)s"
        )
    else:
        output_path = os.path.join(
            outputfile,
            f"{video_code}.%(ext)s"
        )
    part_file = output_path + ".part"
    # 找到output_path最后一个.的位置取之前的字符串
    noext = output_path[:output_path.rfind('.')]+".mp4"
    # 判断是否已经下载
    if os.path.exists(noext):
        print(f"{noext} 已存在，跳过下载。")
        return
    # # 判断 start_time.replace(':', '') 是否出现在文件名中
    # for file in os.listdir(outputfile):
    #     if start_time.replace(':', '') in file:
    #         print(f"{file} 起始位置已存在，跳过下载。")
    #         return
    # command.append('--force-overwrites')  # 覆盖已有文件，如果part损坏

    command = [
        'yt-dlp', video_url,   # 调用 yt-dlp
        '-f', stream,    # 指定只下载 xxx 格式
        '-o', output_path,     # 输出文件名
    ]

    if start_time and end_time:
        command += ['--download-sections', f"*{start_time}-{end_time}"]
    # 检查是否已有部分下载
    if os.path.exists(part_file):
        print(f"检测到未完成的文件 '{part_file}'，将尝试续传。")
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print(result.stdout)  # 输出 yt-dlp 的日志信息
        print(f"下载成功： {output_path}\n --------------------\n ")
    except subprocess.CalledProcessError as e:
        print(f"下载出错: {e}")
        print(e.stderr)  # 输出错误信息
    except FileNotFoundError:
        print("错误：未找到 yt-dlp，请确保已安装并配置环境变量")

# 转换6h44m10s   --->   "05:44:10"
def convert_timestr(ss):
    h = ss.split('h')[0]
    m = ss.split('h')[1].split('m')[0]
    s = ss.split('m')[1].split('s')[0]
    ms = ss.split('s')[1].split('x')[0]
    return f"{h.zfill(2)}:{m.zfill(2)}:{s.zfill(2)}.{ms.zfill(3)}"

def seconds_to_hms(seconds):
    hours = int(seconds // 3600)  # 计算小时数
    minutes = int((seconds % 3600) // 60)  # 计算分钟数
    secs = seconds % 60  # 计算秒数（包括小数部分）
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"  # 格式化为 HH:MM:SS.sss

def hms_to_seconds(time_str):
    hours, minutes, seconds = time_str.split(':')
    seconds1, milliseconds = seconds.split('.')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds1) + int(milliseconds) / 1000
    return total_seconds

def find_impact_segments(twitch_url, audio_path, template_folder, output_folder,
                         audio_clip_original_starttime_seconds=0.0,
                         x=0.65, dis=10.0, pro=0.1,
                         segment_duration_seconds=180.0,
                         overlap_seconds=10.0):
    video_id = twitch_url.split('/')[-1]
    # print(f"提取的视频 ID: {video_id}") # 已在 main.py 中打印

    save_directory = os.path.join(output_folder, video_id)
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
        print(f"创建保存目录: {save_directory}")

    try:
        y, sr = librosa.load(audio_path, sr=None)
        if y is None or len(y) == 0:
            print(f"错误: 加载的音频文件 {audio_path} 为空。跳过处理。")
            return []
        print(f"加载音频文件: {audio_path}, 采样率: {sr}, 时长: {len(y)/sr:.2f} 秒")
        # print(f"此音频片段在原视频中的绝对开始时间（秒）: {audio_clip_original_starttime_seconds}") # 已在 main.py 中打印
    except Exception as e:
        print(f"错误: 无法加载音频文件 {audio_path}: {e}")
        return []

    if sr is None or sr == 0:
        print(f"错误: 音频文件 {audio_path} 的采样率为零或None。跳过处理。")
        return []

    template_files = [f for f in os.listdir(template_folder) if f.endswith(('.mp3', '.wav', '.m4a', '.aac', '.ogg'))]
    print(f"在 {template_folder} 中找到 {len(template_files)} 个模板文件: {template_files}")

    detected_times_in_original_video = []
    timestamps_filepath = os.path.join(save_directory, 'timestamps.txt')

    segment_length_samples = int(segment_duration_seconds * sr)
    overlap_samples = int(overlap_seconds * sr)
    step_samples = segment_length_samples - overlap_samples

    if segment_length_samples <= 0:
        print(f"错误：计算得到的 segment_length_samples ({segment_length_samples}) 无效。")
        return []
    if step_samples <= 0 :
        print(f"警告：分段的步长 ({step_samples} 样本) 小于或等于零。这意味着重叠 ({overlap_seconds}s) 可能过大或分段时长 ({segment_duration_seconds}s) 过小。将调整为非重叠处理。")
        step_samples = segment_length_samples
        overlap_samples = 0

    with open(timestamps_filepath, 'w', encoding='utf-8') as f_timestamps:
        for template_file in template_files:
            template_normalized = None # 初始化
            try:
                template_path = os.path.join(template_folder, template_file)
                template, sr_template = librosa.load(template_path, sr=None)

                if template is None or len(template) == 0:
                    print(f"警告: 模板 {template_file} 为空或加载失败。跳过此模板。")
                    continue
                print(f"\n加载模板文件: {template_path}, 采样率: {sr_template}, 时长: {len(template)/sr_template:.2f} 秒")

                if sr_template != sr:
                    print(f"模板采样率 {sr_template} 与目标音频采样率 {sr} 不匹配。正在重采样模板...")
                    template = librosa.resample(template, orig_sr=sr_template, target_sr=sr)
                    print(f"模板已重采样到目标采样率: {sr}")

                if len(template) == 0:
                    print(f"警告: 重采样后的模板 {template_file} 为空。跳过此模板。")
                    continue

                # --- 模板归一化 (保留模板归一化) ---
                template_max_abs = np.max(np.abs(template))
                if template_max_abs > 1e-6: # 避免除以非常小的值或零
                    template_normalized = template / template_max_abs
                    print(f"  模板 '{template_file}' 已归一化 (原最大绝对值: {template_max_abs:.4f})")
                else:
                    print(f"警告: 模板 '{template_file}' 最大绝对值过小 ({template_max_abs:.4f})，可能为空白或接近空白。跳过归一化，并按原样使用。")
                    template_normalized = template # 如果模板是静音或接近静音，保持原样

            except Exception as e:
                print(f"错误: 加载、重采样或归一化模板 {template_path} 失败: {e}")
                continue

            # --- 使用归一化后的模板计算能量和阈值 (这部分逻辑不变) ---
            current_template_energy = np.sum(template_normalized**2)
            if current_template_energy < 1e-6: # 检查能量是否过小
                print(f"警告: 归一化后的模板 '{template_file}' 能量 ({current_template_energy:.4f}) 过低。跳过此模板。")
                continue

            print(f"  模板: {template_file}, 归一化后能量: {current_template_energy:.4f}")
            threshold = x * current_template_energy # X 仍然是作用于归一化模板能量
            print(f"  基于 X={x}, 计算得到的 height 阈值 (基于归一化能量): {threshold:.4f}")

            current_segment_start_sample = 0
            segment_count = 0
            while current_segment_start_sample < len(y):
                segment_count += 1
                segment_start_time_in_clip = current_segment_start_sample / sr
                current_segment_end_sample = min(current_segment_start_sample + segment_length_samples, len(y))
                segment = y[current_segment_start_sample:current_segment_end_sample] # 这是原始的音频分段

                if len(segment) < len(template_normalized): # 模板仍然是归一化后的模板
                    if segment_count == 1 and current_segment_start_sample == 0 and len(y) < len(template_normalized):
                         print(f"  整个音频片段 ({len(y)/sr:.2f}s) 比模板 ({template_file}, {len(template_normalized)/sr:.2f}s) 短，无法处理。")
                         break
                    current_segment_start_sample += step_samples
                    if step_samples <= 0 : current_segment_start_sample +=1
                    continue

                # --- 【重要改动】不再对音频分段 (segment) 进行归一化 ---
                # segment_normalized = None # 原有代码
                # segment_max_abs = np.max(np.abs(segment)) # 原有代码
                # if segment_max_abs > 1e-6: # 原有代码
                #     segment_normalized = segment / segment_max_abs # 原有代码
                # else: # 原有代码
                #     # print(f"  分段 {segment_count} 最大绝对值过小 ({segment_max_abs:.4f})，可能为空白。跳过归一化，按原样使用。") # 原有代码
                #     segment_normalized = segment # 原有代码

                # --- 使用 原始音频分段(segment) 和 归一化后的模板(template_normalized) 进行互相关 ---
                # 注意：现在是用原始信号强度的 segment 与归一化（峰值为1）的 template_normalized 进行匹配
                corr = correlate(segment, template_normalized, mode='valid') # 【重要改动】使用 segment (原始) 而不是 segment_normalized

                if len(corr) == 0:
                    current_segment_start_sample += step_samples
                    if step_samples <= 0: current_segment_start_sample +=1
                    continue

                distance_samples = int(dis * sr)
                if distance_samples < 1: distance_samples = 1

                peaks_in_segment, properties = find_peaks(corr, height=threshold, distance=distance_samples, prominence=pro)

                if len(peaks_in_segment) > 0:
                    actual_prominences = properties.get('prominences', [])
                    #您可以取消下面这行注释来查看每个分段的详细峰值信息，但日志会非常多
                    print(f"    在分段 {segment_count} 中找到 {len(peaks_in_segment)} 个峰值 (PRO设置值为: {pro})。实际Prominences: {np.array2string(np.array(actual_prominences), formatter={'float_kind':lambda val: '%.2f' % val})}")
                    pass

                times_in_segment = peaks_in_segment / sr
                for t_segment_idx, t_segment_time in enumerate(times_in_segment):
                    t_clip = segment_start_time_in_clip + t_segment_time
                    t_original_video = audio_clip_original_starttime_seconds + t_clip

                    is_duplicate = False
                    for recorded_time in detected_times_in_original_video:
                        if abs(t_original_video - recorded_time) < 0.25: # 去重阈值0.25秒
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        actual_prom = properties['prominences'][t_segment_idx] if 'prominences' in properties and t_segment_idx < len(properties['prominences']) else "N/A"
                        peak_corr_value = corr[peaks_in_segment[t_segment_idx]] # 获取该峰值在corr中的值
                        print(f"      >> 考虑记录时间戳 (原视频): {seconds_to_hms(t_original_video)}, 模板: {template_file}, Corr峰值: {peak_corr_value:.2f}, 峰值Prominence: {actual_prom}, Height阈值: {threshold:.2f}") #
                        f_timestamps.write(f"{seconds_to_hms(t_original_video)}\n")
                        detected_times_in_original_video.append(t_original_video)

                if current_segment_end_sample >= len(y): break
                current_segment_start_sample += step_samples
                if step_samples <= 0:
                    print("错误：step_samples 计算为0或负数，强行终止分段处理以避免无限循环。")
                    break
            # print(f"  模板 {template_file} 处理完毕，当前总检测数: {len(detected_times_in_original_video)}")

    print(f"总共检测到 {len(detected_times_in_original_video)} 个不重复的时间戳 (相对于原视频) 写入到 {timestamps_filepath}")
    if detected_times_in_original_video:
        detected_times_in_original_video.sort()
        with open(timestamps_filepath, 'w', encoding='utf-8') as f_timestamps_sorted:
            for t in detected_times_in_original_video:
                f_timestamps_sorted.write(f"{seconds_to_hms(t)}\n")
        print("时间戳已排序并重新写入文件。")

    return detected_times_in_original_video

def download_impact_segments(twitch_url, detected_times_path, save_directory, length=0.8):
    # 读取时间戳文件
    with open(detected_times_path, 'r', encoding='utf-8') as f:
        detected_times = [hms_to_seconds(line.strip()) for line in f]
    # 根据时间戳下载视频片段
    for i, start_time in enumerate(detected_times):
        end_time = start_time + length
        start_time_str = seconds_to_hms(start_time)
        end_time_str = seconds_to_hms(end_time)
        # 下载片段
        download_twitch(twitch_url, save_directory, start_time_str, end_time_str)

def update_txt(txt_path, problem_folder):
    problem_files = [f for f in os.listdir(problem_folder) if f.endswith(('.mp4'))]
    # 读取txt文件，加入list
    detected_times=[]
    with open(txt_path, 'r', encoding='utf-8') as f:
        detected_times = [line.strip() for line in f]
    # 写新的txt文件

    for file in problem_files:
        start_time = file.split('_')[1]
        h = start_time[:2]
        m = start_time[2:4]
        s = start_time[4:6]
        ms = start_time[7:]
        # print('start_time:',start_time)
        start_time = f"{h.zfill(2)}:{m.zfill(2)}:{s.zfill(2)}.{ms.zfill(3)}"
        # print('start_time:',start_time)
        new_start_time = seconds_to_hms(int(hms_to_seconds(start_time)))
        detected_times = [new_start_time if t == start_time else t for t in detected_times]

    with open(txt_path, 'w', encoding='utf-8') as f: #覆盖了源文件
        for t in detected_times:
            f.write(f"{t}\n")

def redownload_segments(twitch_url, save_directory, txt_path, length=0.8):
    download_impact_segments(twitch_url, txt_path, save_directory, length)
    print("重新下载执行完成！")

def dl_target_audios(urltxt, outputfile):
    with open(urltxt, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:  # 跳过空行
                continue
            try:
                video_url, start_time, end_time = line.split(',')
                print(f"准备下载: URL={video_url}, Start={start_time}, End={end_time}")
                # 调用 download_twitch 下载指定时间段的音频
                # 注意，download_twitch 函数的 stream 参数现在是 'Audio_Only'
                # 并且传递了 start_time 和 end_time
                download_twitch(video_url.strip(), outputfile, start_time=start_time.strip(), end_time=end_time.strip(), stream='Audio_Only')
            except ValueError:
                print(f"警告: 跳过格式错误的行: {line}")
                print("请确保每行格式为: url,starttime,endtime (例如: https://...,00:10:00.000,01:30:00.000)")
            except Exception as e:
                print(f"处理行时发生错误 '{line}': {e}")