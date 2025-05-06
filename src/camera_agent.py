import os
import cv2
import asyncio
import base64
import aiofiles
import numpy as np
from spade import agent, behaviour
from spade.message import Message
import subprocess
from scr.vision import detect_cubes_camera_agent, detect_walls, load_points, build_transformation

 
def find_logitech_c920(max_cameras=10):
    """Try to find a Logitech C920 camera."""
    print("Searching for Logitech C920...")
 
    for index in range(max_cameras):
        cap = cv2.VideoCapture(index)  
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
        # Heuristic: C920 can do 1920x1080 easily
        if int(width) == 1920 and int(height) == 1080:
            print(f"✅ Possible Logitech C920 found at index {index}")

            # # Set zoom to minimum (100)
            try:
                subprocess.run(['v4l2-ctl', '-d', f'/dev/video{index}', '-c', 'zoom_absolute=100'], check=True, capture_output=True)
                print(f"Zoom set to 100 for camera {index}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Could not set zoom for camera {index}: {e}")

            # Disable autofocus (optional, but often helpful for consistent results)
            try:
                subprocess.run(['v4l2-ctl', '-d', f'/dev/video{index}', '-c', 'focus_automatic_continuous=0'], check=True, capture_output=True)
                print(f"Autofocus disabled for camera {index}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Could not disable autofocus for camera {index}: {e}")

            # Set focus to a fixed value (adjust the value as needed)
            try:
                subprocess.run(['v4l2-ctl', '-d', f'/dev/video{index}', '-c', 'focus_absolute=0'], check=True, capture_output=True)
                print(f"Focus set to 0 for camera {index}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Could not set focus for camera {index}: {e}")
            
            # cap.release()
            return index
 
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
                self.agent.camera_stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.agent.camera_stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

 
            camera = self.agent.camera_stream
 
            for _ in range(5):
                camera.grab()
 
            ret, frame = camera.read()
            
            walls = detect_walls(frame)
            cubes = detect_cubes_camera_agent(frame)
            wall_scale_factor = 0.8
                # send a message to another agent
            a_points, b_points = load_points("/agent/points_mapping.png")

            trans = build_transformation(a_points, b_points)
                
            new_walls = []
            for wall in walls:
                x1, y1, x2, y2 = wall
                length_x = abs(x2 - x1)
                length_y = abs(y2 - y1)

                if length_x > length_y:
                    x1 = int(x1 - (length_x - length_x * wall_scale_factor) / 2)
                    x2 = int(x2 + (length_x - length_x * wall_scale_factor) / 2)
                else:
                    y1 = int(y1 - (length_y - length_y * wall_scale_factor) / 2)
                    y2 = int(y2 + (length_y - length_y * wall_scale_factor) / 2)

                new_walls.append([x1, y1, x2, y2])

            walls = new_walls
            
            # Apply the homography transformation to the walls
            walls = [[tx1, ty1, tx2, ty2] 
                    for x1, y1, x2, y2 in walls 
                    for tx1, ty1 in [trans((x1, y1))]
                    for tx2, ty2 in [trans((x2, y2))]]
            
            walls+= cubes
            #save walls in a file and before check if this file exisits
            if os.path.exists("/src/walls.txt"):
                #reas file 
                data = np.load("/src/walls.txt")
                walls = data["walls"]
                #delete file
                os.remove("/src/walls.txt")
            else:
                #save walls in a file npz
                np.savez("/src/walls.txt", walls=walls)
            # send  walls to another agent

            msg = Message(to=self.jid)
            msg.body = f"{walls}"
            msg.thread = str(self.thread)
            msg.metadata = {"thread": str(self.thread)}
            
            print(f"Sending to \n\n\n{self.thread} --> {msg.body}\n\n\n")
            await self.send(msg)
            
            if not ret:
                print("Failed to capture image.")
                return
                
            # === Apply undistortion ===
            #frame = cv2.undistort(frame, self.agent.camera_matrix, self.agent.dist_coeffs)
            # frame = cv2.resize(frame, (800, 600))
            # Add timestamp
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            cv2.putText(frame, current_time, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
 
            print(f"Picture for {self.thread} taken at {current_time}.")
 
            thread_stripped = self.thread.replace("-", "_")
            filename = f"photo_{thread_stripped}.jpg"
            #resize the image to 640x480
            # frame = cv2.resize(frame, (640, 480))
            
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

            print("Photo sent to ", str(self.jid), flush=True)
            print("Message: ", msg, flush=True)

            xmpp_username="receiverClient"
            xmpp_server="prosody"
            msg = Message(to=f"{xmpp_username}@{xmpp_server}")
            msg.set_metadata("robot_id", "top_camera")
            msg.set_metadata("type", "image")
            msg.body = encoded_img

            try:
                await self.send(msg)
                print(f"Image sent to {xmpp_username}@{xmpp_server} with thread {self.thread}.", flush=True)
            except Exception as e:
                print(f"Failed to send image to {xmpp_username}@{xmpp_server}: {e}", flush=True)
            
 
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
