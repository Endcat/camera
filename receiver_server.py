from flask import Flask, request, Response, render_template_string
import base64
import cv2
import numpy as np
import threading
import time

app = Flask(__name__)

# 全局变量存储最新的帧
latest_frame = None
frame_lock = threading.Lock()
last_received_time = 0

# HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>FaceTime Camera</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            margin: 20px;
        }
        #video-container {
            margin: 20px auto;
            max-width: 960px;
        }
        img {
            width: 100%;
            max-width: 960px;
            border: 1px solid #ddd;
        }
        .info {
            margin: 10px 0;
            padding: 5px;
            background-color: #f0f0f0;
        }
    </style>
    <meta http-equiv="refresh" content="300"> <!-- 每5分钟刷新一次页面以保持连接 -->
</head>
<body>
    <h1>FaceTime Camera</h1>
    <div class="info">状态: <span id="status">等待连接...</span></div>
    <div id="video-container">
        <img src="/video_feed" width="960" height="540" />
    </div>
    
    <script>
        // 检测连接状态
        function checkConnection() {
            fetch('/connection_status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').textContent = data.status;
                    document.getElementById('status').style.color = 
                        data.connected ? 'green' : 'red';
                })
                .catch(err => {
                    document.getElementById('status').textContent = 
                        '连接错误: ' + err;
                    document.getElementById('status').style.color = 'red';
                });
        }
        
        // 定期检查连接状态
        setInterval(checkConnection, 2000);
        checkConnection();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/receive_frame', methods=['POST'])
def receive_frame():
    """接收从摄像头设备发送的帧"""
    global latest_frame, last_received_time
    
    if request.json and 'frame' in request.json:
        # 获取 base64 编码的帧并解码
        frame_data = request.json['frame']
        jpg_data = base64.b64decode(frame_data)
        
        # 解码为 OpenCV 图像
        try:
            img_array = np.frombuffer(jpg_data, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            # 更新全局帧
            with frame_lock:
                latest_frame = frame
                last_received_time = time.time()
            
            return {"status": "success"}, 200
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400
    else:
        return {"status": "error", "message": "No frame data"}, 400

@app.route('/video_feed')
def video_feed():
    """生成 MJPEG 流供网页显示"""
    def generate_frames():
        global latest_frame
        while True:
            with frame_lock:
                if latest_frame is not None:
                    frame_copy = latest_frame.copy()
                    ret, buffer = cv2.imencode('.jpg', frame_copy)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               frame_bytes + b'\r\n')
            time.sleep(0.03)  # ~30 fps
    
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/connection_status')
def connection_status():
    """返回摄像头连接状态"""
    global last_received_time
    current_time = time.time()
    connected = (current_time - last_received_time < 3.0)  # 3秒内有接收帧就算连接正常
    
    status = "已连接" if connected else "未连接或连接中断"
    return {"connected": connected, "status": status}

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='视频帧接收服务器')
    parser.add_argument('--port', type=int, default=8000, 
                        help='服务器端口 (默认: 8000)')
    
    args = parser.parse_args()
    
    print(f"接收服务器启动在端口 {args.port}...")
    app.run(host='0.0.0.0', port=args.port, threaded=True)