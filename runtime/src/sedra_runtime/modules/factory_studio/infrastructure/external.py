"""External Clients — Factory Studio HTTP-Clients für externe Services."""

from __future__ import annotations

import json
from typing import Any

try:
    import httpx
except ImportError:  # httpx fehlt: nur die HTTP-Aufrufe scheitern, Import des Moduls bleibt moeglich
    httpx = None

from ..application.ports import FactoryRegistryPort, EvidenceStorePort, GateClientPort, NotificationPort


class HttpFactoryRegistryClient(FactoryRegistryPort):
    """HTTP-Client für Factory Registry API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:57932", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if httpx is None:
            raise RuntimeError("httpx fehlt: pip install httpx")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        url = f"{self.base_url}/api/factory{path}"
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    
    async def list_types(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/types")
    
    async def get_type(self, typ_id: str) -> dict[str, Any] | None:
        try:
            return await self._request("GET", f"/types/{typ_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def build_project(self, typ_id: str, name: str, gate: bool = True) -> dict[str, Any]:
        return await self._request("POST", f"/build-project", json={"typ_id": typ_id, "name": name, "gate": gate})
    
    async def build_module(self, typ_id: str, name: str, project: str, gate: bool = True) -> dict[str, Any]:
        return await self._request("POST", f"/build-module", json={"typ_id": typ_id, "name": name, "project": project, "gate": gate})
    
    async def build_service(self, typ_id: str, name: str, project: str, gate: bool = True) -> dict[str, Any]:
        return await self._request("POST", f"/build-service", json={"typ_id": typ_id, "name": name, "project": project, "gate": gate})
    
    async def register_type(self, typ_id: str, name: str, functions: list[str], manifest_ref: str, gate: bool = True) -> dict[str, Any]:
        return await self._request("POST", "/register", json={
            "typ_id": typ_id, "name": name, "functions": functions, "manifest_ref": manifest_ref, "gate": gate
        })
    
    async def transition_type(self, typ_id: str, state: str, gate: bool = True) -> dict[str, Any]:
        return await self._request("POST", f"/transition/{typ_id}", json={"state": state, "gate": gate})


class HttpEvidenceStoreClient(EvidenceStorePort):
    """HTTP-Client für Evidence Store API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:57932", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if httpx is None:
            raise RuntimeError("httpx fehlt: pip install httpx")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        url = f"{self.base_url}/api/factory/evidence{path}"
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    
    async def list_runs(self, typ_id: str | None = None, limit: int = 50, success: bool | None = None) -> list[dict[str, Any]]:
        params = {"limit": limit}
        if typ_id:
            params["typ_id"] = typ_id
        if success is not None:
            params["success"] = str(success).lower()
        return await self._request("GET", "/runs", params=params)
    
    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        try:
            return await self._request("GET", f"/runs/{run_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_benchmarks(self, typ_id: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if typ_id:
            params["typ_id"] = typ_id
        return await self._request("GET", "/benchmarks", params=params)
    
    async def run_benchmark(self, config: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/benchmark/run", json=config)
    
    async def compare_variants(self, typ_id: str, variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await self._request("POST", "/benchmark/compare", json={"typ_id": typ_id, "variants": variants})
    
    async def analyze(self, min_runs: int = 10, typ_id: str | None = None) -> list[dict[str, Any]]:
        params = {"min_runs": min_runs}
        if typ_id:
            params["typ_id"] = typ_id
        return await self._request("GET", "/meta/analyze", params=params)
    
    async def detect_regressions(self, typ_id: str, window: int = 30, threshold: float = 20.0) -> list[dict[str, Any]]:
        params = {"window": window, "threshold": threshold}
        return await self._request("GET", f"/meta/regressions/{typ_id}", params=params)
    
    async def get_insights(self, min_confidence: float = 0.5) -> list[dict[str, Any]]:
        params = {"min_confidence": min_confidence}
        return await self._request("GET", "/meta/insights", params=params)
    
    async def get_report(self, min_runs: int = 10) -> dict[str, Any]:
        params = {"min_runs": min_runs}
        return await self._request("GET", "/meta/report", params=params)


class HttpGateClient(GateClientPort):
    """HTTP-Client für Captain-Gate API (One Sedra Integration)."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:57932", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if httpx is None:
            raise RuntimeError("httpx fehlt: pip install httpx")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        url = f"{self.base_url}/api/gates{path}"
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    
    async def get_pending_gates(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/pending")
    
    async def approve_gate(self, gate_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/{gate_id}/approve")
    
    async def reject_gate(self, gate_id: str, reason: str | None = None) -> dict[str, Any]:
        return await self._request("POST", f"/{gate_id}/reject", json={"reason": reason})
    
    async def get_gate_status(self, gate_id: str) -> dict[str, Any] | None:
        try:
            return await self._request("GET", f"/{gate_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


class NoOpNotificationClient(NotificationPort):
    """No-Op Notification Client (für Testing/Development)."""
    
    async def notify_build_complete(self, project_name: str, success: bool) -> None:
        pass
    
    async def notify_benchmark_complete(self, typ_id: str, score: float) -> None:
        pass
    
    async def notify_gate_pending(self, gate_id: str, gate_type: str) -> None:
        pass
    
    async def notify_gate_decided(self, gate_id: str, decision: str) -> None:
        pass


class ConsoleNotificationClient(NotificationPort):
    """Console-Notification Client (für Development)."""
    
    async def notify_build_complete(self, project_name: str, success: bool) -> None:
        status = "ERFOLGREICH" if success else "FEHLGESCHLAGEN"
        print(f"[NOTIFICATION] Build {status}: {project_name}")
    
    async def notify_benchmark_complete(self, typ_id: str, score: float) -> None:
        print(f"[NOTIFICATION] Benchmark abgeschlossen: {typ_id} (Score: {score:.2f})")
    
    async def notify_gate_pending(self, gate_id: str, gate_type: str) -> None:
        print(f"[NOTIFICATION] Neues Gate: {gate_id} ({gate_type})")
    
    async def notify_gate_decided(self, gate_id: str, decision: str) -> None:
        print(f"[NOTIFICATION] Gate entschieden: {gate_id} -> {decision}")