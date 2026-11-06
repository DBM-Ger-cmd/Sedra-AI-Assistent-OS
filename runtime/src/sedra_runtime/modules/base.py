class BaseModule:
    id='base'
    def health(self): return True
    def handle(self,message): raise NotImplementedError
