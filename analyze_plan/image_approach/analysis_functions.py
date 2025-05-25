import os
import logging
import cv2
import numpy as np
from general_function import (
    seconds_to_hms,hms_to_seconds,
)

logger = logging.getLogger(__name__)

def compare_score_iou(frame_gray_processed, template_image_path, debug=False):
    try:
        template_original = cv2.imread(template_image_path, cv2.IMREAD_UNCHANGED)
        if template_original is None:
            logger.error(f"[图片比较_IOU] 无法加载模板图片: {template_image_path}")
            return False
        # 1. 将模板转换为灰度图 (如果需要)
        if len(template_original.shape) == 3 and template_original.shape[2] == 4: # BGRA
            template_gray = cv2.cvtColor(template_original[:,:,:3], cv2.COLOR_BGR2GRAY)
        elif len(template_original.shape) == 3: # BGR
            template_gray = cv2.cvtColor(template_original, cv2.COLOR_BGR2GRAY)
        else: # Grayscale
            template_gray = template_original

        # 2. 确保模板是二值图像 (前景为255, 背景为0)
        #    假设模板图片本身已经是干净的黑白图，白色为数字，黑色为背景。
        #    如果模板不是标准的0和255，可以进行阈值处理，例如：
        _, template_binary = cv2.threshold(template_gray, 127, 255, cv2.THRESH_BINARY)

        # 确保输入的 frame_gray_processed 也是二值图像 (前景为255, 背景为0)
        # 这一步通常在调用此函数前 (例如在 read_number_single 中) 已完成
        # _, roi_binary = cv2.threshold(frame_gray_processed, 127, 255, cv2.THRESH_BINARY)
        # 但为了确保，这里可以再次处理，或者信赖调用者传入的是正确的二值图
        roi_binary = frame_gray_processed # 假设调用时已传入正确的二值图 (如 Otsu 的结果)


        th, tw = template_binary.shape[:2]
        fh, fw = roi_binary.shape[:2]

        # 3. 检查尺寸是否完全一致
        if fh != th or fw != tw:
            logger.error(f"[图片比较_IOU] 尺寸不匹配: "
                              f"Frame ROI ({fh}x{fw}) vs Template ({th}x{tw}) for {os.path.basename(template_image_path)}. 跳过比较。")
            return False

        # 4. 计算交集 (Intersection)
        #    只关心白色像素 (255) 的交集
        intersection = cv2.bitwise_and(roi_binary, template_binary)
        intersection_count = np.count_nonzero(intersection == 255)

        # 5. 计算并集 (Union)
        #    只关心白色像素 (255) 的并集
        union = cv2.bitwise_or(roi_binary, template_binary)
        union_count = np.count_nonzero(union == 255)

        # 6. 计算 IoU
        if union_count == 0:
            # 如果并集为0，意味着两个图像都是全黑（没有白色像素）
            # 此时，如果交集也为0，可以认为它们是相似的（都是空的）
            iou = 1.0 if intersection_count == 0 else 0.0
        else:
            iou = intersection_count / union_count

        # logger.info(f"[DEBUG 图片比较_IOU] 模板: {os.path.basename(template_image_path)}, "
        #                   f"交集像素: {intersection_count}, 并集像素: {union_count}, "
        #                   f"IoU: {iou:.4f},")

        return iou

    except Exception as e:
        logger.error(f"[图片比较_IOU] 比较图像时出错 (模板: {os.path.basename(template_image_path)}): {e}")
        import traceback
        traceback.print_exc()
        return False


