"""Incremental Loading List — Factory Studio unendliches Scrolling mit Laden bei Bedarf."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from abc import ABC, abstractmethod

from communitytoolkit_mvvm import ObservableObject, ObservableCollection, RelayCommand

T = TypeVar('T')


@dataclass
class IncrementalLoadingConfig:
    """Konfiguration für inkrementelles Laden."""
    page_size: int = 50
    threshold_pixels: int = 200  # Vor Ende laden
    max_pages: int = 0  # 0 = unbegrenzt
    auto_load_first: bool = True


class IncrementalLoadingSource(ABC, Generic[T]):
    """Abstrakte Quelle für inkrementelles Laden."""
    
    @abstractmethod
    async def get_items_async(self, offset: int, count: int) -> list[T]:
        """Lädt Items ab Offset."""
        ...
    
    @abstractmethod
    async def get_total_count_async(self) -> int:
        """Gibt Gesamtanzahl zurück (für Pager)."""
        ...


class IncrementalLoadingList(ObservableObject, Generic[T]):
    """ObservableCollection mit inkrementellem Laden (unendliches Scrolling)."""
    
    def __init__(
        self,
        source: IncrementalLoadingSource[T],
        config: IncrementalLoadingConfig | None = None,
    ):
        self.source = source
        self.config = config or IncrementalLoadingConfig()
        
        self.items: ObservableCollection[T] = ObservableCollection()
        self._loaded_count = 0
        self._total_count: int | None = None
        self._current_offset = 0
        self._is_loading = False
        self._has_more = True
        self._load_more_command = RelayCommand(self.load_more)
    
    @property
    def Items(self) -> ObservableCollection[T]:
        return self.items
    
    @property
    def LoadedCount(self) -> int:
        return self._loaded_count
    
    @property
    def TotalCount(self) -> int | None:
        return self._total_count
    
    @property
    def HasMoreItems(self) -> bool:
        return self._has_more and not self._is_loading
    
    @property
    def IsLoadingMore(self) -> bool:
        return self._is_loading
    
    @property
    def LoadMoreCommand(self) -> RelayCommand:
        return self._load_more_command
    
    async def initialize(self):
        """Initialisiert Liste (lädt erste Page)."""
        if self.config.auto_load_first:
            await self.load_more()
        
        # Total Count laden
        try:
            self._total_count = await self.source.get_total_count_async()
            self.notify_property_changed("TotalCount")
        except Exception:
            pass  # Total Count optional
    
    async def load_more(self):
        """Lädt nächste Page."""
        if self._is_loading or not self._has_more:
            return
        
        if self.config.max_pages > 0 and self._current_offset >= self.config.max_pages * self.config.page_size:
            self._has_more = False
            self.notify_property_changed("HasMoreItems")
            return
        
        self._is_loading = True
        self.notify_property_changed("IsLoadingMore")
        self.notify_property_changed("HasMoreItems")
        
        try:
            new_items = await self.source.get_items_async(self._current_offset, self.config.page_size)
            
            if not new_items:
                self._has_more = False
            else:
                for item in new_items:
                    self.items.append(item)
                self._loaded_count += len(new_items)
                self._current_offset += len(new_items)
                
                if len(new_items) < self.config.page_size:
                    self._has_more = False
            
            self.notify_property_changed("LoadedCount")
            self.notify_property_changed("HasMoreItems")
            
        except Exception as ex:
            print(f"Load more error: {ex}")
            self._has_more = False
        finally:
            self._is_loading = False
            self.notify_property_changed("IsLoadingMore")
            self.notify_property_changed("HasMoreItems")
    
    def refresh(self):
        """Setzt Liste zurück und lädt neu."""
        self.items.clear()
        self._loaded_count = 0
        self._current_offset = 0
        self._has_more = True
        self.notify_property_changed("LoadedCount")
        self.notify_property_changed("HasMoreItems")
        # Async reload
        import asyncio
        asyncio.create_task(self.initialize())


class ScrollViewerIncrementalLoader:
    """Helper: Verbindet ScrollViewer mit IncrementalLoadingList."""
    
    def __init__(self, scroll_viewer, loading_list: IncrementalLoadingList):
        self.scroll_viewer = scroll_viewer
        self.loading_list = loading_list
        self._threshold = loading_list.config.threshold_pixels
        self._attached = False
    
    def attach(self):
        """Verbindet ScrollViewer ViewChanged Event."""
        if not self._attached:
            self.scroll_viewer.ViewChanged += self._on_view_changed
            self._attached = True
    
    def detach(self):
        """Trennt Event."""
        if self._attached:
            self.scroll_viewer.ViewChanged -= self._on_view_changed
            self._attached = False
    
    def _on_view_changed(self, sender, args):
        """Prüft ob nahe am Ende -> load_more triggern."""
        if not self.loading_list.HasMoreItems or self.loading_list.IsLoadingMore:
            return
        
        # Scroll-Position prüfen
        extent = sender.ScrollableHeight
        offset = sender.VerticalOffset
        viewport = sender.ViewportHeight
        
        if extent > 0 and (extent - offset - viewport) < self._threshold:
            # Nahe am Ende -> laden
            import asyncio
            asyncio.create_task(self.loading_list.load_more())


# =============================================================================
# Factory für häufige Quellen
# =============================================================================

class FactoryRunsSource(IncrementalLoadingSource):
    """Quelle für Factory Runs (via Evidence Store)."""
    
    def __init__(self, evidence_store, typ_id: str | None = None, success: bool | None = None):
        self.evidence_store = evidence_store
        self.typ_id = typ_id
        self.success = success
    
    async def get_items_async(self, offset: int, count: int) -> list[Any]:
        runs = self.evidence_store.list_runs(
            typ_id=self.typ_id,
            limit=count,
            success=self.success
        )
        # Offset simulieren (Evidence Store hat kein Offset)
        return runs[offset:offset + count] if offset < len(runs) else []
    
    async def get_total_count_async(self) -> int:
        runs = self.evidence_store.list_runs(typ_id=self.typ_id, limit=10000)
        return len(runs)


class FactoryBenchmarksSource(IncrementalLoadingSource):
    """Quelle für Factory Benchmarks."""
    
    def __init__(self, evidence_store, typ_id: str | None = None):
        self.evidence_store = evidence_store
        self.typ_id = typ_id
    
    async def get_items_async(self, offset: int, count: int) -> list[Any]:
        benches = self.evidence_store.get_benchmarks(typ_id=self.typ_id)
        return benches[offset:offset + count] if offset < len(benches) else []
    
    async def get_total_count_async(self) -> int:
        benches = self.evidence_store.get_benchmarks(typ_id=self.typ_id)
        return len(benches)


class FactoryGatesSource(IncrementalLoadingSource):
    """Quelle für Captain Gates."""
    
    def __init__(self, gate_client):
        self.gate_client = gate_client
    
    async def get_items_async(self, offset: int, count: int) -> list[Any]:
        gates = await self.gate_client.get_pending_gates()
        return gates[offset:offset + count] if offset < len(gates) else []
    
    async def get_total_count_async(self) -> int:
        gates = await self.gate_client.get_pending_gates()
        return len(gates)