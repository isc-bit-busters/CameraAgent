from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

import threading
import asyncio
import os

class LogAgent(Agent):
    class SendBehaviour(OneShotBehaviour):
        def __init__(self, to_jid, message, robot_id, msg_type):
            super().__init__()
            self.to_jid = to_jid
            self.message = message
            self.robot_id = robot_id
            self.msg_type = msg_type

        async def run(self):
            from spade.message import Message
            msg = Message(to=self.to_jid, body=self.message)
            msg.set_metadata("robot_id", self.robot_id)
            msg.set_metadata("type", self.msg_type)
            await self.send(msg)
            await asyncio.sleep(1)
            await self.agent.stop()

def send_log_message(body, robot_id="top_camera", msg_type="log"):
    async def task():
        password = os.getenv("XMPP_PASSWORD", "plsnohack")
        agent = LogAgent(f"{robot_id}@prosody", password)
        await agent.start(auto_register=True)
        to_jid = "receiverClient@prosody"
        agent.add_behaviour(agent.SendBehaviour(to_jid, body, robot_id, msg_type))
        await asyncio.sleep(3)
        await agent.stop()
    threading.Thread(target=lambda: asyncio.run(task()), daemon=True).start()