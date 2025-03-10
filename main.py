import cv2
from flask import Flask, Response
import threading
import time

app = Flask(__name__)

# 全局变量存储最新的帧
global_frame = None
frame_lock = threading.Lock()

def generate_frames():
    global global_frame
    while True:
        with frame_lock:
            if global_frame is None:
                continue
            # 将帧编码为 JPEG 格式
            ret, buffer = cv2.imencode('.jpg', global_frame)
            if not ret:
                continue
        # 以 MJPEG 流格式传输帧
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.03)  # ~30 fps

@app.route('/')
def index():
    return """
    <html>
    <head>
        <title>FaceTime 摄像头流</title>
    </head>
    <body>
        <h1>FaceTime 摄像头流</h1>
        <img src="/video_feed" width="640" height="480" />
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def access_camera():
    global global_frame
    # 初始化摄像头，0表示默认摄像头（FaceTime摄像头）
    cap = cv2.VideoCapture(0)
    
    # 检查摄像头是否成功打开
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    print("摄像头已打开，按 Ctrl+C 停止程序")
    
    try:
        while True:
            # 读取一帧
            ret, frame = cap.read()
            
            # 如果读取失败，跳出循环
            if not ret:
                print("无法读取摄像头帧")
                break
            
            # 更新全局帧
            with frame_lock:
                global_frame = frame.copy()
            
            # 添加短暂延迟，减少 CPU 使用
            time.sleep(0.03)  # ~30 fps
    finally:
        # 释放资源
        cap.release()

def main():
    # 启动摄像头线程
    camera_thread = threading.Thread(target=access_camera)
    camera_thread.daemon = True
    camera_thread.start()
    
    # 启动Flask服务器
    print("启动Web服务器，在浏览器中访问 http://[本机IP]:8000/")
    app.run(host='0.0.0.0', port=8000, debug=False)

if __name__ == "__main__":
    main()