import cv2
import requests
import numpy as np
import time
import threading
import json
import base64
import argparse

class CameraSender:
    def __init__(self, target_ip, target_port=8000, fps=60):
        self.target_url = f"http://{target_ip}:{target_port}/receive_frame"
        self.cap = None
        self.running = False
        self.fps = fps
        self.frame_interval = 1.0 / fps
        
    def start_camera(self):
        """启动摄像头并开始发送帧"""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("无法打开摄像头")
            return False
            
        print(f"摄像头已打开，开始发送帧到 {self.target_url}")
        self.running = True
        
        # 创建发送线程
        send_thread = threading.Thread(target=self.send_frames)
        send_thread.daemon = True
        send_thread.start()
        return True
        
    def send_frames(self):
        """持续发送视频帧到目标服务器"""
        last_time = time.time()
        
        while self.running:
            current_time = time.time()
            # 控制帧率
            if current_time - last_time < self.frame_interval:
                time.sleep(0.001)  # 小休眠避免 CPU 100%
                continue
                
            ret, frame = self.cap.read()
            if not ret:
                print("无法读取摄像头帧")
                time.sleep(1)
                continue
                
            # 压缩图像质量以减小数据传输量
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
            if not ret:
                continue
                
            # 编码为 base64 以便于 HTTP 传输
            frame_data = base64.b64encode(jpeg).decode('utf-8')
            
            try:
                # 发送帧到目标服务器
                response = requests.post(
                    self.target_url, 
                    json={"frame": frame_data},
                    timeout=1
                )
                if response.status_code == 200:
                    print(".", end="", flush=True)
                else:
                    print(f"发送失败: {response.status_code}")
            except Exception as e:
                print(f"发送错误: {str(e)}")
            
            last_time = time.time()
    
    def stop(self):
        """停止摄像头并释放资源"""
        self.running = False
        time.sleep(0.5)
        if self.cap:
            self.cap.release()
        print("\n摄像头已关闭")

def main():
    parser = argparse.ArgumentParser(description="FaceTime 摄像头发送器")
    parser.add_argument("--ip", required=True, help="目标主机 IP 地址")
    parser.add_argument("--port", type=int, default=8000, help="目标主机端口")
    parser.add_argument("--fps", type=int, default=60, help="发送帧率")
    
    args = parser.parse_args()
    
    sender = CameraSender(args.ip, args.port, args.fps)
    try:
        if sender.start_camera():
            print("按 Ctrl+C 停止发送")
            # 主线程保持运行
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在停止...")
    finally:
        sender.stop()

if __name__ == "__main__":
    main()