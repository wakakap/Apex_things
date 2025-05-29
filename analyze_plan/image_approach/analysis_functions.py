import os
import logging
import cv2
import numpy as np
from general_function import (
    seconds_to_hms,hms_to_seconds,
)

logger = logging.getLogger(__name__)

# Define weapon metadata globally or pass it appropriately
# roi_key is currently not used as prompt stated BOW_ROI coords are used for all weapon activation.
# display_name is for the GUI.
WEAPON_METADATA = {
    # Group 1: Standard scan logic, bow has_infinite
    "bow": {"suffix": "bow", "has_infinite": True, "display_name": "Bocek Bow", "scan_logic_type": "standard", "display_name_ch": "波塞克弓"},
    "kraber": {"suffix": "kraber", "has_infinite": False, "display_name": "Kraber", "scan_logic_type": "standard", "display_name_ch": "克雷贝尔"},
    "charge_rifle": {"suffix": "charge", "has_infinite": False, "display_name": "Charge Rifle", "scan_logic_type": "standard", "display_name_ch": "充能步枪"},
    "sentinel": {"suffix": "sentinel", "has_infinite": False, "display_name": "Sentinel", "scan_logic_type": "standard", "display_name_ch": "哨兵"},
    "peacekeeper": {"suffix": "pkred", "has_infinite": False, "display_name": "Peacekeeper (Red)", "scan_logic_type": "standard", "display_name_ch": "和平捍卫者 (红)"},
    "mastiff": {"suffix": "mastiff", "has_infinite": False, "display_name": "Mastiff", "scan_logic_type": "standard", "display_name_ch": "獒犬"},
    "tripletale": {"suffix": "triple", "has_infinite": False, "display_name": "Tripletale", "scan_logic_type": "standard", "display_name_ch": "三重"},
    "longbow": {"suffix": "longbow", "has_infinite": False, "display_name": "Longbow DMR", "scan_logic_type": "standard", "display_name_ch": "长弓精确步枪"},

    # Group 2: Rapid-fire scan logic, no infinite
    "eva8": {"suffix": "eva", "has_infinite": False, "display_name": "EVA-8 Auto", "scan_logic_type": "rapid_fire", "display_name_ch": "EVA-8 自动霰弹枪"},
    "mozambique_double": {"suffix": "mozambiquedouble", "has_infinite": False, "display_name": "Mozambique (Double)", "scan_logic_type": "rapid_fire", "display_name_ch": "莫桑比克 (双发)"},
    "r3030": {"suffix": "3030", "has_infinite": False, "display_name": "30-30 Repeater", "scan_logic_type": "rapid_fire", "display_name_ch": "30-30 重复枪"},
    "wingman": {"suffix": "wingman", "has_infinite": False, "display_name": "Wingman", "scan_logic_type": "rapid_fire", "display_name_ch": "辅助手枪"},
    "g7": {"suffix": "g7", "has_infinite": False, "display_name": "G7 Scout", "scan_logic_type": "rapid_fire", "display_name_ch": "G7 侦察枪"},
    "rampage": {"suffix": "rampage", "has_infinite": False, "display_name": "Rampage LMG", "scan_logic_type": "rapid_fire", "display_name_ch": "暴走轻机枪"},
    "p2020_double": {"suffix": "p2020double", "has_infinite": False, "display_name": "P2020 (Double)", "scan_logic_type": "rapid_fire", "display_name_ch": "P2020 (双发)"},
    "hemlok": {"suffix": "hemlok", "has_infinite": False, "display_name": "Hemlok", "scan_logic_type": "rapid_fire", "display_name_ch": "赫姆洛克"},
    "spitfire": {"suffix": "spitfire", "has_infinite": False, "display_name": "Spitfire", "scan_logic_type": "rapid_fire", "display_name_ch": "喷火"},
    "nemesis": {"suffix": "nemesis", "has_infinite": False, "display_name": "Nemesis", "scan_logic_type": "rapid_fire", "display_name_ch": "复仇女神"},
    "flatline": {"suffix": "flatline", "has_infinite": False, "display_name": "Flatline", "scan_logic_type": "rapid_fire", "display_name_ch": "平行步枪"},
    "havoc": {"suffix": "havoc", "has_infinite": False, "display_name": "Havoc", "scan_logic_type": "rapid_fire", "display_name_ch": "哈沃克"},
    "re45": {"suffix": "re45", "has_infinite": False, "display_name": "RE-45 Auto", "scan_logic_type": "rapid_fire", "display_name_ch": "RE-45 自动手枪"},
    "r301": {"suffix": "r301", "has_infinite": False, "display_name": "R-301 Carbine", "scan_logic_type": "rapid_fire", "display_name_ch": "R-301 卡宾枪"},
    "devotion": {"suffix": "devotion", "has_infinite": False, "display_name": "Devotion LMG", "scan_logic_type": "rapid_fire", "display_name_ch": "专注轻机枪"},
    "car": {"suffix": "car", "has_infinite": False, "display_name": "C.A.R. SMG", "scan_logic_type": "rapid_fire", "display_name_ch": "C.A.R.冲锋枪"},
    "r99": {"suffix": "r99", "has_infinite": False, "display_name": "R-99 SMG", "scan_logic_type": "rapid_fire", "display_name_ch": "R-99 冲锋枪"},
    # Add other weapons here if their templates (e.g. template_g7.png -> "g7": {"suffix": "g7", ...}) exist
}

