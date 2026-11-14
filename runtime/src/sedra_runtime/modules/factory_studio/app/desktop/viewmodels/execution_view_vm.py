"""ExecutionView ViewModel — Benchmark Runs, Logs, Charts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from communitytoolkit_mvvm import ObservableObject, ObservableCollection, RelayCommand

from ....di import ServiceContainer
from ...use_cases.build_benchmark_use_cases import (
    RunBenchmarkRequest, RunBenchmarkResponse,
    CompareVariantsRequest, CompareVariantsResponse,
    ListBenchmarksResponse, ListBuildsResponse,
)
from ...dtos import RunRecord, BenchmarkRecord


@dataclass
class RunItemViewModel(ObservableObject):
    """ViewModel für einen Run in der Liste."""
    id: str
    name: str
    variant: str
    status: str
    score: float | None
    duration_ms: int | None
    artifacts_count: int
    is_selected: bool = False
    
    @property
    def duration_text(self) -> str:
        if self.duration_ms is None:
            return "—"
        if self.duration_ms < 1000:
            return f"{self.duration_ms} ms"
        return f"{self.duration_ms / 1000:.1f} s"


@dataclass
class VariantComparisonViewModel(ObservableObject):
    """ViewModel für Variant-Vergleich."""
    variant: str
    score: float | None
    success_rate: float
    duration_median: int
    artifacts_mean: float


@dataclass
class ChartSeriesViewModel:
    """Chart-Serie für ScottPlot."""
    name: str
    x_values: list[float]
    y_values: list[float]
    color: str


class ExecutionViewViewModel(ObservableObject):
    """ViewModel für ExecutionView — Benchmarks, Runs, Charts."""
    
    def __init__(self, main_vm: Any):
        self.main_vm = main_vm
        self.container: ServiceContainer = main_vm.container
        
        # Collections
        self.runs: ObservableCollection[RunItemViewModel] = ObservableCollection()
        self.benchmarks: ObservableCollection[Any] = ObservableCollection()  # BenchmarkDTO
        self.comparisons: ObservableCollection[VariantComparisonViewModel] = ObservableCollection()
        
        # Selected Items
        self.selected_run: RunItemViewModel | None = None
        self.selected_benchmark: Any = None
        
        # Filters
        self.status_filters: list[str] = ["Alle", "success", "failed", "running", "pending"]
        self.selected_status_filter: str = "Alle"
        self.type_filters: list[str] = ["Alle", "project", "module", "service"]
        self.selected_type_filter: str = "Alle"
        self.benchmark_types: list[str] = []
        self.selected_benchmark_type: str = "Alle"
        
        # Compare
        self.compare_type: str = ""
        self.compare_variants_text: str = ""
        self.comparisons: ObservableCollection[VariantComparisonViewModel] = ObservableCollection()
        
        # Charts
        self.chart_types: list[str] = ["Line", "Bar", "Scatter", "BoxPlot"]
        self.selected_chart_type: str = "Line"
        self.chart_metrics: list[str] = ["duration_ms", "success_rate", "artifacts_count", "score"]
        self.selected_chart_metric: str = "duration_ms"
        self.chart_group_by: list[str] = ["variant", "project", "date"]
        self.selected_chart_group_by: str = "variant"
        
        # State
        self.is_loading: bool = False
        self.is_running_benchmark: bool = False
        
        # Commands
        self.run_benchmark_command = RelayCommand(self._run_benchmark)
        self.compare_variants_command = RelayCommand(self._compare_variants)
        self.open_logs_command = RelayCommand(self._open_logs)
        self.export_command = RelayCommand(self._export_data)
        
        # Chart
        self.chart_series: list[ChartSeriesViewModel] = []
        
        # Selected Project from MainVM
        self._project_id: str | None = None
    
    @property
    def project_id(self) -> str | None:
        return self._project_id
    
    @project_id.setter
    def project_id(self, value: str | None):
        self._project_id = value
        if value:
            self.load_runs()
            self.load_benchmarks()
            self.load_benchmark_types()
    
    # --- Load Methods ---
    
    async def load_runs(self):
        """Lädt Runs für aktuelles Projekt."""
        if not self._project_id:
            return
        
        self.is_loading = True
        self.notify_property_changed("is_loading")
        
        try:
            response: ListBuildsResponse = await self.container.list_builds.execute(self._project_id)
            
            self.runs.clear()
            for b in response.builds:
                self.runs.append(RunItemViewModel(
                    id=b.id,
                    name=b.name or b.id,
                    variant="default",  # TODO: aus Metriken
                    status=b.status,
                    score=None,  # TODO: aus Benchmark
                    duration_ms=b.duration_ms,
                    artifacts_count=len(b.artifacts),
                ))
        except Exception as ex:
            print(f"Load runs error: {ex}")
        finally:
            self.is_loading = False
            self.notify_property_changed("is_loading")
    
    async def load_benchmarks(self):
        """Lädt Benchmarks für aktuelles Projekt."""
        if not self._project_id:
            return
        
        try:
            response: ListBenchmarksResponse = await self.container.list_benchmarks.execute()
            
            self.benchmarks.clear()
            for b in response.benchmarks:
                self.benchmarks.append(b)
            
            # Typen extrahieren
            types = set()
            for b in response.benchmarks:
                types.add(b.typ_id)
            self.benchmark_types = ["Alle"] + sorted(types)
            self.notify_property_changed("benchmark_types")
            
        except Exception as ex:
            print(f"Load benchmarks error: {ex}")
    
    async def load_benchmark_types(self):
        """Lädt verfügbare Factory-Typen für Benchmarks."""
        try:
            types = await self.container.factory_registry.list_types()
            self.benchmark_types = ["Alle"] + sorted([t["typ_id"] for t in types])
            self.notify_property_changed("benchmark_types")
        except Exception as ex:
            print(f"Load types error: {ex}")
    
    # --- Commands ---
    
    def _run_benchmark(self):
        """Startet Benchmark für aktuelles Projekt."""
        if not self._project_id:
            return
        
        self.is_running_benchmark = True
        self.notify_property_changed("is_running_benchmark")
        
        # Async wrapper
        import asyncio
        asyncio.create_task(self._run_benchmark_async())
    
    async def _run_benchmark_async(self):
        try:
            request = RunBenchmarkRequest(
                factory_type_id=self.main_vm.container.registry.liste_typen()[0]["typ_id"] if self.main_vm.container.registry.liste_typen() else "project_type",
                variant="default",
                iterations=3,
                build_type="project",
                project_name=self._project_id,
                gate=True,
            )
            
            response: RunBenchmarkResponse = await self.container.run_benchmark.execute(request)
            
            if response.success:
                await self.load_benchmarks()
                await self.load_runs()
        except Exception as ex:
            print(f"Benchmark error: {ex}")
        finally:
            self.is_running_benchmark = False
            self.notify_property_changed("is_running_benchmark")
    
    def _compare_variants(self):
        """Vergleicht Varianten."""
        if not self.compare_type or not self.compare_variants_text:
            return
        
        variants = [v.strip() for v in self.compare_variants_text.split(",") if v.strip()]
        if len(variants) < 2:
            return
        
        # Async wrapper
        import asyncio
        asyncio.create_task(self._compare_variants_async(variants))
    
    async def _compare_variants_async(self, variants: list[str]):
        self.is_loading = True
        self.notify_property_changed("is_loading")
        
        try:
            request = CompareVariantsRequest(
                factory_type_id=self.compare_type,
                variants=variants,
                iterations=3,
            )
            
            response: CompareVariantsResponse = await self.container.compare_variants.execute(request)
            
            self.comparisons.clear()
            for r in response.benchmarks:
                self.comparisons.append(VariantComparisonViewModel(
                    variant=r.get("variant", ""),
                    score=r.get("score"),
                    success_rate=r.get("aggregated_metrics", {}).get("success_rate", 0),
                    duration_median=r.get("aggregated_metrics", {}).get("duration_ms", {}).get("median", 0),
                    artifacts_mean=r.get("aggregated_metrics", {}).get("artifacts", {}).get("mean", 0),
                ))
        except Exception as ex:
            print(f"Compare error: {ex}")
        finally:
            self.is_loading = False
            self.notify_property_changed("is_loading")
    
    def _open_logs(self):
        """Öffnet Logs für selektierten Run."""
        if not self.selected_run:
            return
        # TODO: Log-Viewer öffnen
        pass
    
    def _export_data(self):
        """Exportiert Daten."""
        # TODO: Export Dialog
        pass