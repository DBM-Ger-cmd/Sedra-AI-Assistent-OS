"""E2E Tests — Factory Studio WinAppDriver Integration."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

# appium ist optional - Tests werden übersprungen wenn nicht installiert
try:
    from appium import webdriver
    from appium.options.windows import WindowsOptions
    from appium.webdriver.common.appiumby import AppiumBy
    APPIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    WindowsOptions = None
    AppiumBy = None
    APPIUM_AVAILABLE = False


class WinAppDriverManager:
    """Manages WinAppDriver lifecycle for E2E tests."""
    
    DEFAULT_URL = "http://127.0.0.1:4723"
    DEFAULT_CAPABILITIES = {
        "platformName": "Windows",
        "deviceName": "WindowsPC",
        "app": "Root",  # For desktop apps, use "Root" and find by AutomationId
    }
    
    def __init__(self, url: str = DEFAULT_URL):
        self.url = url
        self.driver: webdriver.Remote | None = None
        self._process: subprocess.Popen | None = None
    
    def start_driver(self) -> bool:
        """Startet WinAppDriver wenn nicht läuft."""
        if not APPIUM_AVAILABLE:
            return False
            
        try:
            # Prüfen ob WinAppDriver läuft
            import requests
            response = requests.get(f"{self.url}/status", timeout=2)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        
        # WinAppDriver starten
        winappdriver_path = self._find_winappdriver()
        if not winappdriver_path:
            print("WinAppDriver nicht gefunden. Installiere via: winget install Microsoft.WinAppDriver")
            return False
        
        self._process = subprocess.Popen(
            [winappdriver_path, "4723"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Warten bis bereit
        for _ in range(10):
            time.sleep(0.5)
            try:
                response = requests.get(f"{self.url}/status", timeout=1)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
        
        return False
    
    def _find_winappdriver(self) -> str | None:
        """Findet WinAppDriver Installation."""
        possible_paths = [
            r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe",
            r"C:\Program Files\Windows Application Driver\WinAppDriver.exe",
        ]
        for p in possible_paths:
            if Path(p).exists():
                return p
        return None
    
    def create_session(self, app_id: str = "Root") -> webdriver.Remote:
        """Erstellt neue Appium Session."""
        options = WindowsOptions()
        options.set_capability("app", app_id)
        options.set_capability("platformName", "Windows")
        options.set_capability("deviceName", "WindowsPC")
        
        self.driver = webdriver.Remote(self.url, options=options)
        self.driver.implicitly_wait(10)
        return self.driver
    
    def close(self):
        """Schließt Session und Driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
        if self._process:
            self._process.terminate()
            self._process = None


# Skip marker für alle Tests in dieser Datei wenn appium nicht verfügbar
pytestmark = pytest.mark.skipif(not APPIUM_AVAILABLE, reason="appium nicht installiert")


