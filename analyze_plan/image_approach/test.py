import cv2

from analysis_functions import (
    read_number_single,
    read_number_two,
    compare_twovalue
)

if __name__ == '__main__':
    image_path = "E:\\mande\\0_PLAN\\pic_template\\test32.png"
    yrm_path = "E:\\mande\\0_PLAN\\pic_template\\template.png"
    # 1. 使用 cv2.imread() 加载图像
    loaded_frame = cv2.imread(image_path)

    # 2. 检查图像是否成功加载
    if loaded_frame is None:
        print(f"错误：无法加载图像 {image_path}。请检查文件路径和文件是否损坏。")
    else:
        print(f"图像 {image_path} 加载成功，类型: {type(loaded_frame)}, 形状: {loaded_frame.shape}")
        
        # 假设这是您为 "1.jpg" 右下角数字区域定义的ROI坐标 (这些值需要您根据实际图像调整)
        # 例如，对于 "1.jpg" 中右下角的 "24"，大致坐标可能是：
        # (请根据实际情况精确调整这些坐标)
        BOW_ROI_X1 = 1554
        BOW_ROI_Y1 = 958
        BOW_ROI_X2 = 1702
        BOW_ROI_Y2 = 998
        NUMBER_ROI_X1 = 1723
        NUMBER_ROI_Y1 = 958
        NUMBER_ROI_X2 = 1787
        NUMBER_ROI_Y2 = 1002
        NUMBER_MID = 1754
        # 3. 将加载后的图像对象 (loaded_frame) 传递给函数
        extracted_num = read_number_two(
            loaded_frame, 
            NUMBER_ROI_X1, NUMBER_ROI_Y1, 
            NUMBER_ROI_X2, NUMBER_ROI_Y2, NUMBER_MID
            # debug_image_prefix="E:\\mande\\0_PLAN\\pic_template\\de" # 指定保存调试图像的前缀和路径
        )

        if extracted_num is not None:
            print(f"成功提取数字: {extracted_num}")
        else:
            print("提取数字失败。")