def compare_score_iou(frame_gray_processed, template_image_path, debug=False):
    try:
        template_original = cv2.imread(template_image_path, cv2.IMREAD_UNCHANGED)
        if template_original is None:
            logger.error(f"[图片比较_IOU] 无法加载模板图片: {template_image_path}")
            return 0.0 # Return a score instead of False

        if len(template_original.shape) == 3 and template_original.shape[2] == 4: # BGRA
            template_gray = cv2.cvtColor(template_original[:,:,:3], cv2.COLOR_BGR2GRAY)
        elif len(template_original.shape) == 3: # BGR
            template_gray = cv2.cvtColor(template_original, cv2.COLOR_BGR2GRAY)
        else: # Grayscale
            template_gray = template_original

        _, template_binary = cv2.threshold(template_gray, 127, 255, cv2.THRESH_BINARY)
        roi_binary = frame_gray_processed 

        th, tw = template_binary.shape[:2]
        fh, fw = roi_binary.shape[:2]

        if fh != th or fw != tw:
            logger.debug(f"[图片比较_IOU] 尺寸不匹配: Frame ROI ({fh}x{fw}) vs Template ({th}x{tw}) for {os.path.basename(template_image_path)}. 返回0分.")
            return 0.0


        intersection = cv2.bitwise_and(roi_binary, template_binary)
        intersection_count = np.count_nonzero(intersection == 255)
        union = cv2.bitwise_or(roi_binary, template_binary)
        union_count = np.count_nonzero(union == 255)

        if union_count == 0:
            iou = 1.0 if intersection_count == 0 else 0.0
        else:
            iou = intersection_count / union_count
        
        # if debug:
        # logger.debug(f"[图片比较_IOU] 模板: {os.path.basename(template_image_path)}, "
        # f"交集像素: {intersection_count}, 并集像素: {union_count}, "
        # f"IoU: {iou:.4f},")
        return iou

    except Exception as e:
        logger.error(f"[图片比较_IOU] 比较图像时出错 (模板: {os.path.basename(template_image_path)}): {e}")
        # import traceback # Keep for detailed debugging if needed
        # traceback.print_exc()
        return 0.0 # Return a score

# Renamed to clarify it's checking a generic ROI against a single template and returning boolean
def check_roi_against_template(frame, template_path,
    roi_x1, roi_y1, roi_x2, roi_y2,
    threshold = 0.7, # Note: variable name is 'threashold' in original, kept for consistency if it's a typo there
    debug_image_prefix = None
):
    try:
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = int(roi_x1), int(roi_y1), int(roi_x2), int(roi_y2)
        if not (0 <= x1 < fw and 0 <= y1 < fh and x1 < x2 and y1 < y2 and x2 <= fw and y2 <= fh):
            logger.error(f"[ROI检查] ROI坐标 ({x1},{y1},{x2},{y2}) 超出帧边界 ({fw},{fh})")
            return False # Changed from None to boolean
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            logger.error("[ROI检查] 提取的ROI为空")
            return False

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, preprocessed_roi_otsu = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        if debug_image_prefix: # 保存调试图像的逻辑保持不变
            try:
                os.makedirs(os.path.dirname(debug_image_prefix), exist_ok=True)
                cv2.imwrite(f"{debug_image_prefix}_original_roi.png", roi)
                cv2.imwrite(f"{debug_image_prefix}_gray_roi.png", gray_roi)
                cv2.imwrite(f"{debug_image_prefix}_preprocessed_roi_otsu.png", preprocessed_roi_otsu)
                logger.debug(f"[ROI检查] 基础调试图像已保存，前缀: {debug_image_prefix}")
            except Exception as e:
                logger.error(f"[ROI检查] 无法保存某些基础调试图像: {e}")

        score = compare_score_iou(preprocessed_roi_otsu, template_path) # Use the IOU score function
        if score > threshold: # Compare with the passed threshold
            # logger.info(f"[DEBUG ROI检查] score {score} > threshold {threshold} 匹配模板 {os.path.basename(template_path)}")
            return True
        else:
            # logger.info(f"[DEBUG ROI检查] score {score} <= threshold {threshold} 不匹配模板 {os.path.basename(template_path)}")
            return False
                  
    except Exception as e:
        logger.error(f"[FATAL ROI检查] 处理ROI时发生严重错误: {e}")
        # import traceback # Keep for detailed debugging if needed
        # traceback.print_exc()
    return False # Return boolean


