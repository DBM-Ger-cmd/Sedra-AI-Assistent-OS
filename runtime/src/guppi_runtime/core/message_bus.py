from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Callable
from .util import utcnow

@dataclass
class Message:
    mission_id: str
    sender: str
    recipient: str
    type: str
    payload: dict = field(default_factory=dict)
    expects_response: bool = False
    message_id: str = field(default_factory=lambda: f"MSG-{uuid.uuid4().hex[:10].upper()}")
    correlation_id: str|None = None
    reply_to: str|None = None
    created_at: str = field(default_factory=utcnow)

class MessageBus:
    def __init__(self,audit=None):
        self.handlers={}; self.audit=audit
    def register(self, component_id: str, handler: Callable[[Message], object]):
        self.handlers[component_id]=handler
    def send(self, msg: Message):
        if self.audit:
            self.audit.append('MESSAGE_SENT',component=msg.sender,mission_id=msg.mission_id,payload={'to':msg.recipient,'type':msg.type,'message_id':msg.message_id})
        if msg.recipient not in self.handlers:
            raise KeyError(f'No handler registered for {msg.recipient}')
        result=self.handlers[msg.recipient](msg)
        if self.audit:
            self.audit.append('MESSAGE_PROCESSED',component=msg.recipient,mission_id=msg.mission_id,payload={'type':msg.type,'message_id':msg.message_id})
        return result