def compare_twovalue(frame, template_path,
    roi_x1, roi_y1, roi_x2, roi_y2,
    threashold = 0.7,
    debug_image_prefix =None
):
    try:
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = int(roi_x1), int(roi_y1), int(roi_x2), int(roi_y2)
        if not (0 <= x1 < fw and 0 <= y1 < fh and x1 < x2 and y1 < y2 and x2 <= fw and y2 <= fh):
            logger.error(f"[提取数字] ROI坐标 ({x1},{y1},{x2},{y2}) 超出帧边界 ({fw},{fh})")
            return None
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            logger.error("[提取数字] 提取的ROI为空")
            return None
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Otsu二值化
        _, preprocessed_roi_otsu = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if debug_image_prefix:
            try:
                os.makedirs(os.path.dirname(debug_image_prefix), exist_ok=True) # 确保目录存在
                cv2.imwrite(f"{debug_image_prefix}_original_roi.png", roi)
                cv2.imwrite(f"{debug_image_prefix}_gray_roi.png", gray_roi)
                cv2.imwrite(f"{debug_image_prefix}_preprocessed_roi_otsu.png", preprocessed_roi_otsu)
                logger.debug(f"[提取数字] 基础调试图像已保存，前缀: {debug_image_prefix}")
            except Exception as e:
                logger.error(f"[提取数字] 无法保存某些基础调试图像: {e}")

        # Iterate through image files, common extensions like .png, .jpg, .bmp, .tif
        score = compare_score_iou(preprocessed_roi_otsu, template_path)
        if score > threashold:
            # logger.info(f"[DEBUG 图片比较] score {score} > threashold {threashold} 匹配")
            return True
        else:
            # logger.info(f"[DEBUG 图片比较] score {score} <= threashold {threashold} 不匹配")
            return False
                  
    except Exception as e:
        logger.error(f"[FATAL 提取数字] 处理ROI时发生严重错误: {e}")
        import traceback
        traceback.print_exc()
    return None


def read_number_single(
    frame, 
    roi_x1, roi_y1, roi_x2, roi_y2, 
    lorr,
    debug_image_prefix=None,
):
    try:
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = int(roi_x1), int(roi_y1), int(roi_x2), int(roi_y2)
        if not (0 <= x1 < fw and 0 <= y1 < fh and x1 < x2 and y1 < y2 and x2 <= fw and y2 <= fh):
            logger.error(f"[提取数字] ROI坐标 ({x1},{y1},{x2},{y2}) 超出帧边界 ({fw},{fh})")
            return None
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            logger.error("[提取数字] 提取的ROI为空")
            return None
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Otsu二值化
        _, preprocessed_roi_otsu = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if debug_image_prefix:
            try:
                os.makedirs(os.path.dirname(debug_image_prefix), exist_ok=True) # 确保目录存在
                cv2.imwrite(f"{debug_image_prefix}_original_roi.png", roi)
                cv2.imwrite(f"{debug_image_prefix}_gray_roi.png", gray_roi)
                cv2.imwrite(f"{debug_image_prefix}_preprocessed_roi_otsu.png", preprocessed_roi_otsu)
                logger.debug(f"[提取数字] 基础调试图像已保存，前缀: {debug_image_prefix}")
            except Exception as e:
                logger.error(f"[提取数字] 无法保存某些基础调试图像: {e}")
        # 写个循环遍历如果lorr='right'则便利E:\\mande\\0_PLAN\\pic_template\\right 中的所有图片 运行compare_images_grayscale(preprocessed_roi_otsu, "E:\\mande\\0_PLAN\\pic_template\\i.png", 0.9)，如果为真则返回这个值，如果都没有则返回none。如果lorr='left' 同理完成
        base_template_path = "E:\\mande\\0_PLAN\\pic_template"
        if lorr == 'right':
            template_dir = os.path.join(base_template_path, "right")
        elif lorr == 'left':
            template_dir = os.path.join(base_template_path, "left")
        else:
            logger.error(f"[ERROR 提取数字] 无效的 'lorr' 参数: {lorr}. 必须是 'left' 或 'right'.")
            return None

        if not os.path.isdir(template_dir):
            logger.error(f"[ERROR 提取数字] 模板目录不存在: {template_dir}")
            return None

        # Iterate through image files, common extensions like .png, .jpg, .bmp, .tif
        valid_extensions = ('.png')
        tmpscore = 0.6
        digit_name = None
        for filename in sorted(os.listdir(template_dir)): # sorted 确保一致的顺序
            if filename.lower().endswith(valid_extensions):
                template_path = os.path.join(template_dir, filename)
                curscore = compare_score_iou(preprocessed_roi_otsu, template_path)
                # logger.info(str(filename) + ' ' + str(curscore))
                if curscore > tmpscore:
                    tmpscore = curscore
                    digit_name = os.path.splitext(filename)[0][0] # 获取不带扩展名的数字，如 "0"
                    # logger.info(f"[INFO 提取数字] 成功覆盖 匹配度{tmpscore}. 识别为: {digit_name}")
        if tmpscore > 0.6:
            # logger.info(f"[INFO 提取数字] {lorr} 识别为: {digit_name} 匹配度:{tmpscore} ")
            return digit_name # 返回识别到的数字字符串
        else:
            logger.info(f"[提取数字] {lorr} {template_dir} 中未找到>0.6的匹配模板。")
            return None
                  
    except Exception as e:
        logger.error(f"[FATAL 提取数字] 处理ROI时发生严重错误: {e}")
        import traceback
        traceback.print_exc()
    return None

