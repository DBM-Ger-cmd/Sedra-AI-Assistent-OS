from .openai_local import OpenAICompatibleLocalAdapter

class LlamaCppServerAdapter(OpenAICompatibleLocalAdapter):
    def __init__(self, base_url="http://127.0.0.1:8080", timeout=20):
        super().__init__("llama-cpp-server",base_url,timeout)
