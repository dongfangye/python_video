import os
import cv2
import numpy as np
import pyaudio
import wave
import threading
import time
import signal
import sys
from moviepy.editor import VideoFileClip, AudioFileClip

# 播放音频文件(音频文件路径，停止事件, 倍数播放)
def play_audio(audio_file, stop_event, start_time=0, fast_forward_event=None, speed_factor=1.0):
    wf = wave.open(audio_file, 'rb')  # 打开音频文件
    # 创建音频流
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=int(wf.getframerate() * speed_factor),  # 调整播放速率
                    output=True)

    chunk = 1024
    wf.setpos(int(start_time * wf.getframerate()))  # 定位到开始位置
    data = wf.readframes(chunk)  # 读取数据

    # 播放音频
    while data and not stop_event.is_set():
        if fast_forward_event and fast_forward_event.is_set():
            start_time += 10
            wf.setpos(int(start_time * wf.getframerate()))
            fast_forward_event.clear()
        stream.write(data)
        data = wf.readframes(chunk)

    # 停止和关闭音频流
    stream.stop_stream()
    stream.close()
    p.terminate()

# 从视频中提取音频并保存为临时文件(输入视频文件路径，保存的音频文件路径)
def extract_audio(video_file, audio_file):
    video = VideoFileClip(video_file)
    video.audio.write_audiofile(audio_file)  # 提取并保存音频文件

# 播放视频(视频文件路径，停止事件，窗口名称，窗口大小, 放大比例)
def play_video(video_file, stop_event, window_name, window_size, zoom_factor=1.0, start_time=0, fast_forward_event=None, speed_factor=1.0):
    cap = cv2.VideoCapture(video_file)
    fps = cap.get(cv2.CAP_PROP_FPS) * speed_factor  # 调整播放速率
    frame_time = 1.0 / fps

    cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, window_size[0], window_size[1])

    current_time = start_time
    while cap.isOpened() and not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            return "finished", current_time, speed_factor

        # 获取原始帧的尺寸
        height, width, channels = frame.shape
        new_height, new_width = int(height / zoom_factor), int(width / zoom_factor)

        # 计算中心区域
        y1 = (height - new_height) // 2
        y2 = y1 + new_height
        x1 = (width - new_width) // 2
        x2 = x1 + new_width

        # 裁剪中心区域
        frame_cropped = frame[y1:y2, x1:x2]
        frame_zoomed = cv2.resize(frame_cropped, window_size)

        cv2.imshow(window_name, frame_zoomed)

        elapsed_time = time.time() - start_time
        sleep_time = frame_time - (elapsed_time % frame_time)
        if sleep_time > 0:
            time.sleep(sleep_time)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            stop_event.set()
            return "stop", current_time, speed_factor
        elif key == ord('a'):
            return "previous", current_time, speed_factor
        elif key == ord('d'):
            return "next", current_time, speed_factor
        elif key == ord('w'):
            zoom_factor += 1.0
        elif key == ord('s'):
            zoom_factor -= 1.0
            if zoom_factor < 1.0:
                zoom_factor = 1.0
        elif key == ord('c'):
            current_time += 10
            cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
            if fast_forward_event:
                fast_forward_event.set()
        elif key == ord('p'):
            if speed_factor == 1.0:
                speed_factor = 2.0
            else:
                speed_factor = 1.0
            # Continue with current_time and updated speed_factor
            return "speed_change", current_time, speed_factor

    cap.release()
    cv2.destroyAllWindows()
    return "stop", current_time, speed_factor

def signal_handler(sig, frame):
    print("Interrupt received, stopping...")
    stop_event.set()
    audio_thread.join()
    sys.exit(0)

if __name__ == "__main__":
    video_files = ["video.mp4", "video2.mp4"]
    audio_files = list()
    for tmp in video_files:
        name = tmp.split('.')[0]
        audio_files.append(name + '.wav')

    for indx, val in enumerate(audio_files):
        if not os.path.exists(val):
            extract_audio(video_files[indx], audio_files[indx])  # 从视频中提取音频并保存为临时文件

    stop_event = threading.Event()
    signal.signal(signal.SIGINT, signal_handler)

    fast_forward_event = threading.Event()
    current_video_indx = 0
    zoom_factor = 1.0
    start_time = 0
    speed_factor = 1.0

    while 0 <= current_video_indx < len(video_files):
        video = video_files[current_video_indx]
        audio = audio_files[current_video_indx]

        stop_event.clear()  # 复位停止事件
        audio_thread = threading.Thread(target=play_audio, args=(audio, stop_event, start_time, fast_forward_event, speed_factor))
        audio_thread.start()
        window_name = 'Video'
        window_size = (800, 600)
        result, current_time, speed_factor = play_video(video, stop_event, window_name, window_size, zoom_factor, start_time, fast_forward_event, speed_factor)

        stop_event.set()  # 停止播放音频文件
        audio_thread.join()

        if result == "next":
            current_video_indx += 1
            start_time = 0
        elif result == "previous":
            current_video_indx -= 1
            start_time = 0
        elif result == "finished":
            current_video_indx += 1
            start_time = 0
        elif result == "speed_change":
            start_time = current_time  # Keep current_time unchanged
        elif result == "stop":
            break
        else:
            start_time = current_time

    print("all video finished")