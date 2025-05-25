import subprocess
import os
from urllib.parse import urlparse
import librosa
import numpy as np
from scipy.signal import correlate, find_peaks

from analyze_plan_function import download_twitch
from analyze_plan_function import seconds_to_hms as sth
from analyze_plan_function import hms_to_seconds as hts
from analyze_plan_function import find_impact_segments
from analyze_plan_function import download_impact_segments
from analyze_plan_function import update_txt
from analyze_plan_function import redownload_segments
from analyze_plan_function import dl_target_audios

# "yt-dlp -F https://www.twitch.tv/videos/2386208922"  # 查看视频流信息
# sb1        mhtml 110x62       0 │                  mhtml │ images      storyboard
# sb0        mhtml 220x124      0 │                  mhtml │ images      storyboard
# Audio_Only mp4   audio only     │ ~790.97MiB  217k m3u8  │ audio only  mp4a.40.2 217k
# 160p       mp4   284x160     30 │ ~  1.04GiB  291k m3u8  │ avc1.4D000C mp4a.40.2
# 360p       mp4   640x360     30 │ ~  2.64GiB  743k m3u8  │ avc1.4D001E mp4a.40.2
# 480p       mp4   852x480     30 │ ~  5.24GiB 1471k m3u8  │ avc1.4D001F mp4a.40.2
# 720p60     mp4   1280x720    60 │ ~ 12.22GiB 3432k m3u8  │ avc1.4D0020 mp4a.40.2
# 1080p60    mp4   1920x1080   60 │ ~ 30.05GiB 8441k m3u8  │ avc1.64002A mp4a.40.2


