import os

def list_png_files(folder_path):
    # 获取所有以 .png 结尾的文件名
    png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]
    # 用逗号连接并打印
    print(','.join(png_files))

# 示例用法（你可以修改为实际路径或使用 input() 获取路径）
# folder_path = "C:/Users/YourName/Pictures"
folder_path = input("请输入文件夹路径：")
list_png_files(folder_path)
