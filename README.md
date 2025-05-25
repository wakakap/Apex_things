# Apex_things

## 下载视频

显示信息
```bash
yt-dlp -F https://www.youtube.com/watch?v=ID
```

bash用
```bash
yt-dlp "https://www.twitch.tv/videos/xxxxxx" -o "E:\xxxx\xxxx\xxxxx.mp4" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" --download-sections "*00:17:00-05:02:10"
```
python用
```python
command = [
        'yt-dlp', video_url,
        '-f', "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        '-o', file_mp4,
        '--merge-output-format', 'mp4',
        '--download-sections', f"*{start_time}-{end_time}"
]
downloaded_file_path = subprocess.run(command, check=True, text=True, capture_output=True, encoding='utf-8')
```

偶尔会有无法续传的情况，经验上bash会好一点。如果发现下载停止，可以不关bash，把网重新连一下续传概率更高。

## 目录结构
```
root_directory/
├── pic_template/
│   ├── template.png  # 弓箭图片
│   ├── template2.png # 无穷图片
│   ├── left/
│   │   ├── 0l.png
│   │   ├── 1l.png
│   │   ├── 2l.png
│   │   ├── 3l.png
│   │   └── 4l.png
│   └── right/
│       ├── 0r.png
│       ├── 1r.png
│       ├── 2r.png
│       ├── 3r.png
│       ├── 4r.png
│       ├── 5r.png
│       ├── 6r.png
│       ├── 7r.png
│       ├── 8r.png
│       └── 9r.png
├── downloaded_videos/
├── clips_output/
│   └── 2462742265/
│       ├── shooting_bow.txt
│       ├── infinite.txt
│       ├── infinite_2.txt
│       ├── infinite_3.txt
│       └── shooting_bow_sum.txt
```

## 使用说明

- 下载视频直接用 `bash` 更推荐
- 如果用本工具下载视频，`video_urls.txt`用于决定要下载哪些视频。每行格式为`https://www.twitch.tv/videos/xxxxxx,02:29:30.000,05:37:10.000`下载完成后，之后的处理中的时间戳都已本地视频为准，而不是原网络视频的时间。下载和处理两个部分互相独立。
- `pic_template`文件夹里存储模板图片，要放到主路径中。弓箭对应`template.png` 无穷符号对应`template2.png`。`pic_template\left` 存储左侧的数字，右侧的同理。
- 点击 `Refresh Video List` 勾选要进行处理的视频
- infinite是老爷爷大招的时间检测，为粗略时间统计在infinite.txt中。手动查看infinite.txt然后以每行`01:00:03.000 - 01:00:57.000`的格式写出要的时间范围，保存为`infinite_2.txt`，为给part4处理。然后把这些片段拖到Pr中，确定每一法的精确时间，以每行`02:48:11.000 - 00:00:09:04 00:00:10:14 00:00:11:11 00:00:20:16`的格式保存为`infinite_3.txt`，然后给part5处理，得到所有发射的总记录文件`shooting_bow_sum.txt`。如果不想麻烦处理infinite问题，只需要前两步即可。

## 备注

- 没有写到界面里的参数：shooting_time = max(0, t_fine_shot - 0.3) # 用于记录的时间提前一点0.3
- 未来需要把武器名称分开命名，让本工具适用于其他单发武器。
- 之所以数字识别时采用打分最高的，而不是直接一个阈值超过则识别的形式，是因为3，0，9，8等数字很相像，得分都很高。即使用打分最高的这种方法也偶尔会出问题。识别精确问题需要改善。
- audio_approach 不太精准，先搁置。
