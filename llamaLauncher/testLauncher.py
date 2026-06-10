#!/usr/bin/env python3
"""
Unit Tests for the Refactored llamaLauncher/app Backend Package
=============================================================
Audits and validates the correct execution of each backend module:
- app/backend/hardware.py: CPU core and GPU acceleration scanning.
- app/backend/config.py: Parameter optimizations and PolarQuant KV caching flags.
- app/backend/models.py: Scanning local model folders.
- app/backend/manager.py: Server process manager Singleton lifecycle and logs.

Usage:
    python testLauncher.py
    python -m unittest testLauncher.py -v
"""

import unittest
import sys
from pathlib import Path

# Add project root to path (testLauncher.py is in llamaLauncher/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import app.backend.hardware as hardware
import app.backend.config as config
import app.backend.models as models
from app.backend.manager import ProcessManager

class TestHardwareModule(unittest.TestCase):
    """Audits the hardware scanner module."""
    
    def test_cpu_cores_detection(self):
        """Verifies that CPU cores detection returns valid values."""
        physical, logical = hardware.get_cpu_cores()
        
        self.assertIsInstance(physical, int)
        self.assertIsInstance(logical, int)
        self.assertGreaterEqual(physical, 1)
        self.assertGreaterEqual(logical, 1)
        self.assertGreaterEqual(logical, physical)
        
    def test_gpu_detection(self):
        """Verifies that GPU detection returns Boolean states."""
        has_nvidia, has_vulkan = hardware.detect_gpus()
        
        self.assertIsInstance(has_nvidia, bool)
        self.assertIsInstance(has_vulkan, bool)

class TestConfigModule(unittest.TestCase):
    """Audits the parameter optimizer module."""
    
    def test_optimize_params_cpu(self):
        """Verifies optimization parameters for CPU mode."""
        params = config.optimize_params("CPU", physical_cores=4)
        
        self.assertIn("threads", params)
        self.assertIn("port", params)
        self.assertIn("context", params)
        self.assertIn("ngl", params)
        
        self.assertEqual(params["threads"], 4)
        self.assertEqual(params["port"], 8080)
        self.assertEqual(params["context"], 8192)
        self.assertEqual(params["ngl"], 0)

    def test_optimize_params_gpu(self):
        """Verifies optimization parameters for CUDA/GPU mode."""
        params = config.optimize_params("CUDA", physical_cores=6)
        
        self.assertEqual(params["threads"], 6)
        self.assertEqual(params["context"], 8192)
        self.assertEqual(params["ngl"], 99)

    def test_polar_quant_flags(self):
        """Verifies PolarQuant flag matching and string generation."""
        # 1. Performance mode (4-bit)
        flags_1, status_1 = config.get_polar_quant_flags("1")
        self.assertIn("q4_0", flags_1)
        self.assertIn("Flash Attention", status_1)
        
        # 2. Quality mode (8-bit)
        flags_2, status_2 = config.get_polar_quant_flags("2")
        self.assertIn("q8_0", flags_2)
        
        # 3. Off / Standard mode
        flags_3, status_3 = config.get_polar_quant_flags("3")
        self.assertEqual(flags_3, "")
        self.assertIn("Disabled", status_3)

    def test_optimize_params_with_polar_quant(self):
        """Verifies optimization parameters with PolarQuant choices."""
        # GPU Performance Mode (Q4_0) -> 32768 tokens
        params_gpu_perf = config.optimize_params("CUDA", physical_cores=6, pq_choice="1")
        self.assertEqual(params_gpu_perf["context"], 32768)
        
        # GPU Quality Mode (Q8_0) -> 16384 tokens
        params_gpu_qual = config.optimize_params("CUDA", physical_cores=6, pq_choice="2")
        self.assertEqual(params_gpu_qual["context"], 16384)
        
        # CPU Performance Mode (Q4_0) -> 16384 tokens
        params_cpu_perf = config.optimize_params("CPU", physical_cores=4, pq_choice="1")
        self.assertEqual(params_cpu_perf["context"], 16384)

class TestModelsModule(unittest.TestCase):
    """Audits local model scanning and online recommended structures."""
    
    def test_recommended_models_structure(self):
        """Verifies recommended model configurations match requirements."""
        self.assertGreater(len(models.RECOMMENDED_MODELS), 0)
        
        for key, item in models.RECOMMENDED_MODELS.items():
            self.assertIn("name", item)
            self.assertIn("category", item)
            self.assertIn("filename", item)
            self.assertIn("url", item)
            self.assertIn("size_est", item)
            
            self.assertTrue(item["filename"].endswith(".gguf"))
            self.assertTrue(item["url"].startswith("http"))
            self.assertIn(item["category"], ["edge", "large", "coder"])

    def test_scan_local_models_empty(self):
        """Verifies scanning doesn't fail and returns list structure."""
        temp_dir = Path("c:/temp/AI Local/models")
        results = models.scan_local_models(temp_dir, "edge")
        self.assertIsInstance(results, list)

class TestServerModule(unittest.TestCase):
    """Audits ProcessManager and server lifecycles."""
    
    def test_active_servers_cleanup_runs(self):
        """Verifies server killing helper runs without exceptions."""
        pm = ProcessManager()
        try:
            pm.kill_all_zombies()
            executed = True
        except Exception:
            executed = False
        self.assertTrue(executed)

if __name__ == "__main__":
    unittest.main()
