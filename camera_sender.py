# 替代方案：使用 websockets 库
import asyncio
import websockets
import cv2
import base64
import json
import argparse
import time
import threading

class CameraSender:
    def __init__(self, target_ip, target_port=8000, fps=60, quality=85):
        self.ws_url = f"ws://{target_ip}:{target_port}/ws"
        self.cap = None
        self.running = False
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.quality = quality
        self.frames_sent = 0
        self.start_time = 0
        
    def start_camera(self):
        """启动摄像头并开始发送帧"""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("无法打开摄像头")
            return False
            
        # 设置较低分辨率提高传输速度
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.running = True
        self.start_time = time.time()
        self.frames_sent = 0
        
        # 创建异步事件循环和任务
        event_loop = asyncio.new_event_loop()
        
        # 在新线程中运行异步循环
        def run_async_loop():
            asyncio.set_event_loop(event_loop)
            event_loop.run_until_complete(self.send_frames_async())
        
        thread = threading.Thread(target=run_async_loop)
        thread.daemon = True
        thread.start()
        
        # 创建帧率监控线程
        monitor_thread = threading.Thread(target=self.monitor_fps)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return True
    
    async def send_frames_async(self):
        """异步发送视频帧"""
        last_time = time.time()
        skip_count = 0
        
        while True:
            try:
                # 尝试连接WebSocket
                print(f"正在连接到 {self.ws_url}...")
                async with websockets.connect(self.ws_url) as ws:
                    print("WebSocket连接已建立")
                    
                    while self.running:
                        current_time = time.time()
                        # 控制帧率
                        if current_time - last_time < self.frame_interval:
                            await asyncio.sleep(0.001)
                            continue
                        
                        if not self.cap.isOpened():
                            await asyncio.sleep(0.5)
                            continue
                            
                        ret, frame = self.cap.read()
                        if not ret:
                            print("无法读取摄像头帧")
                            await asyncio.sleep(0.5)
                            continue
                            
                        # 压缩图像
                        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                        if not ret:
                            continue
                            
                        # 跳过部分帧如果处理太慢
                        if skip_count > 0:
                            skip_count -= 1
                            continue
                            
                        # 编码为base64
                        frame_data = base64.b64encode(jpeg).decode('utf-8')
                        
                        try:
                            message = json.dumps({"frame": frame_data})
                            await ws.send(message)
                            print(".", end="", flush=True)
                            self.frames_sent += 1
                        except Exception as e:
                            print(f"\n发送错误: {str(e)}")
                            break
                            
                        # 自适应帧率控制
                        processing_time = time.time() - current_time
                        if processing_time > self.frame_interval:
                            frames_to_skip = int(processing_time / self.frame_interval)
                            skip_count = min(frames_to_skip, 5)
                            
                        last_time = time.time()
                
            except Exception as e:
                print(f"WebSocket连接错误: {e}")
                if not self.running:
                    break
                await asyncio.sleep(2)  # 等待2秒后重试连接
    
    def monitor_fps(self):
        """监控实际发送帧率"""
        while self.running:
            time.sleep(5)  # 每5秒报告一次
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                actual_fps = self.frames_sent / elapsed
                print(f"\n实际发送帧率: {actual_fps:.2f} FPS")
    
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
    parser.add_argument("--fps", type=int, default=30, help="目标帧率")
    parser.add_argument("--quality", type=int, default=85, help="JPEG质量 (1-100)")
    
    args = parser.parse_args()
    
    sender = CameraSender(args.ip, args.port, args.fps, args.quality)
    try:
        if sender.start_camera():
            print("按 Ctrl+C 停止发送")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在停止...")
    finally:
        sender.stop()

if __name__ == "__main__":
    main()