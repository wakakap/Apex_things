import subprocess
import os
from urllib.parse import urlparse
import librosa
import numpy as np
from scipy.signal import correlate, find_peaks

def download_twitch(video_url, outputfile, start_time=None, end_time=None, stream='1080p60'):
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

def find_impact_segments(twitch_url, audio_path, template_folder, output_folder, x = 0.65, dis=10, pro=0.1):
    # 从 twitch_url 中提取视频 ID
    video_id = twitch_url.split('/')[-1]
    print(f"提取的视频 ID: {video_id}")

    # 创建保存目录
    save_directory = os.path.join(output_folder, video_id)
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
        print(f"创建保存目录: {save_directory}")
    # else:
        # intemp = input("目录已存在: {save_directory}, go or no?\n")
        # if intemp == 'no':
        #     return
    # 加载音频文件
    y, sr = librosa.load(audio_path, sr=None)
    print(f"加载音频文件: {audio_path}, 采样率: {sr}")
    
    # 获取模板文件列表
    template_files = [f for f in os.listdir(template_folder) if f.endswith(('.mp4'))]
    print(f"在 {template_folder} 中找到 {len(template_files)} 个模板文件: {template_files}")
    
    # 初始化时间戳列表
    segment_length = 100 * sr  # 每段100秒
    template_files = [f for f in os.listdir(template_folder) if f.endswith(('.mp4'))]
    detected_times = []
    
    # 保存时间戳到文件
    with open(os.path.join(save_directory, 'timestamps.txt'), 'w', encoding='utf-8') as f:
        # 分段进行 防止内存爆炸
        for template_file in template_files:
            template_path = os.path.join(template_folder, template_file)
            # 加载模板音频
            template, sr_template = librosa.load(template_path, sr=None)
            print(f"加载模板文件: {template_path}, 采样率: {sr_template}")
            
            # 检查采样率并重采样
            if sr_template != sr:
                template = librosa.resample(template, orig_sr=sr_template, target_sr=sr)
                print(f"模板重采样到目标采样率: {sr}")
            
            # 分段处理
            for start_idx in range(0, len(y), segment_length):
                end_idx = min(start_idx + segment_length, len(y))
                segment = y[start_idx:end_idx]
                segment_time_offset = start_idx / sr  # 段的起始时间

                # 计算互相关
                corr = correlate(segment, template, mode='valid')
                # print(f"完成 {template_file} 的互相关计算，长度: {len(corr)}")
                
                # 计算模板能量和阈值
                template_energy = np.sum(template**2)
                threshold = x * template_energy # 关键参数 数字越大越严格
                # print(f"模板 {template_file} 的能量: {template_energy}, 阈值: {threshold}")
            
                # 寻找峰值
                peaks, _ = find_peaks(corr, height=threshold, distance=dis, prominence=pro)  # 添加 distance=10 如果用变量传，格式会错误。
                # plt.plot(corr)
                # plt.axhline(y=threshold, color='r', linestyle='--')
                # plt.show()
                # print(f"检测到 {len(peaks)} 个峰值")
            
                # 转换为时间戳并去重
                times = peaks / sr + segment_time_offset  # 加上段偏移时间
                unique_times = []
                for t in times:
                    # 只记录与上一个时间戳间隔大于 0.01 秒的时间戳
                    if not unique_times or abs(t - unique_times[-1]) > 0.1:
                        unique_times.append(t)
                        f.write(f"{seconds_to_hms(t)}\n")
                        detected_times.append(t)
                        # print(f"检测到时间戳: {seconds_to_hms(t)}\n")
    
    print(f"总共检测到 {len(detected_times)} 个时间戳")
    return detected_times

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
            download_twitch(line.strip(), outputfile, stream='Audio_Only')




