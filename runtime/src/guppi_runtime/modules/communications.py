from .base import BaseModule
class CommunicationsModule(BaseModule):
    id='communications'
    def __init__(self): self.providers={}
    def register_provider(self,name,fn): self.providers[name]=fn
    def handle(self,message):
        req=message.payload.get('request',{}); provider=req.get('provider')
        if provider not in self.providers: return {'status':'unavailable','error':f'provider not configured: {provider}'}
        return self.providers[provider](req)