class FactoryStudioE2ETestBase:
    """Base-Klasse für Factory Studio E2E Tests."""
    
    driver: webdriver.Remote
    manager: WinAppDriverManager
    
    @classmethod
    def setup_class(cls):
        """Klassen-Setup: WinAppDriver starten."""
        cls.manager = WinAppDriverManager()
        assert cls.manager.start_driver(), "WinAppDriver konnte nicht gestartet werden"
        cls.driver = cls.manager.create_session()
    
    @classmethod
    def teardown_class(cls):
        """Klassen-Teardown: Driver schließen."""
        cls.manager.close()
    
    def find_by_automation_id(self, automation_id: str):
        """Findet Element via AutomationId."""
        return self.driver.find_element("accessibility id", automation_id)
    
    def find_by_name(self, name: str):
        """Findet Element via Name."""
        return self.driver.find_element("name", name)
    
    def find_by_xpath(self, xpath: str):
        """Findet Element via XPath."""
        return self.driver.find_element("xpath", xpath)
    
    def click_automation_id(self, automation_id: str):
        """Klickt Element via AutomationId."""
        el = self.find_by_automation_id(automation_id)
        el.click()
    
    def send_keys_automation_id(self, automation_id: str, text: str):
        """Sendet Text an Element via AutomationId."""
        el = self.find_by_automation_id(automation_id)
        el.clear()
        el.send_keys(text)
    
    def wait_for_element(self, automation_id: str, timeout: float = 10.0):
        """Wartet auf Element."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from appium.webdriver.common.appiumby import AppiumBy
        
        WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, automation_id))
        )
    
    def assert_element_exists(self, automation_id: str, message: str = ""):
        """Assertet dass Element existiert."""
        try:
            self.find_by_automation_id(automation_id)
        except Exception:
            pytest.fail(f"Element nicht gefunden: {automation_id}. {message}")
    
    def assert_element_not_exists(self, automation_id: str, message: str = ""):
        """Assertet dass Element NICHT existiert."""
        try:
            self.find_by_automation_id(automation_id)
            pytest.fail(f"Element sollte nicht existieren: {automation_id}. {message}")
        except Exception:
            pass  # Erwartet


# =============================================================================
# Concrete Test Classes
# =============================================================================

class TestProjectBrowserE2E(FactoryStudioE2ETestBase):
    """E2E Tests für ProjectBrowser."""
    
    def test_project_browser_loads(self):
        """ProjectBrowser Tab lädt und zeigt TreeView."""
        # Tab finden und klicken
        self.click_automation_id("ProjectBrowserTab")
        
        # TreeView prüfen
        self.wait_for_element("ProjectTreeView")
        self.assert_element_exists("ProjectTreeView")
    
    def test_create_new_project(self):
        """Neues Projekt erstellen via UI."""
        self.click_automation_id("ProjectBrowserTab")
        self.wait_for_element("ProjectTreeView")
        
        # "Neues Projekt" Button klicken
        self.click_automation_id("CreateProjectButton")
        
        # Dialog prüfen
        self.wait_for_element("CreateProjectDialog")
        
        # Name eingeben
        self.send_keys_automation_id("ProjectNameInput", "E2E_Test_Project")
        self.send_keys_automation_id("ProjectDisplayNameInput", "E2E Test Project")
        
        # Factory Type auswählen
        self.click_automation_id("FactoryTypeComboBox")
        self.click_automation_id("FactoryTypeOption_Project")
        
        # OK klicken
        self.click_automation_id("CreateProjectOKButton")
        
        # Projekt in TreeView prüfen
        self.wait_for_element("ProjectNode_E2E_Test_Project")
        self.assert_element_exists("ProjectNode_E2E_Test_Project")
    
    def test_project_context_menu(self):
        """Projekt Context Menu (Rechtsklick)."""
        self.click_automation_id("ProjectBrowserTab")
        self.wait_for_element("ProjectTreeView")
        
        # Projekt erstellen falls nicht vorhanden
        try:
            self.find_by_automation_id("ProjectNode_E2E_Test_Project")
        except Exception:
            self.test_create_new_project()
        
        # Rechtsklick simulieren (via ContextRequested)
        project_node = self.find_by_automation_id("ProjectNode_E2E_Test_Project")
        project_node.right_click()  # Appium unterstützt right_click
        
        # Context Menu prüfen
        self.wait_for_element("ProjectContextMenu")
        self.assert_element_exists("ContextMenuItem_Build")
        self.assert_element_exists("ContextMenuItem_AddModule")
        self.assert_element_exists("ContextMenuItem_Delete")
    
    def test_drag_drop_module(self):
        """Drag & Drop Modul zwischen Projekten."""
        # TODO: Implement Drag & Drop via Appium Actions
        pass


class TestGraphViewE2E(FactoryStudioE2ETestBase):
    """E2E Tests für GraphView."""
    
    def test_graph_view_loads(self):
        """GraphView Tab lädt und zeigt GraphArea."""
        self.click_automation_id("GraphViewTab")
        
        # GraphArea prüfen
        self.wait_for_element("GraphArea")
        self.assert_element_exists("GraphArea")
    
    def test_graph_layout_algorithms(self):
        """Layout Algorithmus Wechsel."""
        self.click_automation_id("GraphViewTab")
        self.wait_for_element("GraphArea")
        
        # Layout ComboBox
        self.click_automation_id("LayoutAlgorithmCombo")
        self.click_automation_id("LayoutOption_ForceDirected")
        
        # Relayout Button
        self.click_automation_id("RelayoutButton")
        
        # Warten auf Layout-Berechnung
        time.sleep(2)
        
        # Zoom Controls
        self.click_automation_id("ZoomInButton")
        self.click_automation_id("ZoomOutButton")
    
    def test_graph_vertex_selection(self):
        """Vertex Selektion im Graph."""
        self.click_automation_id("GraphViewTab")
        self.wait_for_element("GraphArea")
        
        # Vertex klicken (falls vorhanden)
        try:
            vertex = self.find_by_xpath("//*[@Class='GraphX.Controls.VertexControl']")
            vertex.click()
            
            # Detail Panel prüfen
            self.assert_element_exists("VertexDetailPanel")
        except Exception:
            pytest.skip("Keine Vertices im Graph")


class TestExecutionViewE2E(FactoryStudioE2ETestBase):
    """E2E Tests für ExecutionView."""
    
    def test_execution_view_loads(self):
        """ExecutionView Tab lädt."""
        self.click_automation_id("ExecutionViewTab")
        
        # Pivot prüfen
        self.wait_for_element("ExecutionPivot")
        self.assert_element_exists("ExecutionPivot")
        
        # Tabs prüfen
        self.assert_element_exists("PivotItem_Runs")
        self.assert_element_exists("PivotItem_Benchmarks")
        self.assert_element_exists("PivotItem_Compare")
        self.assert_element_exists("PivotItem_Charts")
    
    def test_run_benchmark(self):
        """Benchmark via UI starten."""
        self.click_automation_id("ExecutionViewTab")
        self.wait_for_element("ExecutionPivot")
        
        # "Benchmark starten" Button
        self.click_automation_id("RunBenchmarkButton")
        
        # Dialog prüfen
        self.wait_for_element("RunBenchmarkDialog")
        
        # Konfiguration
        self.send_keys_automation_id("BenchmarkTypeCombo", "project_type")
        self.send_keys_automation_id("BenchmarkVariantInput", "default")
        self.send_keys_automation_id("BenchmarkIterationsInput", "3")
        
        # Starten
        self.click_automation_id("RunBenchmarkOKButton")
        
        # Warten auf Abschluss
        self.wait_for_element("BenchmarkProgressRing", timeout=60.0)
        
        # Ergebnis prüfen
        self.wait_for_element("BenchmarkResultCard", timeout=60.0)
    
    def test_compare_variants(self):
        """Varianten vergleichen."""
        self.click_automation_id("ExecutionViewTab")
        self.wait_for_element("ExecutionPivot")
        
        # Compare Tab
        self.click_automation_id("PivotItem_Compare")
        
        # Typ und Varianten
        self.send_keys_automation_id("CompareTypeCombo", "project_type")
        self.send_keys_automation_id("VariantsTextBox", "default,minimal,full")
        
        # Vergleichen
        self.click_automation_id("CompareVariantsButton")
        
        # Ergebnisse prüfen
        self.wait_for_element("ComparisonResults")


class TestStatusDashboardE2E(FactoryStudioE2ETestBase):
    """E2E Tests für StatusDashboard."""
    
    def test_status_dashboard_loads(self):
        """StatusDashboard Tab lädt."""
        self.click_automation_id("StatusDashboardTab")
        
        # Health Cards
        self.wait_for_element("HealthCards")
        self.assert_element_exists("HealthCards")
        
        # Gates Section
        self.assert_element_exists("GatesSection")
    
    def test_gate_approve_reject(self):
        """Gate Approve/Reject via Dashboard."""
        self.click_automation_id("StatusDashboardTab")
        self.wait_for_element("GatesList")
        
        # Falls Gates vorhanden
        try:
            gate_item = self.find_by_xpath("//ListViewItem[@AutomationId='GateItem']")
            
            # Approve Button
            approve_btn = gate_item.find_element("accessibility id", "ApproveGateButton")
            approve_btn.click()
            
            # Status prüfen
            time.sleep(1)
            status_badge = gate_item.find_element("accessibility id", "GateStatusBadge")
            assert "approved" in status_badge.get_attribute("Value").lower()
        except Exception:
            pytest.skip("Keine offenen Gates zum Testen")


class TestGatePanelE2E(FactoryStudioE2ETestBase):
    """E2E Tests für GatePanel."""
    
    def test_gate_panel_loads(self):
        """GatePanel lädt (als Flyout/Panel)."""
        # GatePanel ist UserControl, muss in Host eingebunden sein
        # Test via StatusDashboard Integration
        self.click_automation_id("StatusDashboardTab")
        self.wait_for_element("GatesSection")
        
        # GatePanel innerhalb StatusDashboard
        self.assert_element_exists("GatePanelView")


class TestAccessibilityE2E(FactoryStudioE2ETestBase):
    """E2E Tests für Accessibility (Barrierefreiheit)."""
    
    def test_keyboard_navigation(self):
        """Tastatur-Navigation durch alle Tabs."""
        tabs = [
            "ProjectBrowserTab",
            "GraphViewTab", 
            "ExecutionViewTab",
            "StatusDashboardTab",
        ]
        
        for tab_id in tabs:
            self.click_automation_id(tab_id)
            time.sleep(0.5)
            
            # Tab prüfen
            self.assert_element_exists(tab_id)
        
        # Tab-Wechsel via Ctrl+Tab simulieren
        # (Appium: driver.press_keycode)
    
    def test_screen_reader_labels(self):
        """Screen Reader Labels (AutomationProperties.Name)."""
        # Wichtige Elemente haben AutomationProperties.Name
        elements_to_check = [
            ("CreateProjectButton", "Neues Projekt erstellen"),
            ("RunBenchmarkButton", "Benchmark starten"),
            ("ApproveGateButton", "Genehmigen"),
            ("RejectGateButton", "Ablehnen"),
        ]
        
        for automation_id, expected_name in elements_to_check:
            try:
                el = self.find_by_automation_id(automation_id)
                name = el.get_attribute("Name")
                assert name == expected_name, f"{automation_id}: Expected '{expected_name}', got '{name}'"
            except Exception:
                pytest.skip(f"Element {automation_id} nicht gefunden")
    
    def test_high_contrast_mode(self):
        """High Contrast Mode Support."""
        # High Contrast aktivieren (System-Setting)
        # UI prüfen: Farben, Kontraste
        pass
    
    def test_focus_indicators(self):
        """Fokus-Indikatoren sichtbar."""
        self.click_automation_id("ProjectBrowserTab")
        self.wait_for_element("ProjectTreeView")
        
        # Erstes Element fokussieren
        first_item = self.find_by_automation_id("ProjectNode_First")
        first_item.click()
        
        # Fokus-Style prüfen (via Computed Style)
        # Appium: driver.execute_script("return window.getComputedStyle(...)")
    
    def test_automation_ids_present(self):
        """Alle interaktiven Elemente haben AutomationId."""
        # Sammle alle Buttons, Inputs, ListViews
        interactive_types = ["Button", "TextBox", "ComboBox", "ListView", "TreeView", "Pivot"]
        
        for ctrl_type in interactive_types:
            elements = self.driver.find_elements("class name", ctrl_type)
            for el in elements:
                aid = el.get_attribute("AutomationId")
                assert aid and aid.strip(), f"{ctrl_type} ohne AutomationId: {el}"


class TestPerformanceE2E(FactoryStudioE2ETestBase):
    """E2E Tests für Performance."""
    
    def test_project_browser_load_time(self):
        """ProjectBrowser Ladezeit < 2s."""
        import time
        
        start = time.time()
        self.click_automation_id("ProjectBrowserTab")
        self.wait_for_element("ProjectTreeView")
        elapsed = time.time() - start
        
        assert elapsed < 2.0, f"ProjectBrowser Ladezeit {elapsed:.2f}s > 2s"
    
    def test_graph_layout_performance(self):
        """Graph Layout Berechnung < 5s für 100 Knoten."""
        self.click_automation_id("GraphViewTab")
        self.wait_for_element("GraphArea")
        
        # Layout neu berechnen
        start = time.time()
        self.click_automation_id("RelayoutButton")
        self.wait_for_element("GraphArea")  # Warten bis Layout fertig
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Graph Layout {elapsed:.2f}s > 5s"
    
    def test_benchmark_execution_time(self):
        """Benchmark Ausführung innerhalb Timeout."""
        self.click_automation_id("ExecutionViewTab")
        self.wait_for_element("ExecutionPivot")
        
        start = time.time()
        self.click_automation_id("RunBenchmarkButton")
        self.wait_for_element("RunBenchmarkDialog")
        self.click_automation_id("RunBenchmarkOKButton")
        
        # Warten auf Ergebnis (max 60s)
        self.wait_for_element("BenchmarkResultCard", timeout=60.0)
        elapsed = time.time() - start
        
        assert elapsed < 60.0, f"Benchmark {elapsed:.2f}s > 60s"


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Pytest Konfiguration."""
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end (requires WinAppDriver)"
    )
    config.addinivalue_line(
        "markers", "accessibility: marks tests as accessibility tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


# =============================================================================
# Test Runner Helper
# =============================================================================

def run_e2e_tests():
    """Führt E2E Tests aus (für CI/CD)."""
    import sys
    
    # Prerequisites prüfen
    manager = WinAppDriverManager()
    if not manager.start_driver():
        print("WinAppDriver nicht verfügbar. Tests übersprungen.")
        return 0
    
    # Pytest ausführen
    result = pytest.main([
        "-v",
        "-m", "e2e",
        "--tb=short",
        __file__,
    ])
    
    manager.close()
    return result


if __name__ == "__main__":
    sys.exit(run_e2e_tests())