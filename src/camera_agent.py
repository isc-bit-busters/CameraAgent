import cv2
import asyncio
import base64
import aiofiles
from spade import agent, behaviour
from spade.message import Message

class CameraAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.last_sent_time = None
        self.registered_agents = []
        self.camera_stream = None
        
    class SendPhotoBehaviour(behaviour.OneShotBehaviour):
        def __init__(self, jid, thread):
            super().__init__()
            self.jid = jid
            self.thread = thread 

        async def run(self):
            print("Capturing image...")

            # Initialize the camera
            
            if self.agent.camera_stream is None:
                self.agent.camera_stream = cv2.VideoCapture(0)
                self.agent.camera_stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            camera = self.agent.camera_stream

            for _ in range(5):
                camera.grab()

            ret, frame = camera.read()

            if not ret:
                print("Failed to capture image.")
                return

            # add timestamp to the image
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
