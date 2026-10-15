from .openai_local import OpenAICompatibleLocalAdapter

class LMStudioAdapter(OpenAICompatibleLocalAdapter):
    def __init__(self, base_url="http://127.0.0.1:1234", timeout=20):
        super().__init__("lm-studio",base_url,timeout)
