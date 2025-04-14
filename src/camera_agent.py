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
                self.agent.camera_stream = cv2.VideoCapture(1)

            camera = self.agent.camera_stream
            await asyncio.sleep(2)

            ret, frame = camera.read()

            if not ret:
                print("Failed to capture image.")
                return

            filename = "photo.jpg"
            cv2.imwrite(filename, frame)

            print("Image captured and saved as 'photo.jpg'.")

            async with aiofiles.open(filename, "rb") as img_file:
                img_data = await img_file.read()
                encoded_img = base64.b64encode(img_data).decode("utf-8")

            msg = Message(to=self.jid)
            msg.set_metadata("performative", "inform")
            msg.body = f"image {encoded_img}"
            msg.thread = self.thread

            await self.send(msg)
            print("Photo sent to ", agent)

    class ListenToImageRequestBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            print("Waiting for request...")
            msg = await self.receive(timeout=9999)
            if msg:
                command = msg.body.strip().lower()
                thread = msg.thread
                sender = str(msg.sender)

                if command == "request_image":
                    print("Received image request.")
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