if __name__ == "__main__":

    X = 0.05 # X 控制了匹配的“严格程度”的第一道关卡：一个音频片段与模板的互相关结果的峰值，至少要达到模板自身能量的 X 倍（在归一化尺度下）。通常在 0.0 到 1.0 之间 具体体现在，Corr峰值大于 Height阈值则那一段被第一次筛选出来
    PRO = 40 # 峰值显著度 (Prominence)衡量了一个峰值相对于其周围信号的“突出”程度。它定义为一个峰值的高度（其值）与其“基线”之间的垂直距离。这个“基线”是通过从该峰值向左和向右水平延伸，直到碰到比该峰值更高的信号点或者到达信号边界来确定的。一个峰值的 prominence 越大，它就越像一个独立的、重要的山峰，而不是一个小山丘上的小颠簸。用于过滤掉那些虽然超过了 height 阈值，但并非真正“显著”的峰 
    # 设置范围：找到那些您认为是正确检测 (True Positives) 的时间点，查看它们的 实际Prominences 值大概在什么范围。找到那些您认为是错误检测 (False Positives) 的时间点，查看它们的 实际Prominences 值又在什么范围。
    # Corr峰值 在该时间点附近找到的互相关函数的峰值大小。
    DISTANCE = 0.3 # 两个被识别为独立的峰值之间所需的最小时间间隔
    Overlap_Seconds = 2.0 
    Segment_Duration_Seconds = 180.0

    ROOT = "E:\\mande\\0_PLAN"
    URLROOT = "https://www.twitch.tv/videos/"
    URLPATH = ROOT + "\\URLS.txt"
    ### 
    template_folder = ROOT + "\\audio_template"
    output_folder = ROOT + "\\clips"
    AUDIO_DIR = ROOT + "\\audio"

    # part1 下载
    # 下载目标音频
    # dl_target_audios(URLPATH, ROOT+"\\audio")

    # part2 分析音频
    print("\n--- Part 2: 分析音频 (从文件名直接解析信息) ---")

    if not os.path.exists(AUDIO_DIR):
        print(f"错误: 音频目录 {AUDIO_DIR} 未找到。请确保 Part 1 已成功执行或音频文件已存在。")
        exit()

    # audio_files_to_process = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp4', '.m4a', '.wav', '.mp3', '.aac', '.ogg'))]
    audio_files_to_process = ["2458421103_000000.000_052600.000.mp4"] # 仅测试这一个文件
    if not audio_files_to_process:
        print(f"在目录 {AUDIO_DIR} 中没有找到支持的音频文件进行分析。")
        # exit()

    for audio_file_name in audio_files_to_process:
        current_audio_path = os.path.join(AUDIO_DIR, audio_file_name)
        base_name = os.path.splitext(audio_file_name)[0]

        try:
            parts = base_name.split('_')
            if len(parts) < 2: # 至少需要 videoID 和 startTime 部分
                print(f"警告: 文件名 '{audio_file_name}' 格式不符合 'videoID_startTime_...' 规范。跳过此文件。")
                continue

            audio_file_video_id = parts[0]
            # clip_start_time_from_filename 的格式应为 "HHMMSS.mmm", 例如 "000300.000"
            clip_start_time_from_filename = parts[1]

            # --- 新的验证和解析逻辑 ---
            if not (len(clip_start_time_from_filename) == 10 and clip_start_time_from_filename[6] == '.'):
                print(f"警告: 从文件名 '{audio_file_name}' 解析的起始时间部分 '{clip_start_time_from_filename}' 格式无效。预期格式为 'HHMMSS.mmm' (10个字符，第7位是'.')。跳过此文件。")
                continue

            # 进一步验证数字部分
            time_parts_for_check = clip_start_time_from_filename.split('.')
            if not (len(time_parts_for_check) == 2 and len(time_parts_for_check[0]) == 6 and time_parts_for_check[0].isdigit() and len(time_parts_for_check[1]) == 3 and time_parts_for_check[1].isdigit()):
                print(f"警告: 从文件名 '{audio_file_name}' 解析的起始时间部分 '{clip_start_time_from_filename}' 的数字部分格式无效。预期格式为 'HHMMSS.mmm'。跳过此文件。")
                continue

            # 从 "HHMMSS.mmm" 格式转换为 "HH:MM:SS.sss"
            h_str = clip_start_time_from_filename[0:2]
            m_str = clip_start_time_from_filename[2:4]
            s_str = clip_start_time_from_filename[4:6]
            ms_str = clip_start_time_from_filename[7:10] # 小数点后的三位

            clip_start_time_standard_format = f"{h_str}:{m_str}:{s_str}.{ms_str}"
            # --- 结束新的验证和解析逻辑 ---

            clip_original_start_s = hts(clip_start_time_standard_format)

        except IndexError:
            print(f"警告: 无法从文件名 '{audio_file_name}' 中完整解析 video_id 和起始时间。文件名格式应为 'videoID_startTimeHHMMSS.mmm_...'。跳过此文件。")
            continue
        except Exception as e:
            print(f"处理文件名 '{audio_file_name}' 时发生错误: {e}。跳过此文件。")
            continue

        twitch_url_for_analysis = URLROOT + audio_file_video_id

        print(f"\n正在处理音频文件: {audio_file_name}")
        print(f"  对应的 Twitch Video ID: {audio_file_video_id}")
        print(f"  此音频片段在原始视频中的起始时间（秒）: {clip_original_start_s:.3f} (从文件名中的 '{clip_start_time_from_filename}' 解析为 '{clip_start_time_standard_format}')")

        find_impact_segments(
            twitch_url_for_analysis,
            current_audio_path,
            template_folder,
            output_folder,
            audio_clip_original_starttime_seconds=clip_original_start_s,
            x=X,
            dis=DISTANCE,
            pro=PRO,
            segment_duration_seconds = Segment_Duration_Seconds,
            overlap_seconds = Overlap_Seconds
        )

    print("\n--- Part 2: 音频分析完成 ---")

    # part3 下载片段
    # 根据每个文件夹下的时间戳txt文件，下载对应的视频片段
    # for folder in os.listdir(output_folder):
    #     if folder in ['2386208922','2380809051']:# 过滤列表
    #         continue
    #     twitch_url = URLROOT + folder
    #     # 在txt里写个时间范围似乎更好，排除其他游戏
    #     download_impact_segments(twitch_url, f"{output_folder}/{folder}/timestamps.txt", f"{output_folder}/{folder}")

    # # part4 检查
    # # 手动检查下载的视频片段，如果有问题，拖入一个新的problem文件夹 更新txt文件
    # for folder in os.listdir(output_folder):
    #     twitch_url = URLROOT + folder
    #     update_txt(output_folder+'\\'+folder+'\\timestamps.txt', output_folder+'\\'+folder+'\\problem')
    # # 重新下载问题片段
    # for folder in os.listdir(output_folder):
    #     twitch_url = URLROOT + folder
    #     redownload_segments(twitch_url, output_folder+'\\'+folder+'\\timestamps.txt', output_folder+'\\'+folder)
