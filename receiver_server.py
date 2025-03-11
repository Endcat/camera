from flask import Flask, request, Response, render_template_string
import base64
import cv2
import numpy as np
import threading
import time
import json
from flask_sock import Sock  # 需要安装: pip install flask-sock

app = Flask(__name__)
sock = Sock(app)

# 全局变量存储最新的帧
latest_frame = None
frame_lock = threading.Lock()
last_received_time = 0
frames_received = 0
start_time = time.time()

# HTML模板 - 更新使用 WebSocket
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>摄像头接收器</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            margin: 20px;
            background-color: #f5f5f5;
        }
        #video-container {
            margin: 20px auto;
            max-width: 800px;
        }
        #camera-feed {
            width: 100%;
            max-width: 640px;
            border: 2px solid #007bff;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .info {
            margin: 10px auto;
            padding: 10px;
            background-color: #ffffff;
            border-radius: 5px;
            width: fit-content;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        h1 {
            color: #007bff;
        }
        .stats {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 15px 0;
        }
        .stat-box {
            padding: 8px 15px;
            background-color: #e9ecef;
            border-radius: 4px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>FaceTime 摄像头流</h1>
    
    <div class="stats">
        <div class="stat-box">状态: <span id="status">等待连接...</span></div>
        <div class="stat-box">帧率: <span id="fps">0</span> FPS</div>
    </div>
    
    <div id="video-container">
        <img id="camera-feed" src="" alt="等待视频流..." />
    </div>
    
    <script>
        // 获取DOM元素
        const cameraFeed = document.getElementById('camera-feed');
        const statusElement = document.getElementById('status');
        const fpsElement = document.getElementById('fps');
        
        // WebSocket连接
        const ws = new WebSocket(`ws://${window.location.host}/ws_client`);
        
        // 帧计数和FPS计算
        let frameCount = 0;
        let lastTime = Date.now();
        
        // 定期计算和显示FPS
        setInterval(() => {
            const now = Date.now();
            const elapsed = now - lastTime;
            
            if (elapsed > 0) {
                const fps = frameCount * 1000 / elapsed;
                fpsElement.textContent = fps.toFixed(1);
                frameCount = 0;
                lastTime = now;
            }
        }, 1000);
        
        // WebSocket事件处理
        ws.onopen = function() {
            statusElement.textContent = "已连接";
            statusElement.style.color = "green";
        };
        
        ws.onmessage = function(event) {
            try {
                // 接收图像数据并显示
                cameraFeed.src = "data:image/jpeg;base64," + event.data;
                frameCount++;
            } catch (error) {
                console.error("处理图像时出错:", error);
            }
        };
        
        ws.onclose = function() {
            statusElement.textContent = "连接已关闭";
            statusElement.style.color = "red";
            // 尝试重新连接
            setTimeout(() => {
                location.reload();
            }, 3000);
        };
        
        ws.onerror = function(error) {
            statusElement.textContent = "连接错误";
            statusElement.style.color = "red";
            console.error("WebSocket错误:", error);
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@sock.route('/ws')
def ws_camera(ws):
    """接收从摄像头发送的WebSocket连接"""
    global latest_frame, last_received_time, frames_received
    
    print("摄像头WebSocket连接已建立")
    
    try:
        while True:
            data = ws.receive()
            try:
                # 解析JSON数据
                message = json.loads(data)
                if 'frame' in message:
                    # 解码base64图像
                    jpg_data = base64.b64decode(message['frame'])
                    
                    # 转换为OpenCV图像
                    img_array = np.frombuffer(jpg_data, dtype=np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    # 更新全局帧
                    with frame_lock:
                        latest_frame = frame
                        last_received_time = time.time()
                        frames_received += 1
                        
            except Exception as e:
                print(f"处理摄像头帧时出错: {e}")
    except Exception as e:
        print(f"摄像头WebSocket连接断开: {e}")

@sock.route('/ws_client')
def ws_client(ws):
    """向客户端浏览器发送视频流"""
    global latest_frame
    try:
        while True:
            with frame_lock:
                if latest_frame is not None:
                    frame_copy = latest_frame.copy()
                    # 添加时间戳
                    cv2.putText(
                        frame_copy, 
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.8, 
                        (0, 255, 0), 
                        2
                    )
                    ret, buffer = cv2.imencode('.jpg', frame_copy, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        # 发送Base64编码的图像数据给客户端
                        ws.send(base64.b64encode(buffer).decode('utf-8'))
            
            # 短暂休眠避免过高的CPU使用率
            time.sleep(0.01)
    except Exception as e:
        print(f"客户端WebSocket连接断开: {e}")

# 添加统计线程来监控接收帧率
def monitor_fps():
    global frames_received, start_time
    
    while True:
        time.sleep(5)
        elapsed = time.time() - start_time
        if elapsed > 0:
            fps = frames_received / elapsed
            print(f"平均接收帧率: {fps:.2f} FPS")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='WebSocket视频接收服务器')
    parser.add_argument('--port', type=int, default=8000, help='服务器端口 (默认: 8000)')
    
    args = parser.parse_args()
    
    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_fps)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print(f"接收服务器启动在端口 {args.port}...")
    app.run(host='0.0.0.0', port=args.port, threaded=True)