def read_number_single(
    frame, 
    roi_x1, roi_y1, roi_x2, roi_y2, 
    lorr, # lorr means left or right digit
    root_pic_template_dir, # Added: base path for number templates "E:\\mande\\0_PLAN\\pic_template"
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
        _, preprocessed_roi_otsu = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        if debug_image_prefix: # 保存调试图像的逻辑保持不变
            try:
                os.makedirs(os.path.dirname(debug_image_prefix), exist_ok=True) 
                cv2.imwrite(f"{debug_image_prefix}_original_roi.png", roi)
                cv2.imwrite(f"{debug_image_prefix}_gray_roi.png", gray_roi)
                cv2.imwrite(f"{debug_image_prefix}_preprocessed_roi_otsu.png", preprocessed_roi_otsu)
                logger.debug(f"[提取数字] 基础调试图像已保存，前缀: {debug_image_prefix}")
            except Exception as e:
                logger.error(f"[提取数字] 无法保存某些基础调试图像: {e}")

        # base_template_path = "E:\\mande\\0_PLAN\\pic_template" # Replaced by parameter
        if lorr == 'right':
            template_dir = os.path.join(root_pic_template_dir, "right")
        elif lorr == 'left':
            template_dir = os.path.join(root_pic_template_dir, "left")
        else:
            logger.error(f"[ERROR 提取数字] 无效的 'lorr' 参数: {lorr}. 必须是 'left' 或 'right'.")
            return None

        if not os.path.isdir(template_dir):
            logger.error(f"[ERROR 提取数字] 数字模板目录不存在: {template_dir}")
            return None

        valid_extensions = ('.png')
        tmpscore = 0.6 # Min score to be considered a digit
        digit_name = None
        for filename in sorted(os.listdir(template_dir)): 
            if filename.lower().endswith(valid_extensions):
                template_path = os.path.join(template_dir, filename)
                curscore = compare_score_iou(preprocessed_roi_otsu, template_path) # Use IOU score
                if curscore > tmpscore:
                    tmpscore = curscore
                    digit_name = os.path.splitext(filename)[0][0] 
        if tmpscore > 0.6: # Check against the initial min score
            return digit_name 
        else:
            # logger.info(f"[提取数字] {lorr} {template_dir} 中未找到>{0.6}的匹配模板。") # Can be noisy
            return None
                  
    except Exception as e:
        logger.error(f"[FATAL 提取数字] 处理ROI时发生严重错误: {e}")
        # import traceback # Keep for detailed debugging if needed
        # traceback.print_exc()
    return None


def read_number_two(frame, full_roi_x1, full_roi_y1, full_roi_x2, full_roi_y2, mid_split_x,
                    root_pic_template_dir, # Added
                    debug_image_prefix_base=None):
    left_debug_prefix = f"{debug_image_prefix_base}_left_digit" if debug_image_prefix_base else None
    right_debug_prefix = f"{debug_image_prefix_base}_right_digit" if debug_image_prefix_base else None

    digit1 = read_number_single(frame,full_roi_x1, full_roi_y1,
                                           mid_split_x, full_roi_y2,'left',
                                           root_pic_template_dir, # Pass through
                                           debug_image_prefix=left_debug_prefix)
    digit2 = read_number_single(frame,mid_split_x, full_roi_y1,
                                           full_roi_x2, full_roi_y2,'right',
                                           root_pic_template_dir, # Pass through
                                           debug_image_prefix=right_debug_prefix)
    if digit1 is not None and digit2 is not None:
        combined_number_str = f"{digit1}{digit2}"
        try:
            combined_number_int = int(combined_number_str)
            # logger.info(f"[提取两位数字] 成功组合数字: {combined_number_int}") # Can be noisy
            return combined_number_int
        except ValueError:
            logger.error(f"[提取两位数字] 组合后的字符串 '{combined_number_str}' 无法转换为整数。")
            return None
    else:
        return None


def find_shooting_moments(video_path,
                          root_pic_template_dir,
                          selected_weapon_names,
                          video_output_dir,
                          infinite_symbol_template_path,
                          weapon_activation_similarity_threshold,
                          similarity_threshold_infinite,
                          number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x,
                          weapon_roi_x1, weapon_roi_y1, weapon_roi_x2, weapon_roi_y2,
                          infinite_roi_x1, infinite_roi_y1, infinite_roi_x2, infinite_roi_y2,
                          coarse_interval_seconds=3.0,
                          fine_interval_seconds=0.1, start_time="00:00:00.000"):
    version_tag = "20250528_MultiWeaponLogic" # 更新版本标签
    logger.info(f"\n[{version_tag}] Initiating for video: {video_path}")
    logger.info(f"分析的武器: {selected_weapon_names}")
    logger.info(f"武器激活ROI (x1,y1,x2,y2): ({weapon_roi_x1},{weapon_roi_y1},{weapon_roi_x2},{weapon_roi_y2})")
    logger.info(f"武器激活阈值: {weapon_activation_similarity_threshold}")
    if "bow" in selected_weapon_names:
        logger.info(f"弓用无限符号模板: {os.path.basename(infinite_symbol_template_path)}, 阈值: {similarity_threshold_infinite}")
        logger.info(f"弓用无限符号ROI: ({infinite_roi_x1},{infinite_roi_y1},{infinite_roi_x2},{infinite_roi_y2})")
    logger.info(f"数字ROI (x1,y1,x2,y2,m): ({number_roi_x1},{number_roi_y1},{number_roi_x2},{number_roi_y2}, {mid_split_x}).")
    logger.info(f"粗扫描间隔: {coarse_interval_seconds}s, 精扫描间隔: {fine_interval_seconds}s. 开始时间: {start_time}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"错误: 无法打开视频 {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or fps is None:
        logger.error(f"错误: 无法读取视频FPS或FPS为0 {video_path}")
        cap.release()
        return
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        logger.error(f"错误: 视频总帧数为0 {video_path}")
        cap.release()
        return
    logger.info(f"视频 FPS: {fps}, 总帧数: {total_frames}")

    frame_skip_coarse = max(1, int(fps * coarse_interval_seconds))
    frame_skip_fine = max(1, int(fps * fine_interval_seconds))
    logger.info(f"粗步长: {frame_skip_coarse} frames, 精步长: {frame_skip_fine} frames")

    shooting_times_by_weapon = {name: [] for name in selected_weapon_names}
    prev_number_coarse_by_weapon = {name: 10000 for name in selected_weapon_names}
    prev_number_coarse_frame_by_weapon = {name: 0 for name in selected_weapon_names}
    last_known_active_frame_by_weapon = {name: 0 for name in selected_weapon_names}

    infinite_symbo_times_bow = []
    prev_frame_had_infinite_coarse_bow = False
    # prev_infinite_coarse_frame_bow = 0 # 似乎未使用，可以考虑移除

    current_frame_num = int(hms_to_seconds(start_time) * fps)
    last_coarse_log_frame = -frame_skip_coarse * 10 
    
    WRITE_TXT_COUNTS = 20 
    coarse_loop_iteration_counter = 0

    all_weapon_template_paths = {}
    # 确保 WEAPON_METADATA 是最新的，包含所有武器及其 'suffix'
    for name, meta in WEAPON_METADATA.items(): 
        path = os.path.join(root_pic_template_dir, f"template_{meta['suffix']}.png")
        if os.path.exists(path):
            all_weapon_template_paths[name] = path
        else:
            logger.warning(f"武器模板缺失: {path} for {name} (display: {meta.get('display_name', 'N/A')}). 该武器将无法被检测。")


    if not any(name in all_weapon_template_paths for name in selected_weapon_names):
        logger.error("所有选定武器的模板均缺失！无法继续分析。")
        cap.release()
        return

    roi_x1_w, roi_y1_w, roi_x2_w, roi_y2_w = int(weapon_roi_x1), int(weapon_roi_y1), int(weapon_roi_x2), int(weapon_roi_y2)

    while current_frame_num < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_num)
        ret, frame = cap.read()
        if not ret:
            logger.info(f"[Analysis 粗] Error reading frame {current_frame_num}. Ending.")
            break
        
        timestamp_sec = current_frame_num / fps
        if current_frame_num >= last_coarse_log_frame + (frame_skip_coarse * 5) : 
            active_prev_numbers_str = ", ".join([f"{name}: {prev_number_coarse_by_weapon.get(name, 'N/A')}" for name in selected_weapon_names])
            # logger.info(f"[Analysis 粗] : Frame {current_frame_num}/{total_frames} ({seconds_to_hms(timestamp_sec)})")
            logger.info(f"[Analysis 粗] : Frame {current_frame_num}/{total_frames} ({seconds_to_hms(timestamp_sec)}), 上个数字 (已选武器): {active_prev_numbers_str}")
            last_coarse_log_frame = current_frame_num

        active_weapon_name_this_frame = None
        max_iou_score = -1.0
        
        fh_frame, fw_frame = frame.shape[:2]
        if not (0 <= roi_x1_w < fw_frame and 0 <= roi_y1_w < fh_frame and \
                  roi_x1_w < roi_x2_w and roi_y1_w < roi_y2_w and \
                  roi_x2_w <= fw_frame and roi_y2_w <= fh_frame):
            logger.error(f"武器ROI坐标 ({roi_x1_w},{roi_y1_w},{roi_x2_w},{roi_y2_w}) 超出帧边界 ({fw_frame},{fh_frame}) on frame {current_frame_num}")
            current_frame_num += frame_skip_coarse
            coarse_loop_iteration_counter += 1
            continue 
        
        weapon_roi_current_frame = frame[roi_y1_w:roi_y2_w, roi_x1_w:roi_x2_w]
        if weapon_roi_current_frame.size == 0:
            logger.warning(f"提取的武器ROI为空 on frame {current_frame_num}")
            current_frame_num += frame_skip_coarse
            coarse_loop_iteration_counter += 1
            continue
            
        gray_weapon_roi = cv2.cvtColor(weapon_roi_current_frame, cv2.COLOR_BGR2GRAY)
        _, preprocessed_weapon_roi_otsu = cv2.threshold(gray_weapon_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        for w_name, w_template_path in all_weapon_template_paths.items():
            iou_score = compare_score_iou(preprocessed_weapon_roi_otsu, w_template_path)
            if iou_score > max_iou_score:
                max_iou_score = iou_score
                if iou_score > weapon_activation_similarity_threshold:
                    active_weapon_name_this_frame = w_name
                else:
                    active_weapon_name_this_frame = None 

        if active_weapon_name_this_frame and active_weapon_name_this_frame in selected_weapon_names:
            current_active_weapon_name = active_weapon_name_this_frame
            last_known_active_frame_by_weapon[current_active_weapon_name] = current_frame_num
            
            fine_scan_reason = None
            triggering_weapon_for_fine_scan = None
            
            current_number_coarse = read_number_two(frame, number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x, root_pic_template_dir)
            prev_number_for_this_weapon = prev_number_coarse_by_weapon[current_active_weapon_name]

            detected_shot_in_coarse = False
            if current_number_coarse is not None and prev_number_for_this_weapon is not None:
                if current_number_coarse != prev_number_for_this_weapon: # 基本的数字变化检测
                    detected_shot_in_coarse = True
            
            if detected_shot_in_coarse:
                fine_scan_reason = "shot"
                triggering_weapon_for_fine_scan = current_active_weapon_name
                logger.info(f"[Analysis 粗] Weapon '{current_active_weapon_name}' 数字变化触发精扫描 @ F{current_frame_num} ({seconds_to_hms(timestamp_sec)}). Num: {prev_number_for_this_weapon} -> {current_number_coarse}.")
            
            elif current_active_weapon_name == "bow" and WEAPON_METADATA["bow"]["has_infinite"]:
                is_infinite_active = check_roi_against_template(frame, infinite_symbol_template_path, 
                                                                infinite_roi_x1, infinite_roi_y1, infinite_roi_x2, infinite_roi_y2, 
                                                                threshold=similarity_threshold_infinite)
                if not prev_frame_had_infinite_coarse_bow and is_infinite_active:
                    fine_scan_reason = "infinite_bow"
                    triggering_weapon_for_fine_scan = "bow" 
                    bow_infinite_time = max(0, timestamp_sec) 
                    if bow_infinite_time not in infinite_symbo_times_bow:
                        infinite_symbo_times_bow.append(bow_infinite_time)
                        logger.info(f"[Analysis 粗] Bow ∞时刻 记录下 {seconds_to_hms(bow_infinite_time)} @ F{current_frame_num}.")
            
            if fine_scan_reason and triggering_weapon_for_fine_scan:
                fine_scan_start_frame = max(0, prev_number_coarse_frame_by_weapon[triggering_weapon_for_fine_scan]) 
                fine_scan_end_frame = min(total_frames - 1, current_frame_num)
                
                prev_number_fine_scan = current_number_coarse if fine_scan_reason == "shot" else -5 

                weapon_meta_fine_scan = WEAPON_METADATA.get(triggering_weapon_for_fine_scan, {})
                current_scan_logic = weapon_meta_fine_scan.get("scan_logic_type", "standard")

                logger.info(f"[Analysis 粗] 精扫描初始化 for '{triggering_weapon_for_fine_scan}' (Reason: {fine_scan_reason.upper()}, Logic: {current_scan_logic.upper()}): "
                            f"范围 [{fine_scan_start_frame}, {fine_scan_end_frame}] "
                            f"({seconds_to_hms(fine_scan_start_frame/fps)} to {seconds_to_hms(fine_scan_end_frame/fps)}). "
                            f"起始精扫数字: {prev_number_fine_scan}")

                weapon_template_for_fine_scan = all_weapon_template_paths.get(triggering_weapon_for_fine_scan)

                last_processed_fine_frame_rev = fine_scan_end_frame 
                for fn_fine in range(fine_scan_end_frame, max(0, fine_scan_end_frame - frame_skip_coarse - frame_skip_fine-1) , -frame_skip_fine):
                    if fn_fine < 0 or fn_fine >= last_processed_fine_frame_rev : break 
                    last_processed_fine_frame_rev = fn_fine
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fn_fine)
                    ret_f, frame_f = cap.read()
                    if not ret_f: continue
                    ts_fine_sec = fn_fine / fps

                    weapon_roi_fine = frame_f[roi_y1_w:roi_y2_w, roi_x1_w:roi_x2_w]
                    if weapon_roi_fine.size == 0: continue
                    gray_weapon_roi_fine = cv2.cvtColor(weapon_roi_fine, cv2.COLOR_BGR2GRAY)
                    _, prep_weapon_roi_otsu_fine = cv2.threshold(gray_weapon_roi_fine, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    is_trigger_weapon_active_fine = False
                    if weapon_template_for_fine_scan:
                         iou_fine = compare_score_iou(prep_weapon_roi_otsu_fine, weapon_template_for_fine_scan)
                         if iou_fine > weapon_activation_similarity_threshold:
                             is_trigger_weapon_active_fine = True
                    
                    if is_trigger_weapon_active_fine:
                        current_number_fine = read_number_two(frame_f, number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x, root_pic_template_dir)
                        if current_number_fine is not None:
                            shot_detected_reversed = False
                            if prev_number_fine_scan is not None:
                                if current_scan_logic == "standard":
                                    # prev_number_fine_scan is number at later time in video, current_number_fine is earlier
                                    if prev_number_fine_scan + 1 == current_number_fine:
                                        shot_detected_reversed = True
                                elif current_scan_logic == "rapid_fire":
                                    # current_number_fine (ammo earlier) - prev_number_fine_scan (ammo later) should be 1 to 3
                                    if 0 < (current_number_fine - prev_number_fine_scan) <= 3:
                                        shot_detected_reversed = True
                            
                            if shot_detected_reversed:
                                shot_time = max(0, ts_fine_sec - 0.3) 
                                if shot_time not in shooting_times_by_weapon[triggering_weapon_for_fine_scan]:
                                    shooting_times_by_weapon[triggering_weapon_for_fine_scan].append(shot_time)
                                    logger.info(f"[Analysis 精 ({current_scan_logic.upper()})] Weapon '{triggering_weapon_for_fine_scan}' 检测到射击! F {fn_fine} ({seconds_to_hms(ts_fine_sec)}). Num: {current_number_fine} -> {prev_number_fine_scan}. 记录: {seconds_to_hms(shot_time)}")
                            
                            if current_number_fine == prev_number_coarse_by_weapon[triggering_weapon_for_fine_scan] and fine_scan_reason == "shot":
                                logger.info(f"[Analysis 精 ({current_scan_logic.upper()})] 反向扫描时找到粗扫描的起始数字 {current_number_fine}. Weapon '{triggering_weapon_for_fine_scan}'.")
                                break 
                            prev_number_fine_scan = current_number_fine 
                
                prev_number_fine_scan_fwd = prev_number_coarse_by_weapon[triggering_weapon_for_fine_scan]
                logger.info(f"[Analysis 精 ({current_scan_logic.upper()})] 正向扫描开始. Weapon '{triggering_weapon_for_fine_scan}'. 上一个数字重置为: {prev_number_fine_scan_fwd}")
                
                for fn_fine in range(fine_scan_start_frame, min(min(total_frames,fine_scan_start_frame + frame_skip_coarse + frame_skip_fine + 1),last_processed_fine_frame_rev+1), frame_skip_fine):
                    if fn_fine < 0: continue
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fn_fine)
                    ret_f, frame_f = cap.read()
                    if not ret_f: continue
                    ts_fine_sec = fn_fine / fps
                    
                    weapon_roi_fine_fwd = frame_f[roi_y1_w:roi_y2_w, roi_x1_w:roi_x2_w]
                    if weapon_roi_fine_fwd.size == 0: continue
                    gray_weapon_roi_fine_fwd = cv2.cvtColor(weapon_roi_fine_fwd, cv2.COLOR_BGR2GRAY)
                    _, prep_weapon_roi_otsu_fine_fwd = cv2.threshold(gray_weapon_roi_fine_fwd, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    is_trigger_weapon_active_fine_fwd = False
                    if weapon_template_for_fine_scan:
                         iou_fine_fwd = compare_score_iou(prep_weapon_roi_otsu_fine_fwd, weapon_template_for_fine_scan)
                         if iou_fine_fwd > weapon_activation_similarity_threshold:
                             is_trigger_weapon_active_fine_fwd = True

                    if is_trigger_weapon_active_fine_fwd:
                        current_number_fine_fwd = read_number_two(frame_f, number_roi_x1, number_roi_y1, number_roi_x2, number_roi_y2, mid_split_x, root_pic_template_dir)
                        if current_number_fine_fwd is not None:
                            shot_detected_forward = False
                            if prev_number_fine_scan_fwd is not None: 
                                if current_scan_logic == "standard":
                                    # prev_number_fine_scan_fwd is number at earlier time, current_number_fine_fwd is later
                                    if prev_number_fine_scan_fwd - 1 == current_number_fine_fwd:
                                        shot_detected_forward = True
                                elif current_scan_logic == "rapid_fire":
                                    # prev_number_fine_scan_fwd (ammo earlier) - current_number_fine_fwd (ammo later) should be 1 to 3
                                    if 0 < (prev_number_fine_scan_fwd - current_number_fine_fwd) <= 3:
                                        shot_detected_forward = True
                            
                            if shot_detected_forward:
                                shot_time = max(0, ts_fine_sec - 0.3)
                                if shot_time not in shooting_times_by_weapon[triggering_weapon_for_fine_scan]:
                                    shooting_times_by_weapon[triggering_weapon_for_fine_scan].append(shot_time)
                                    logger.info(f"[Analysis 精 ({current_scan_logic.upper()})] Weapon '{triggering_weapon_for_fine_scan}' 检测到射击! F {fn_fine} ({seconds_to_hms(ts_fine_sec)}). Num: {prev_number_fine_scan_fwd} -> {current_number_fine_fwd}. 记录: {seconds_to_hms(shot_time)}")
                            
                            if current_number_fine_fwd == current_number_coarse and fine_scan_reason == "shot": 
                                logger.info(f"[Analysis 精 ({current_scan_logic.upper()})] 正向扫描时找到粗扫描的结束数字 {current_number_fine_fwd}. Weapon '{triggering_weapon_for_fine_scan}'.")
                                break 
                            prev_number_fine_scan_fwd = current_number_fine_fwd
            
            if current_number_coarse is not None:
                prev_number_coarse_by_weapon[current_active_weapon_name] = current_number_coarse
                prev_number_coarse_frame_by_weapon[current_active_weapon_name] = current_frame_num
            
            if current_active_weapon_name == "bow" and WEAPON_METADATA["bow"]["has_infinite"] and fine_scan_reason == "infinite_bow": # This was already specific to bow infinite detection
                prev_frame_had_infinite_coarse_bow = True 
                # prev_infinite_coarse_frame_bow = current_frame_num # Re-consider if this is needed
            elif current_active_weapon_name == "bow": 
                prev_frame_had_infinite_coarse_bow = False
        
        else: # No weapon active, or active weapon not selected by user
            # This logic ensures that if the bow was showing infinite, and then ceases to be the active weapon,
            # the infinite flag is reset. This seems reasonable.
            if prev_frame_had_infinite_coarse_bow and active_weapon_name_this_frame != "bow":
               prev_frame_had_infinite_coarse_bow = False
               # logger.debug(f"[Analysis 粗] Bow不再是激活武器或未被选择, 重置无限符号标记 @ F{current_frame_num}")


        if coarse_loop_iteration_counter > 0 and coarse_loop_iteration_counter % WRITE_TXT_COUNTS == 0:
            for w_name_selected in selected_weapon_names:
                if shooting_times_by_weapon[w_name_selected]:
                    current_shooting_output_txt_path = os.path.join(video_output_dir, f"shooting_{WEAPON_METADATA[w_name_selected]['suffix']}.txt") # Use suffix for filename consistency if desired, or just w_name_selected
                    unique_times_to_write = list(set(shooting_times_by_weapon[w_name_selected]))
                    
                    # Read existing times to avoid duplicates if appending, or ensure overwrite is intended.
                    # Current final write logic overwrites, so periodic append is okay.
                    with open(current_shooting_output_txt_path, 'a', encoding='utf-8') as f: 
                        for t_shot in unique_times_to_write:
                            f.write(f"{seconds_to_hms(t_shot)}\n")
                    logger.info(f"写入 {len(unique_times_to_write)} 个 {w_name_selected} 射击时刻到 {current_shooting_output_txt_path} (临时)")
                    shooting_times_by_weapon[w_name_selected].clear() 

            if "bow" in selected_weapon_names and WEAPON_METADATA["bow"]["has_infinite"] and infinite_symbo_times_bow:
                current_infinite_output_txt_path = os.path.join(video_output_dir, "infinite.txt") 
                unique_inf_times = list(set(infinite_symbo_times_bow))
                with open(current_infinite_output_txt_path, 'a', encoding='utf-8') as f: 
                    for t_inf in unique_inf_times:
                        f.write(f"{seconds_to_hms(t_inf)}\n")
                logger.info(f"写入 {len(unique_inf_times)} 个 Bow ∞ 时刻到 {current_infinite_output_txt_path} (临时)")
                infinite_symbo_times_bow.clear()

        coarse_loop_iteration_counter += 1
        current_frame_num += frame_skip_coarse

    cap.release()

    all_combined_shooting_times = [] 

    for w_name_final in selected_weapon_names:
        # Use weapon's suffix from WEAPON_METADATA for the output filename, or just w_name_final if preferred
        # Original code in GUI uses `shooting_{weapon_name_to_clip}.txt` where weapon_name_to_clip is the internal key.
        # For consistency, let's stick to internal key for filename.
        final_shooting_output_txt_path = os.path.join(video_output_dir, f"shooting_{w_name_final}.txt")
        existing_times_sec = []
        if os.path.exists(final_shooting_output_txt_path):
            try:
                with open(final_shooting_output_txt_path, 'r', encoding='utf-8') as f_read:
                    for line in f_read:
                        line = line.strip()
                        if line: existing_times_sec.append(hms_to_seconds(line))
            except Exception as e:
                logger.error(f"读取现有时间文件 {final_shooting_output_txt_path} 失败: {e}")

        combined_w_times = shooting_times_by_weapon[w_name_final] + existing_times_sec
        unique_shooting_times_w = sorted(list(set(combined_w_times)))

        if not unique_shooting_times_w:
            logger.info(f"武器 '{w_name_final}' 没有检测到射击时刻。{final_shooting_output_txt_path} 将为空或不创建。")
            if os.path.exists(final_shooting_output_txt_path): 
                try: 
                    # Only remove if it's truly empty or only contains whitespace after this session
                    if os.path.getsize(final_shooting_output_txt_path) == 0:
                        os.remove(final_shooting_output_txt_path)
                    else: # Check content if not zero size
                        with open(final_shooting_output_txt_path, 'r', encoding='utf-8') as f_check:
                            if not f_check.read().strip():
                                os.remove(final_shooting_output_txt_path)

                except OSError as e: logger.error(f"无法删除空的 {final_shooting_output_txt_path}: {e}")
        else:
            logger.info(f"武器 '{w_name_final}' 检测到 {len(unique_shooting_times_w)} 个独立射击时刻。")
            with open(final_shooting_output_txt_path, 'w', encoding='utf-8') as f:
                for t_shot in unique_shooting_times_w:
                    f.write(f"{seconds_to_hms(t_shot)}\n")
            logger.info(f"{w_name_final} 射击时刻已保存到: {final_shooting_output_txt_path}")
            all_combined_shooting_times.extend(unique_shooting_times_w) 

    if all_combined_shooting_times:
        unique_all_weapons_times = sorted(list(set(all_combined_shooting_times)))
        all_weapons_txt_path = os.path.join(video_output_dir, "all_weapons.txt")
        with open(all_weapons_txt_path, 'w', encoding='utf-8') as f_all:
            for t_shot_all in unique_all_weapons_times:
                f_all.write(f"{seconds_to_hms(t_shot_all)}\n")
        logger.info(f"所有选定武器的 {len(unique_all_weapons_times)} 个射击时刻已合并保存到: {all_weapons_txt_path}")
    else:
        logger.info("没有为任何选定武器检测到射击时刻，all_weapons.txt 将不被创建。")
        all_weapons_txt_path = os.path.join(video_output_dir, "all_weapons.txt")
        if os.path.exists(all_weapons_txt_path):
            try: os.remove(all_weapons_txt_path)
            except OSError as e: logger.error(f"无法删除空的 all_weapons.txt: {e}")


    if "bow" in selected_weapon_names and WEAPON_METADATA["bow"]["has_infinite"]:
        final_infinite_output_txt_path = os.path.join(video_output_dir, "infinite.txt") 
        existing_inf_times_sec = []
        if os.path.exists(final_infinite_output_txt_path):
            try:
                with open(final_infinite_output_txt_path, 'r', encoding='utf-8') as f_read_inf:
                    for line in f_read_inf:
                        line = line.strip()
                        if line: existing_inf_times_sec.append(hms_to_seconds(line))
            except Exception as e:
                 logger.error(f"读取现有无限时间文件 {final_infinite_output_txt_path} 失败: {e}")
        
        combined_inf_times = infinite_symbo_times_bow + existing_inf_times_sec
        unique_infinite_start_times_bow = sorted(list(set(combined_inf_times)))

        if not unique_infinite_start_times_bow:
            logger.info(f"没有检测到Bow ∞ 大符号开始时刻。{final_infinite_output_txt_path} 将为空或不创建。")
            if os.path.exists(final_infinite_output_txt_path):
                try: 
                    if os.path.getsize(final_infinite_output_txt_path) == 0:
                        os.remove(final_infinite_output_txt_path)
                    else:
                         with open(final_infinite_output_txt_path, 'r', encoding='utf-8') as f_check_inf:
                            if not f_check_inf.read().strip():
                                os.remove(final_infinite_output_txt_path)
                except OSError as e: logger.error(f"无法删除空的 {final_infinite_output_txt_path}: {e}")
        else:
            logger.info(f"检测到 {len(unique_infinite_start_times_bow)} 个Bow ∞ 大符号开始时刻。")
            with open(final_infinite_output_txt_path, 'w', encoding='utf-8') as f:
                for t_inf_start in unique_infinite_start_times_bow:
                    f.write(f"{seconds_to_hms(t_inf_start)}\n")
            logger.info(f"Bow ∞ 大符号开始时刻已保存到: {final_infinite_output_txt_path}")

    logger.info(f"Video {video_path} analysis COMPLETED ({version_tag}).")