"""External API Adapters.

Adapters for external services (HTTP APIs, message queues, etc.).
"""
# Example HTTP adapter:
# import httpx
# from ...application.ports import ExternalServicePort
#
# class HttpExternalServiceAdapter(ExternalServicePort):
#     def __init__(self, base_url: str, api_key: str):
#         self._client = httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {api_key}"})
#
#     def call_service(self, endpoint: str, data: dict) -> dict:
#         response = self._client.post(endpoint, json=data)
#         response.raise_for_status()
#         return response.json()