def read_number_two(frame, full_roi_x1, full_roi_y1, full_roi_x2, full_roi_y2, mid_split_x, debug_image_prefix_base=None):
    # Prepare debug prefixes if a base prefix is provided
    left_debug_prefix = f"{debug_image_prefix_base}_left_digit" if debug_image_prefix_base else None
    right_debug_prefix = f"{debug_image_prefix_base}_right_digit" if debug_image_prefix_base else None

    # Extract left digit
    digit1 = read_number_single(frame,full_roi_x1, full_roi_y1,
                                           mid_split_x, full_roi_y2,'left',
                                           debug_image_prefix=left_debug_prefix)
    # Extract right digit
    digit2 = read_number_single(frame,mid_split_x, full_roi_y1,
                                           full_roi_x2, full_roi_y2,'right',
                                           debug_image_prefix=right_debug_prefix)
    # logger.info(f"[DEBUG read_number_two] Left digit: {digit1}")
    # logger.info(f"[DEBUG read_number_two] Right digit: {digit2}")
    # Combine the digits
    if digit1 is not None and digit2 is not None:
        combined_number_str = f"{digit1}{digit2}"
        try:
            combined_number_int = int(combined_number_str)
            logger.info(f"[提取两位数字] 成功组合数字: {combined_number_int}")
            return combined_number_int
        except ValueError:
            logger.error(f"[提取两位数字] 组合后的字符串 '{combined_number_str}' 无法转换为整数。")
            return None
    else:
        # logger.info("[DEBUG 提取两位数字] 未能提取一个或两个数字以组成两位数。")
        # if digit1 is None:
        #     logger.info("[DEBUG 提取两位数字] 左侧数字提取失败。")
        # if digit2 is None:
        #     logger.info("[DEBUG 提取两位数字] 右侧数字提取失败。")
        return None


