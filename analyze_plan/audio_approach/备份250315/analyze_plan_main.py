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
    X = 0.45 # 最关键参数 0-1之间 越大匹配越严格
    DISTANCE = float(10)
    PRO = 0.1
    ROOT = "E:\\mande\\202503_PLAN"
    URLROOT = "https://www.twitch.tv/videos/"
    URLPATH = ROOT + "\\URLS.txt"
    ### 
    template_folder = ROOT + "\\audio_template"
    output_folder = ROOT + "\\clips"

    # part1 下载
    # 下载目标音频
    #dl_target_audios(URLPATH, ROOT+"\\audio")

    # part2 分析音频 最费时间 容易内存卡顿
    # 遍历每个目标音频文件，运行 find_impact_segments 以获得并记录时间戳txt文件
    # for audio in os.listdir(ROOT+"\\audio"):
    #     twitch_url = URLROOT + audio.split(".")[0]
    #     audio_path = os.path.join(ROOT+"\\audio",audio)
    #     name = os.path.splitext(audio)[0]
    #     if name in ['2386208922','2380809051']:
    #         continue
    #     find_impact_segments(twitch_url, audio_path, template_folder, output_folder, x = X, dis = DISTANCE, pro = PRO)

    # part3 下载片段
    # 根据每个文件夹下的时间戳txt文件，下载对应的视频片段
    for folder in os.listdir(output_folder):
        if folder in ['2386208922','2380809051']:# 过滤列表
            continue
        twitch_url = URLROOT + folder
        # 在txt里写个时间范围似乎更好，排除其他游戏
        download_impact_segments(twitch_url, f"{output_folder}/{folder}/timestamps.txt", f"{output_folder}/{folder}")

    # # part4 检查
    # # 手动检查下载的视频片段，如果有问题，拖入一个新的problem文件夹 更新txt文件
    # for folder in os.listdir(output_folder):
    #     twitch_url = URLROOT + folder
    #     update_txt(output_folder+'\\'+folder+'\\timestamps.txt', output_folder+'\\'+folder+'\\problem')
    # # 重新下载问题片段
    # for folder in os.listdir(output_folder):
    #     twitch_url = URLROOT + folder
    #     redownload_segments(twitch_url, output_folder+'\\'+folder+'\\timestamps.txt', output_folder+'\\'+folder)
