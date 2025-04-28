import cv2
import asyncio
import base64
import aiofiles
import numpy as np
from spade import agent, behaviour
from spade.message import Message
 
def find_logitech_c920(max_cameras=10):
    """Try to find a Logitech C920 camera."""
    print("Searching for Logitech C920...")
 
    for index in range(max_cameras):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # CAP_DSHOW: no delay on Windows
        if cap is None or not cap.isOpened():
            print(f"❌ Camera {index} not found.")
            continue
 
        # Try to get a high resolution to guess it's a C920
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
 
        print(f"Camera {index}: {int(width)}x{int(height)}")
 
        # Heuristic: C920 can do 1920x1080 easily
        # if int(width) == 1920 and int(height) == 1080:
        #     print(f"✅ Possible Logitech C920 found at index {index}")
        #     cap.release()
        #     return index
 
        cap.release()
 
    print("❌ No Logitech C920 found, falling back to camera 0.")
    return 0  # Default fallback
 
 
class CameraAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.last_sent_time = None
        self.registered_agents = []
        self.camera_stream = None
 
        # === Load the camera calibration ===
        calibration_data = np.load("src/camera_calibration.npz")
        self.camera_matrix = calibration_data["camera_matrix"]
        self.dist_coeffs = calibration_data["dist_coeffs"]
        print("Calibration loaded successfully.")
 
        # === Find the best camera (prefer C920) ===
        self.camera_index = find_logitech_c920()
 
    class SendPhotoBehaviour(behaviour.OneShotBehaviour):
        def __init__(self, jid, thread):
            super().__init__()
            self.jid = jid
            self.thread = thread
 
        async def run(self):
            print("Capturing image...")
 
            if self.agent.camera_stream is None:
                self.agent.camera_stream = cv2.VideoCapture(self.agent.camera_index)
                self.agent.camera_stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
 
            camera = self.agent.camera_stream
 
            for _ in range(5):
                camera.grab()
 
            ret, frame = camera.read()
 
            if not ret:
                print("Failed to capture image.")
                return
 
            # === Apply undistortion ===
            frame = cv2.undistort(frame, self.agent.camera_matrix, self.agent.dist_coeffs)
 
            # Add timestamp
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            cv2.putText(frame, current_time, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
 
            print(f"Picture for {self.thread} taken at {current_time}.")
 
            thread_stripped = self.thread.replace("-", "_")
            filename = f"photo_{thread_stripped}.jpg"
            cv2.imwrite(filename, frame)
 
            print(f"Image captured and saved as '{filename}'.")
 
            async with aiofiles.open(filename, "rb") as img_file:
                img_data = await img_file.read()
                encoded_img = base64.b64encode(img_data).decode("utf-8")
 
            msg = Message(to=self.jid)
            msg.body = f"image {encoded_img}"
            msg.thread = str(self.thread)
            msg.metadata = {"thread": str(self.thread)}
 
            print(f"Sending to \n\n\n{self.thread} --> {msg.body}\n\n\n")
 
            await self.send(msg)
            print("Photo sent to ", str(self.jid))
            print("Message: ", msg)
 
    class ListenToImageRequestBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            print("Waiting for request...")
            msg = await self.receive(timeout=9999)
            if msg:
                print(msg)
                command = msg.body.strip().lower()
                thread = msg.thread
                sender = str(msg.sender)
 
                if command == "request_image":
                    print(f"Received image request from {sender} with thread {thread}.")
                    send_photo_behaviour = self.agent.SendPhotoBehaviour(sender, thread)
                    self.agent.add_behaviour(send_photo_behaviour)
                else:
                    print("Received unknown command.")
 
    class PeriodicalSendImageBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            send_photo_behaviour = self.agent.SendPhotoBehaviour()
            self.agent.add_behaviour(send_photo_behaviour)
 
    async def setup(self):
        print(f"{self.jid} is ready.")
        self.add_behaviour(self.ListenToImageRequestBehaviour())
 
    async def stop(self):
        print("Stopping agent...")
        if self.camera_stream is not None:
            self.camera_stream.release()
            print("Camera stream released.")
        await super().stop()