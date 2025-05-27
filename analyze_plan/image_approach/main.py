import os
import logging
from urllib.parse import urlparse
# 确保 analysis_functions.py 中的函数被导入
from analysis_functions import (
    find_shooting_moments,
)
from general_function import (
    download_twitch,
)
from clip_functions import(
    clip_video_ffmpeg, clip_video_ffmpeg_merged,clip_video_ffmpeg_with_duration,process_and_merge_times
)

def setup_global_logging(log_file_path ="app.log"):
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        print(f"Created log directory: {log_dir}") # Simple feedback for setup

    # Configure logging ONCE, typically at the start of your main application.
    # This configures the root logger. All other loggers will inherit this.
    logging.basicConfig(
        filename=log_file_path,
        encoding='utf-8',
        level=logging.DEBUG,       # Set the minimum logging level for the whole application
        format="%(asctime)s [%(levelname)s](%(module)s.%(funcName)s): %(message)s", # Added module and funcName
        datefmt="%Y-%m-%d %H:%M:%S"
    )

main_logger = logging.getLogger(__name__)

if __name__ == "__main__":
    #设置日志
    log_file_path = "E:\\mande\\0_important\\0_script\\analyze_plan\\script_run.log"
    setup_global_logging(log_file_path)
    # If you used logging.getLogger(__name__) here, __name__ is "__main__".
    main_logger = logging.getLogger(__name__) # Using a specific name

    main_logger.info("Application starting...")

    NUMBER_ROI_X1 = 1723
    NUMBER_ROI_Y1 = 958
    NUMBER_ROI_X2 = 1787
    NUMBER_ROI_Y2 = 1002
    NUMBER_MID = 1754
    BOW_ROI_X1 = 1554
    BOW_ROI_Y1 = 958
    BOW_ROI_X2 = 1702
    BOW_ROI_Y2 = 998
    INFINITE_ROI_X1 = 1723
    INFINITE_ROI_Y1 = 964
    INFINITE_ROI_X2 = 1782
    INFINITE_ROI_Y2 = 993
    BOW_SIMILARITY_THRESHOLD = 0.75
    SIMILARITY_THRESHOLD_INFINITE = 0.74
    COARSE_SCAN_INTERVAL_SECONDS = 3.0
    FINE_SCAN_INTERVAL_SECONDS = 0.1
    START_TIME = "00:00:00.000"

    ROOT = "E:\\mande\\0_PLAN"
    URLROOT = "https://www.twitch.tv/videos/"
    URLPATH = os.path.join(ROOT, "video_urls.txt")

    template_image_path = os.path.join(ROOT, "pic_template", "template_bow.png")
    infinite_symbol_template_path = os.path.join(ROOT, "pic_template", "template_infinite_bow.png")

    output_root_folder = os.path.join(ROOT, "clips_output")
    os.makedirs(output_root_folder, exist_ok=True)

    video_download_base_dir = os.path.join(ROOT, "downloaded_videos")
    os.makedirs(video_download_base_dir, exist_ok=True)

    # --- 用户选择要运行的Part ---
    main_logger.info("脚本开始运行。")
    main_logger.info("--------------------------------------------------")
    main_logger.info("可用的脚本部分:")
    main_logger.info("  Part 1: 下载视频")
    main_logger.info("  Part 2: 分析视频 - 检测射击时刻 (合并逻辑)")
    main_logger.info("  Part 3: 根据 shooting_bow.txt 剪辑视频")
    main_logger.info("  Part 4: 根据infinite剪辑出片段用于Pr中查看射击点")
    main_logger.info("  Part 5: 合并两个txt")
    main_logger.info("  Part 6: 根据sum.txt剪辑")
    main_logger.info("--------------------------------------------------")

    while True:
        parts_to_run_input = input("请输入要运行的Part编号，用逗号分隔 (例如: 1,3,4)，或输入 'all' 运行所有: ").strip().lower()
        if parts_to_run_input == 'all':
            selected_parts = {'1', '2', '3', '4', '5', '6'}
            main_logger.info(f"用户选择运行所有Parts: {sorted(list(selected_parts))}")
            break
        else:
            selected_parts = {part.strip() for part in parts_to_run_input.split(',')}
            valid_parts = {'1', '2', '3', '4', '5', '6'}
            if selected_parts.issubset(valid_parts) and selected_parts:
                main_logger.info(f"用户选择运行Parts: {sorted(list(selected_parts))}")
                break
            else:
                main_logger.info("输入无效。请输入有效的Part编号 (1, 2, 3, 4, 5, 6)，用逗号分隔，或输入 'all'。")

    # --- Part 1: 下载视频 ---
    if '1' in selected_parts:
        downloaded_video_files_info = []

        if os.path.exists(URLPATH):
            with open(URLPATH, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    try:
                        parts = line.split(',')
                        video_url = parts[0].strip()

                        parsed_video_id = urlparse(video_url).path.split('/')[-1]
                        if not parsed_video_id:
                            parsed_video_id = f"unknown_video_{line_num}"
                            main_logger.info(f"警告: 无法从URL '{video_url}' 解析出video_id，使用临时代号 '{parsed_video_id}' (主要用于下载日志)")

                        start_time_str = None
                        end_time_str = None
                        if len(parts) == 3:
                            start_time_str = parts[1].strip()
                            end_time_str = parts[2].strip()
                            main_logger.info(f"准备下载视频片段: {video_url} 从 {start_time_str} 到 {end_time_str}")
                            downloaded_file_path = download_twitch(video_url, video_download_base_dir, start_time_str, end_time_str)
                        elif len(parts) == 1:
                            main_logger.info(f"准备下载完整视频: {video_url}")
                            downloaded_file_path = download_twitch(video_url, video_download_base_dir)
                        else:
                            main_logger.info(f"警告: URL文件行格式错误: {line}，跳过。")
                            continue

                        if downloaded_file_path and os.path.exists(downloaded_file_path):
                            actual_filename = os.path.basename(downloaded_file_path)
                            downloaded_video_files_info.append({
                                "parsed_id": parsed_video_id,
                                "filename": actual_filename,
                                "path": downloaded_file_path,
                            })
                            main_logger.info(f"视频 {parsed_video_id} (文件: {actual_filename}) 已下载或已存在于: {downloaded_file_path}")
                        else:
                            main_logger.info(f"视频 {video_url} 未能成功下载或找到。")

                    except Exception as e:
                        main_logger.error(f"处理URL文件行 '{line}' 时出错: {e}")
        else:
            main_logger.info(f"错误: video_urls.txt 文件未找到于 {URLPATH}")
        main_logger.info("--- Part 1 完成 ---")
    else:
        main_logger.info("--- 跳过 Part 1: 下载视频 ---")


    # --- Part 2: 分析视频 - 检测射击时刻 (合并逻辑) ---
    if '2' in selected_parts:
        if not os.path.exists(template_image_path):
            main_logger.info(f"错误: 弓箭模板图片 {template_image_path} 未找到。Part 2 将跳过。")
        elif not os.path.exists(infinite_symbol_template_path):
            main_logger.info(f"错误: 无穷大符号模板图片 {infinite_symbol_template_path} 未找到。Part 2 将跳过。")
        elif not os.path.exists(video_download_base_dir) or not os.listdir(video_download_base_dir):
            main_logger.info(f"错误: 视频下载目录 '{video_download_base_dir}' 不存在或为空。请先运行 Part 1 或确保该目录有视频。Part 2 跳过。")
        else:
            main_logger.info(f"开始扫描目录 '{video_download_base_dir}' 中的视频文件进行分析...")
            processed_videos_in_part2 = 0
            for filename_in_dir in os.listdir(video_download_base_dir):
                ######只运行一个文件######
                if filename_in_dir == '2463573331.mp4':
                    main_logger.info(f"处理文件: {filename_in_dir}")
                else:
                    main_logger.info(f"跳过: {filename_in_dir}")
                    continue
                if filename_in_dir.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    video_path_for_analysis = os.path.join(video_download_base_dir, filename_in_dir)
                    current_video_id = os.path.splitext(filename_in_dir)[0]
                    main_logger.info(f"\n[Part 2] 分析视频文件: {filename_in_dir} (ID: {current_video_id})")
                    main_logger.info(f"完整路径: {video_path_for_analysis}")
                    video_specific_output_dir_part2 = os.path.join(output_root_folder, current_video_id)
                    os.makedirs(video_specific_output_dir_part2, exist_ok=True)
                    shooting_bow_txt_path = os.path.join(video_specific_output_dir_part2, "shooting_bow.txt")
                    infinite_txt_path = os.path.join(video_specific_output_dir_part2, "infinite.txt")
                    output_exists = False
                    if os.path.exists(shooting_bow_txt_path):
                        main_logger.info(f"分析结果文件 {shooting_bow_txt_path} 已存在。")
                        output_exists = True
                    if os.path.exists(infinite_txt_path): # infinite.txt 也可能由 Part 2 生成
                        main_logger.info(f"分析结果文件 {infinite_txt_path} 已存在。")
                        output_exists = True
                    if output_exists:
                        overwrite = input(f"是否覆盖 '{video_specific_output_dir_part2}' 中的现有分析文件? (y/n，默认为n): ").lower()
                        if overwrite != 'y':
                            main_logger.info(f"跳过对视频 {current_video_id} 的分析。")
                            continue
                    main_logger.info(f"分析参数 -> BowTh: {BOW_SIMILARITY_THRESHOLD}, InfTh: {SIMILARITY_THRESHOLD_INFINITE}, " +
                                  f"NumROI: ({NUMBER_ROI_X1},{NUMBER_ROI_Y1},{NUMBER_ROI_X2},{NUMBER_ROI_Y2}), " +
                                  f"Coarse: {COARSE_SCAN_INTERVAL_SECONDS}s, Fine: {FINE_SCAN_INTERVAL_SECONDS}s")
                    main_logger.info(f"分析结果将保存到: {video_specific_output_dir_part2}")
                    find_shooting_moments(
                        video_path_for_analysis,
                        template_image_path,
                        infinite_symbol_template_path,
                        shooting_bow_txt_path,
                        infinite_txt_path,
                        similarity_threshold_bow = BOW_SIMILARITY_THRESHOLD,
                        similarity_threshold_infinite = SIMILARITY_THRESHOLD_INFINITE,

                        number_roi_x1 = NUMBER_ROI_X1,
                        number_roi_y1 = NUMBER_ROI_Y1,
                        number_roi_x2 = NUMBER_ROI_X2,
                        number_roi_y2 = NUMBER_ROI_Y2,
                        mid_split_x = NUMBER_MID,

                        bow_roi_x1 = BOW_ROI_X1,
                        bow_roi_y1 = BOW_ROI_Y1,
                        bow_roi_x2 = BOW_ROI_X2,
                        bow_roi_y2 = BOW_ROI_Y2,

                        infinite_roi_x1 = INFINITE_ROI_X1,
                        infinite_roi_y1 = INFINITE_ROI_Y1,
                        infinite_roi_x2 = INFINITE_ROI_X2,
                        infinite_roi_y2 = INFINITE_ROI_Y2,
                        
                        coarse_interval_seconds=COARSE_SCAN_INTERVAL_SECONDS,
                        fine_interval_seconds=FINE_SCAN_INTERVAL_SECONDS,
                        start_time = START_TIME
                    )
                    processed_videos_in_part2 += 1
            if processed_videos_in_part2 == 0 and any(fname.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')) for fname in os.listdir(video_download_base_dir)):
                 main_logger.info(f"在目录 '{video_download_base_dir}' 中没有视频被实际分析（可能都选择了不覆盖）。")
            elif processed_videos_in_part2 == 0: # 目录中有文件，但没有一个是视频文件
                 main_logger.info(f"在目录 '{video_download_base_dir}' 中没有找到符合条件的可处理视频文件。")
        main_logger.info("--- Part 2 (分析) 完成 ---")
    else:
        main_logger.info("--- 跳过 Part 2: 分析视频 ---")


    # --- Part 3 : 根据 shooting_bow.txt 剪辑视频 ---
    if '3' in selected_parts:
        if not os.path.exists(video_download_base_dir) or not os.listdir(video_download_base_dir):
            main_logger.info(f"错误: 视频下载目录 '{video_download_base_dir}' 不存在或为空。没有视频可供剪辑。Part 3 跳过。")
        else:
            main_logger.info(f"开始扫描目录 '{video_download_base_dir}' 中的视频文件准备剪辑...")
            processed_clips_in_part3 = 0
            for filename_in_dir_p3 in os.listdir(video_download_base_dir):
                if filename_in_dir_p3.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p3)
                    current_video_id_p3 = os.path.splitext(filename_in_dir_p3)[0]
                    ######只处理一个文件时用######
                    if current_video_id_p3 == '2463573331':
                        main_logger.info(f"处理文件: {current_video_id_p3}")
                    else:
                        main_logger.info(f"跳过: {current_video_id_p3}")
                        continue

                    main_logger.info(f"\n[Part 3] 准备为视频 {current_video_id_p3} (源文件: {filename_in_dir_p3}) 剪辑片段...")

                    video_specific_output_dir_p3 = os.path.join(output_root_folder, current_video_id_p3)
                    shooting_bow_txt_path_for_clipping = os.path.join(video_specific_output_dir_p3, "shooting_bow.txt")

                    if not os.path.exists(video_specific_output_dir_p3):
                        main_logger.info(f"提示: 视频 {current_video_id_p3} 的分析输出目录 '{video_specific_output_dir_p3}' 不存在。可能未经过 Part 2 分析。跳过剪辑。")
                        continue
                    if not os.path.exists(shooting_bow_txt_path_for_clipping):
                        main_logger.info(f"错误: 时间戳文件 {shooting_bow_txt_path_for_clipping} 未找到。请先成功运行 Part 2 (分析)。跳过视频 {current_video_id_p3} 的剪辑。")
                        continue
                    if os.path.getsize(shooting_bow_txt_path_for_clipping) == 0:
                        main_logger.info(f"提示: {shooting_bow_txt_path_for_clipping} 为空，没有片段可为视频 {current_video_id_p3} 剪辑。")
                        continue

                    main_logger.info(f"剪辑片段将保存在: {video_specific_output_dir_p3}")

                    # clip_video_ffmpeg_merged(video_path_for_clipping, shooting_bow_txt_path_for_clipping, video_specific_output_dir_p3, clip_duration=1.1)# 视频长度 间隔时间较近的片段合并
                    clip_video_ffmpeg(video_path_for_clipping, shooting_bow_txt_path_for_clipping, video_specific_output_dir_p3, clip_duration=0.9)# 视频长度
                    processed_clips_in_part3 +=1 # 视频的射箭节奏比较均匀

            if processed_clips_in_part3 == 0:
                main_logger.info(f"在目录 '{video_download_base_dir}' 中没有找到可处理剪辑的视频（或其对应的txt文件无效/不存在）。")
        main_logger.info("--- Part 3 (剪辑) 完成 ---")
    else:
        main_logger.info("--- 跳过 Part 3: 剪辑视频 ---")

    # --- Part 4 : INFINITE剪辑---
    if '4' in selected_parts:
        if not os.path.exists(video_download_base_dir) or not os.listdir(video_download_base_dir):
            main_logger.info(f"错误: 视频下载目录 '{video_download_base_dir}' 不存在或为空。没有视频可供剪辑。Part 4 跳过。")
        else:
            main_logger.info(f"开始扫描目录 '{video_download_base_dir}' 中的视频文件准备INFINITE剪辑...")
            processed_clips_in_part4 = 0
            for filename_in_dir_p3 in os.listdir(video_download_base_dir):
                if filename_in_dir_p3.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p3)
                    current_video_id_p3 = os.path.splitext(filename_in_dir_p3)[0]
                    ######只处理一个文件时用######
                    if current_video_id_p3 == '2463573331':
                        main_logger.info(f"处理文件: {current_video_id_p3}")
                    else:
                        main_logger.info(f"跳过: {current_video_id_p3}")
                        continue

                    main_logger.info(f"\n[Part 4] 准备为视频 {current_video_id_p3} (源文件: {filename_in_dir_p3}) 剪辑片段...")

                    video_specific_output_dir_p3 = os.path.join(output_root_folder, current_video_id_p3)
                    shooting_bow_txt_path_for_clipping = os.path.join(video_specific_output_dir_p3, "infinite_2.txt")

                    if not os.path.exists(video_specific_output_dir_p3):
                        main_logger.info(f"提示: 视频 {current_video_id_p3} 的分析输出目录 '{video_specific_output_dir_p3}' 不存在。可能未经过 Part 2 分析。跳过剪辑。")
                        continue
                    if not os.path.exists(shooting_bow_txt_path_for_clipping):
                        main_logger.info(f"错误: 时间戳文件 {shooting_bow_txt_path_for_clipping} 未找到。请先成功运行 Part 2 (分析)。跳过视频 {current_video_id_p3} 的剪辑。")
                        continue
                    if os.path.getsize(shooting_bow_txt_path_for_clipping) == 0:
                        main_logger.info(f"提示: {shooting_bow_txt_path_for_clipping} 为空，没有片段可为视频 {current_video_id_p3} 剪辑。")
                        continue

                    main_logger.info(f"剪辑片段将保存在: {video_specific_output_dir_p3}")

                    clip_video_ffmpeg_with_duration(video_path_for_clipping, shooting_bow_txt_path_for_clipping, video_specific_output_dir_p3)# 视频长度
                    processed_clips_in_part4 +=1 # 视频的射箭节奏比较均匀

            if processed_clips_in_part4 == 0:
                main_logger.info(f"在目录 '{video_download_base_dir}' 中没有找到可处理剪辑的视频（或其对应的txt文件无效/不存在）。")
        main_logger.info("--- Part 4 (INFINITE剪辑) 完成 ---")
    else:
        main_logger.info("--- 跳过 Part 4: INFINITE剪辑 ---")

    main_logger.info(f"\n脚本运行结束。选择运行的Parts: {sorted(list(selected_parts))}")

    # --- Part 5 : 合并INFINITE到shooting---
    if '5' in selected_parts:
        if not os.path.exists(video_download_base_dir) or not os.listdir(video_download_base_dir):
            main_logger.info(f"错误: 视频下载目录 '{video_download_base_dir}' 不存在或为空。没有视频可供剪辑。Part 4 跳过。")
        else:
            main_logger.info(f"开始扫描目录 '{video_download_base_dir}' 中的视频文件准备INFINITE剪辑...")
            processed_clips_in_part4 = 0
            for filename_in_dir_p3 in os.listdir(video_download_base_dir):
                if filename_in_dir_p3.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p3)
                    current_video_id_p3 = os.path.splitext(filename_in_dir_p3)[0]
                    ######只处理一个文件时用######
                    if current_video_id_p3 == '2463573331':
                        main_logger.info(f"处理文件: {current_video_id_p3}")
                    else:
                        main_logger.info(f"跳过: {current_video_id_p3}")
                        continue
                    main_logger.info(f"\n[Part 3] 准备为视频 {current_video_id_p3} 合并两个txt")

                    video_specific_output_dir_p3 = os.path.join(output_root_folder, current_video_id_p3)
                    shooting_bow_file = os.path.join(video_specific_output_dir_p3, "shooting_bow.txt")
                    infinite_file = os.path.join(video_specific_output_dir_p3, "infinite_3.txt")
                    process_and_merge_times(shooting_bow_file, infinite_file)
    # --- Part 6 : 对新的txt进行剪辑---
    if '6' in selected_parts:
        if not os.path.exists(video_download_base_dir) or not os.listdir(video_download_base_dir):
            main_logger.info(f"错误: 视频下载目录 '{video_download_base_dir}' 不存在或为空。没有视频可供剪辑。Part 6 跳过。")
        else:
            main_logger.info(f"开始扫描目录 '{video_download_base_dir}' 中的视频文件准备剪辑...")
            processed_clips_in_part3 = 0
            for filename_in_dir_p3 in os.listdir(video_download_base_dir):
                if filename_in_dir_p3.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    video_path_for_clipping = os.path.join(video_download_base_dir, filename_in_dir_p3)
                    current_video_id_p3 = os.path.splitext(filename_in_dir_p3)[0]
                    ######只处理一个文件时用######
                    if current_video_id_p3 == '2463573331':
                        main_logger.info(f"处理文件: {current_video_id_p3}")
                    else:
                        main_logger.info(f"跳过: {current_video_id_p3}")
                        continue

                    main_logger.info(f"\n[Part 3] 准备为视频 {current_video_id_p3} (源文件: {filename_in_dir_p3}) 剪辑片段...")

                    video_specific_output_dir_p3 = os.path.join(output_root_folder, current_video_id_p3)
                    shooting_bow_txt_path_for_clipping = os.path.join(video_specific_output_dir_p3, "shooting_bow_sum.txt")

                    if not os.path.exists(video_specific_output_dir_p3):
                        main_logger.info(f"提示: 视频 {current_video_id_p3} 的分析输出目录 '{video_specific_output_dir_p3}' 不存在。可能未经过 Part 2 分析。跳过剪辑。")
                        continue
                    if not os.path.exists(shooting_bow_txt_path_for_clipping):
                        main_logger.info(f"错误: 时间戳文件 {shooting_bow_txt_path_for_clipping} 未找到。请先成功运行 Part 2 (分析)。跳过视频 {current_video_id_p3} 的剪辑。")
                        continue
                    if os.path.getsize(shooting_bow_txt_path_for_clipping) == 0:
                        main_logger.info(f"提示: {shooting_bow_txt_path_for_clipping} 为空，没有片段可为视频 {current_video_id_p3} 剪辑。")
                        continue

                    main_logger.info(f"剪辑片段将保存在: {video_specific_output_dir_p3}")

                    # clip_video_ffmpeg_merged(video_path_for_clipping, shooting_bow_txt_path_for_clipping, video_specific_output_dir_p3, clip_duration=1.1)# 视频长度 间隔时间较近的片段合并
                    clip_video_ffmpeg(video_path_for_clipping, shooting_bow_txt_path_for_clipping, video_specific_output_dir_p3, clip_duration=0.9)# 视频长度
                    processed_clips_in_part3 +=1 # 视频的射箭节奏比较均匀

            if processed_clips_in_part3 == 0:
                main_logger.info(f"在目录 '{video_download_base_dir}' 中没有找到可处理剪辑的视频（或其对应的txt文件无效/不存在）。")
        main_logger.info("--- Part 6 (剪辑) 完成 ---")
    else:
        main_logger.info("--- 跳过 Part 6: 剪辑视频 ---")