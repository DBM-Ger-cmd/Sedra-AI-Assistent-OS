from .openai_local import OpenAICompatibleLocalAdapter

class LlamaCppServerAdapter(OpenAICompatibleLocalAdapter):
    def __init__(self, base_url="http://127.0.0.1:8080", timeout=20):
        super().__init__("llama-cpp-server",base_url,timeout)


class LlamaCppRouterAdapter(LlamaCppServerAdapter):
    """llama-server in router mode (config llama_server.external): the router picks the model by the name in the request, so the recipe's
    model name goes out without a vendor prefix ("google/gemma-4-12b-qat" -> "gemma-4-12b-qat"), the name the router knows it under."""
    def chat(self,messages,model=None,**kwargs):
        if isinstance(model,str): model=model.rsplit("/",1)[-1]
        return super().chat(messages,model=model,**kwargs)
