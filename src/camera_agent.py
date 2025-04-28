import cv2
import asyncio
import base64
import aiofiles
from spade import agent, behaviour
from spade.message import Message
import numpy as np

class CameraAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.last_sent_time = None
        self.registered_agents = []
        self.camera_stream = None
        self.mtx = None
        self.dist = None

    
    def find_c920(self):
        """Tries to find the Logitech C920 camera automatically."""
        print("Searching for C920 camera...")

        for index in range(5):  # try the first 5 devices
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                continue

            # Set a high resolution to check if supported
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            ret, frame = cap.read()
            if ret and frame is not None and frame.shape[1] == 1920 and frame.shape[0] == 1080:
                print(f"Found candidate camera at index {index}.")
                return cap  # return the VideoCapture object

            cap.release()

        print("No suitable C920 camera found.")
        return None
        
    class SendPhotoBehaviour(behaviour.OneShotBehaviour):
        def __init__(self, jid, thread):
            super().__init__()
            self.jid = jid
            self.thread = thread 
            

        async def run(self):
            print("Capturing image...")

            # Initialize the camera if not already done
            if self.agent.camera_stream is None:
                self.agent.camera_stream = self.agent.find_c920()
                if self.agent.camera_stream is None:
                    print("Failed to find C920 camera.")
                    return

                self.agent.camera_stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Load calibration data only once
                calibration = np.load('src/camera_calibration.npz')
                self.agent.mtx = calibration['camera_matrix'].copy()
                self.agent.dist = calibration['dist_coeffs'].copy()


            camera = self.agent.camera_stream

            for _ in range(5):
                camera.grab()

            ret, frame = camera.read()

            if not ret:
                print("Failed to capture image.")
                return

            # Undistort the frame
            h, w = frame.shape[:2]
            newcameramtx, roi = cv2.getOptimalNewCameraMatrix(self.agent.mtx, self.agent.dist, (w, h), 1, (w, h))
            frame_undistorted = cv2.undistort(frame, self.agent.mtx, self.agent.dist, None, newcameramtx)
            frame = frame_undistorted

            # Add timestamp
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            cv2.putText(frame, current_time, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            print(f"Picture for {self.thread} taken at {current_time}.")

            thread_stripped = self.thread.replace("-", "_")
            filename = f"photo_{thread_stripped}.jpg"
            cv2.imwrite(filename, frame)

            print(f"Image saved as '{filename}'.")

            async with aiofiles.open(filename, "rb") as img_file:
                img_data = await img_file.read()
                encoded_img = base64.b64encode(img_data).decode("utf-8")

            msg = Message(to=self.jid)
            msg.body = f"image {encoded_img}"
            msg.thread = str(self.thread)
            msg.metadata = {"thread": str(self.thread)}

            await self.send(msg)
            print(f"Photo sent to {self.jid} with thread {self.thread}.")

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