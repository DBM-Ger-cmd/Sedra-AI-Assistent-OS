from .base import BaseModule
class KnowledgeModule(BaseModule):
    id='knowledge'
    def __init__(self,store): self.store=store
    def handle(self,message):
        q=message.payload.get('query',''); return {'results':self.store.search(q)}