def find_shooting_moments(video_path, 
                                   bow_template_path,
                                   infinite_symbol_template_path,
                                   shooting_output_txt_path,
                                   infinite_output_txt_path,
                                   similarity_threshold_bow,
                                   similarity_threshold_infinite,
                                   number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x,
                                   bow_roi_x1,bow_roi_y1,bow_roi_x2,bow_roi_y2,
                                   infinite_roi_x1,infinite_roi_y1,infinite_roi_x2,infinite_roi_y2,
                                   coarse_interval_seconds=3.0,
                                   fine_interval_seconds=0.1, start_time="00:00:00.000"):
    version_tag = "20250521VLog"
    logger.info(f"\n Initiating for video: {video_path}")
    logger.info(f" Bow Template: {os.path.basename(bow_template_path)}, Similarity Threshold: {similarity_threshold_bow}")
    logger.info(f" Infinite Symbol Template: {os.path.basename(infinite_symbol_template_path)}, Similarity Threshold: {similarity_threshold_infinite}")
    logger.info(f" Shooting Output: {shooting_output_txt_path}")
    logger.info(f" Infinite Symbol Start Output: {infinite_output_txt_path}")
    logger.info(f" Number ROI (x1,y1,x2,y2): ({number_roi_x1},{number_roi_y1},{number_roi_x2},{number_roi_y2}).")
    logger.info(f" Coarse Interval: {coarse_interval_seconds}s, Fine Interval: {fine_interval_seconds}s")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.info(f"错误: 无法打开视频 {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or fps is None:
        logger.info(f"错误: 无法读取视频FPS或FPS为0 {video_path}")
        cap.release()
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        logger.info(f"错误: 视频总帧数为0 {video_path}")
        cap.release()
        return

    logger.info(f" Video FPS: {fps}, Total Frames: {total_frames}")

    frame_skip_coarse = int(fps * coarse_interval_seconds)
    if frame_skip_coarse == 0: frame_skip_coarse = 1
    frame_skip_fine = int(fps * fine_interval_seconds)
    if frame_skip_fine == 0: frame_skip_fine = 1
    logger.info(f" 粗步长: {frame_skip_coarse} frames, 精步长: {frame_skip_fine} frames")

    shooting_times = []
    infinite_symbo_times = []
    prev_number_coarse = 10000
    prev_number_coarse_frame = 0
    current_frame_num = int(hms_to_seconds(start_time)*fps)
    last_coarse_log_frame = -frame_skip_coarse * 10 
    prev_frame_had_infinite_coarse = False
    prev_frame_had_infinite_coarse_frame = 0
    last_bow_frame = 0
    # 大步29->notbow->27: 只有在 is_bow正在使用弓时才改变“上一个”或“上一帧”，相应着，精扫描时范围使用上一帧到现在帧
    # 大步29->(28)->notbow->∞: (28)表示被跳过的，触发无穷精扫，遇上28，就会记录无穷触发时间，但前面还有一个数字变化，不能漏掉，所以精扫中记录后不跳出，直到扫完。注意prev_number_fine要在进入循环前赋值，如果是无穷触发赋一个很小的-1
    # 大步29->(∞)->notbow->28：3秒内不会出现
    # 视频开头∞->notbow->∞：这时候就连续不标记∞，导致真个∞被忽略。这是我测试片段的特殊性，一般不会开头是∞

    WRITE_TXT_COUNTS = 10
    coarse_loop_iteration_counter = 0
    while current_frame_num < total_frames: # 粗循环
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_num)
        ret, frame = cap.read()
        if not ret:
            logger.info(f"[Analysis 粗] Error reading frame {current_frame_num}. Ending.")
            break

        timestamp_sec = current_frame_num / fps

        if current_frame_num >= last_coarse_log_frame + frame_skip_coarse : # 间隔性地定期输出信息
            logger.info(f"[Analysis 粗] : 粗循环扫描到 Frame {current_frame_num}/{total_frames} ({seconds_to_hms(timestamp_sec)}), “上个数字”: {prev_number_coarse}")
            last_coarse_log_frame = current_frame_num
        is_bow_active = compare_twovalue(frame, bow_template_path, bow_roi_x1,bow_roi_y1,bow_roi_x2,bow_roi_y2, threashold = similarity_threshold_bow)

        if is_bow_active: # 如果是弓箭 排除其他武器或背包界面
            last_bow_frame = current_frame_num
            fine_scan_reason = None
            current_number_coarse = read_number_two(frame, number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x)
            detected_shot_in_coarse = False
            if current_number_coarse is not None and prev_number_coarse is not None:# 如果两者都是数字
                if current_number_coarse != prev_number_coarse : # 且数字不一样，例如 28 -> 25最一般情况， 包括补充子弹28 -> 40 （存在很多补充子弹换枪的情况，这种情况要不要复查前面这一段，我很纠结，按说3秒也不算长，开包时间多数也很长，制造装置时间也很长） 包括两把弓交换时28 -> 40 因为这种情况还是扫描吧。还有28->23但是只是两把弓交换，这种也能cover
                    detected_shot_in_coarse = True
            if detected_shot_in_coarse: # 如果检测到射击
                fine_scan_reason = "shot"
                logger.info(f"[Analysis 粗] 数字变化触发精扫描 {current_frame_num} ({seconds_to_hms(timestamp_sec)}). Num: {prev_number_coarse} -> {current_number_coarse}.")
            else: #如果是无穷
                current_frame_is_infinite = compare_twovalue(frame, infinite_symbol_template_path,infinite_roi_x1,infinite_roi_y1,infinite_roi_x2,infinite_roi_y2,threashold = similarity_threshold_infinite)
                if not prev_frame_had_infinite_coarse and current_frame_is_infinite:# 如果现在是新无穷
                    fine_scan_reason = "infinite"
                    if timestamp_sec not in infinite_symbo_times:
                        infinite_symbo_times.append(max(0, timestamp_sec))# 作为 ∞ 的时间
                        logger.info(f"[Analysis 粗] ∞时刻 记录下{seconds_to_hms(timestamp_sec)}.")    
            
            if fine_scan_reason:
            #     if fine_scan_reason =='infinite': # 这种情况回溯的目的仅仅是检查有没有漏掉数字变化
            #         fine_scan_start_frame = max(0, prev_frame_had_infinite_coarse_frame - frame_skip_fine)
            #         fine_scan_end_frame = min(total_frames - 1, current_frame_num + 1)
            #         prev_number_fine = -5 # 精扫描上一帧的数字
            #         logger.info(f"[Analysis 粗] 精扫描上一个数字为粗扫描结尾数字： {prev_number_fine}")
            #         logger.info(f"[Analysis 粗] 精扫描初始化 '{fine_scan_reason.upper()}': 范围 [{fine_scan_start_frame}, {fine_scan_end_frame}] ({seconds_to_hms(fine_scan_start_frame/fps)} to {seconds_to_hms(fine_scan_end_frame/fps)})")
            #     else:
            #         fine_scan_start_frame = max(0, prev_number_coarse_frame - frame_skip_fine) # 精扫描的开始帧：上次记录的数字的帧前一点点
            #         fine_scan_end_frame = min(total_frames - 1, current_frame_num + 1) # 精扫描的结束帧：粗扫描的当前帧后一点点
            #         prev_number_fine = current_number_coarse # 精扫描上一帧的数字
            #         logger.info(f"[Analysis 粗] 精扫描上一个数字为粗扫描结尾数字： {prev_number_fine}")
            #         logger.info(f"[Analysis 粗] 精扫描初始化 '{fine_scan_reason.upper()}': 范围 [{fine_scan_start_frame}, {fine_scan_end_frame}] ({seconds_to_hms(fine_scan_start_frame/fps)} to {seconds_to_hms(fine_scan_end_frame/fps)})")
                
                prev_number_fine = current_number_coarse # 精扫描上一帧的数字
                fine_scan_start_frame = max(0, current_frame_num - frame_skip_coarse - 1) # 上面这种会更稳能找到一些小概率被忽略的情况，但会因为每场比赛之间的时间而产生大量计算
                fine_scan_end_frame = min(total_frames - 1, current_frame_num + 1) # 精扫描的结束帧：粗扫描的当前帧后一点点
                logger.info(f"[Analysis 粗] 精扫描上一个数字为粗扫描结尾数字： {prev_number_fine}")
                logger.info(f"[Analysis 粗] 精扫描初始化 '{fine_scan_reason}': 范围 [{fine_scan_start_frame}, {fine_scan_end_frame}] ({seconds_to_hms(fine_scan_start_frame/fps)} to {seconds_to_hms(fine_scan_end_frame/fps)})")
                ## 反向扫描
                logger.info(f"[Analysis 精]开始反向扫描")
                tmp_frame = 0
                for fn_fine in range(fine_scan_end_frame, fine_scan_start_frame, - frame_skip_fine): # 倒着扫描
                    tmp_frame = fn_fine
                    if fn_fine < 0: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fn_fine)
                    ret_f, frame_f = cap.read()
                    if not ret_f: continue
                    ts_fine_sec = fn_fine / fps
                    is_bow_active_fine = compare_twovalue(frame_f,bow_template_path,bow_roi_x1,bow_roi_y1,bow_roi_x2,bow_roi_y2,threashold = similarity_threshold_bow) # 是否使用弓箭
                    if is_bow_active_fine: # 保证不是其他武器和背包。
                        current_number_fine = read_number_two(frame_f, number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x)
                        if current_number_fine is not None:# 如果是数字
                            if prev_number_fine is not None:# 都是数字
                                if prev_number_fine + 1 == current_number_fine:# 满足差1的条件
                                    t_fine_shot = ts_fine_sec
                                    shooting_time = max(0, t_fine_shot - 0.3) # 用于记录的时间提前一点0.3
                                    if shooting_time not in shooting_times:
                                        shooting_times.append(shooting_time)
                                        logger.info(f"[Analysis 精] 检测到射击! Frame {fn_fine} ({seconds_to_hms(t_fine_shot)}). Num: {current_number_fine} -> {prev_number_fine}. 记录下: {seconds_to_hms(shooting_time)}")
                            if current_number_fine == prev_number_coarse: # 如果当前数字已经找到粗扫描中的前一个数字，即可跳出
                                logger.info(f"[Analysis 精] 扫描到数字: {current_number_fine} == 端部数字: {prev_number_coarse}. 跳出精扫描")
                                break
                            prev_number_fine = current_number_fine # 只要是数字，就更替
                        else:# 如果当前不是数字，只能是无穷 无穷不记录 继续找数字
                            logger.info(f"[Analysis 精] ∞ 时刻 Frame {fn_fine} ({seconds_to_hms(ts_fine_sec)}) 什么也不做")
                    else: # 如果没有使用弓箭 例如是背包 则不改变数据
                        logger.info(f"[Analysis 精] 没有使用弓箭 Frame {fn_fine} ({seconds_to_hms(ts_fine_sec)})")

                ## 正着扫描
                logger.info(f"[Analysis 精]开始正向扫描. 前一个数字赋值为 = {prev_number_fine}")
                
                for fn_fine in range(fine_scan_start_frame, min(fine_scan_start_frame + frame_skip_fine+1, tmp_frame+1), frame_skip_fine): # 正着扫描时避免重复取tmp_frame但也要考虑很长的间隔的情况下
                    if fn_fine < 0: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fn_fine)
                    ret_f, frame_f = cap.read()
                    if not ret_f: continue
                    ts_fine_sec = fn_fine / fps
                    is_bow_active_fine = compare_twovalue(frame_f,bow_template_path,bow_roi_x1,bow_roi_y1,bow_roi_x2,bow_roi_y2,threashold = similarity_threshold_bow) # 是否使用弓箭
                    if is_bow_active_fine: # 保证不是其他武器和背包。
                        current_number_fine = read_number_two(frame_f, number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x)
                        if current_number_fine is not None:# 如果是数字
                            if prev_number_fine is not None:# 都是数字
                                if prev_number_fine -1 == current_number_fine:# 满足差1的条件
                                    t_fine_shot = ts_fine_sec
                                    shooting_time = max(0, t_fine_shot - 0.3) # 用于记录的时间提前一点0.3
                                    if shooting_time not in shooting_times:
                                        shooting_times.append(shooting_time)
                                        logger.info(f"[Analysis 精] 检测到射击! Frame {fn_fine} ({seconds_to_hms(t_fine_shot)}). Num: {current_number_fine} -> {prev_number_fine}. 记录下: {seconds_to_hms(shooting_time)}")
                            if current_number_fine == current_number_coarse: # 如果当前数字已经找到粗扫描中的后一个数字，即可跳出
                                logger.info(f"[Analysis 精] current_number_fine: {current_number_fine} == prev_number_coarse: {prev_number_coarse}. 跳出精扫描")
                                break
                            prev_number_fine = current_number_fine # 只要是数字，就更替
                        else:# 如果当前不是数字，只能是无穷 无穷不记录 继续找数字
                            logger.info(f"[Analysis 精] ∞ 时刻 Frame {fn_fine} ({seconds_to_hms(ts_fine_sec)}) 什么也不做")
                    else: # 如果没有使用弓箭 例如是背包 则不改变数据
                        logger.info(f"[Analysis 精] 没有使用弓箭 Frame {fn_fine} ({seconds_to_hms(ts_fine_sec)})")

            if current_number_coarse is not None: # 一开始prev_number_coarse没有值，需要付给它第一次出现的，所以写在这里不写在里面
                prev_number_coarse = current_number_coarse
                prev_number_coarse_frame = current_frame_num
            if fine_scan_reason =='infinite': # 更新infinite的记录
                prev_frame_had_infinite_coarse = True
                prev_frame_had_infinite_coarse_frame = current_frame_num
            else:
                prev_frame_had_infinite_coarse = False
                prev_frame_had_infinite_coarse_frame = current_frame_num # 表明检查过的帧 下次调用时就不会很远
        # 非弓箭情况没有命令
        if coarse_loop_iteration_counter > 0 and coarse_loop_iteration_counter % WRITE_TXT_COUNTS == 0:# 写入txt，这时候还不排序
            unique_shooting_times = list(set(shooting_times))
            if len(unique_shooting_times) == 0:
                logger.info(f"没有检测到射击时刻。{shooting_output_txt_path} 不写")
            else:
                logger.info(f"本次写入检测到 {len(unique_shooting_times)} 个独立射击时刻。")
                with open(shooting_output_txt_path, 'a') as f:
                    for t_shot in unique_shooting_times:
                        f.write(f"{seconds_to_hms(t_shot)}\n")
                logger.info(f"本次写入完成")

            unique_infinite_start_times = list(set(infinite_symbo_times))
            if len(unique_infinite_start_times) == 0:
                logger.info(f"没有检测到∞时刻。{shooting_output_txt_path} 不写")
            else:
                logger.info(f"本次写入检测到 {len(unique_infinite_start_times)} 个∞大符号开始时刻。")
                with open(infinite_output_txt_path, 'a') as f:
                    for t_inf_start in unique_infinite_start_times:
                        f.write(f"{seconds_to_hms(t_inf_start)}\n")
                logger.info(f"本次写入完成")
            shooting_times = [] # 清空
            infinite_symbo_times = [] # 清空

        coarse_loop_iteration_counter += 1
        current_frame_num += frame_skip_coarse # 粗步长

    cap.release()
    # 最后完成前导入txt中的加上这时shooting_times的
    ## 写数字的
    if os.path.exists(shooting_output_txt_path):
        with open(shooting_output_txt_path, 'r', encoding='utf-8') as file:
            for line in file:
                shooting_times.append(hms_to_seconds(line.strip()))

    unique_shooting_times = sorted(list(set(shooting_times)))#按时间先后排序
    if len(unique_shooting_times) == 0:
        logger.info(f" 没有检测到射击时刻。{shooting_output_txt_path} 将为空或不创建。")
    else:
        logger.info(f" 检测到 {len(unique_shooting_times)} 个独立射击时刻。")
        with open(shooting_output_txt_path, 'w') as f: # 覆盖写入
            for t_shot in unique_shooting_times:
                f.write(f"{seconds_to_hms(t_shot)}\n")
        logger.info(f"射击时刻已保存到: {shooting_output_txt_path}")
    ## 写无穷的
    if os.path.exists(infinite_output_txt_path):
        with open(infinite_output_txt_path, 'r', encoding='utf-8') as file:
            for line in file:
                infinite_symbo_times.append(hms_to_seconds(line.strip()))

    unique_infinite_start_times = sorted(list(set(infinite_symbo_times)))
    if len(unique_infinite_start_times) == 0:
        logger.info(f" 没有检测到∞大符号开始时刻。{infinite_output_txt_path} 将为空或不创建。")
    else:
        logger.info(f" 检测到 {len(unique_infinite_start_times)} 个∞大符号开始时刻。")
        with open(infinite_output_txt_path, 'w') as f: # 覆盖写入
            for t_inf_start in unique_infinite_start_times:
                f.write(f"{seconds_to_hms(t_inf_start)}\n")
        logger.info(f"∞大符号开始时刻已保存到: {infinite_output_txt_path}")

    logger.info(f" Video {video_path} analysis COMPLETED.")