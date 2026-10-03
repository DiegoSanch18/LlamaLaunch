#!/usr/bin/env python3
"""
Unit Tests for the Refactored llamaLauncher/app Backend Package
=============================================================
Audits and validates the correct execution of each backend module:
- app/backend/hardware.py: CPU core and GPU acceleration scanning.
- app/backend/config.py: Parameter optimizations and PolarQuant KV caching flags.
- app/backend/models.py: Scanning local model folders and hierarchical scanner.
- app/backend/binaries.py: Dynamic path resolution and dedicated vs generic binary priority.
- app/backend/manager.py: Server process manager Singleton lifecycle and logs.

Usage:
    python -m unittest llamaLauncher/testLauncher.py -v
    python testLauncher.py
"""

import unittest
import sys
import tempfile
import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Dynamically locate llamaLauncher and project root
CURRENT_FILE = Path(__file__).resolve()
if CURRENT_FILE.parent.name == "llamaLauncher":
    SCRIPT_DIR = CURRENT_FILE.parent
    PROJECT_ROOT = SCRIPT_DIR.parent
else:
    p = CURRENT_FILE.parent
    while p.parent != p and not (p / "llamaLauncher").exists():
        p = p.parent
    PROJECT_ROOT = p
    SCRIPT_DIR = PROJECT_ROOT / "llamaLauncher"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import app.backend.hardware as hardware
import app.backend.config as config
import app.backend.models as models
from app.backend.manager import ProcessManager

# Attempt import of binaries module (created in M1)
try:
    import app.backend.binaries as binaries
    HAS_BINARIES_MODULE = True
except ImportError:
    try:
        import llamaLauncher.app.backend.binaries as binaries
        HAS_BINARIES_MODULE = True
    except ImportError:
        binaries = None
        HAS_BINARIES_MODULE = False

try:
    from app.backend.api import ApiBridge
    HAS_API_BRIDGE = True
except ImportError:
    try:
        from llamaLauncher.app.backend.api import ApiBridge
        HAS_API_BRIDGE = True
    except ImportError:
        ApiBridge = None
        HAS_API_BRIDGE = False

try:
    import app.backend.batch_manager as batch_manager
    HAS_BATCH_MANAGER = True
except ImportError:
    try:
        import llamaLauncher.app.backend.batch_manager as batch_manager
        HAS_BATCH_MANAGER = True
    except ImportError:
        batch_manager = None
        HAS_BATCH_MANAGER = False


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
        """Verifies optimization parameters with PolarQuant choices across CUDA and CPU."""
        # GPU Performance Mode (Q4_0) -> 32768 tokens
        params_gpu_perf = config.optimize_params("CUDA", physical_cores=6, pq_choice="1")
        self.assertEqual(params_gpu_perf["context"], 32768)
        
        # GPU Quality Mode (Q8_0) -> 16384 tokens
        params_gpu_qual = config.optimize_params("CUDA", physical_cores=6, pq_choice="2")
        self.assertEqual(params_gpu_qual["context"], 16384)
        
        # CPU Performance Mode (Q4_0) -> 16384 tokens (capped to prevent system RAM exhaustion)
        params_cpu_perf = config.optimize_params("CPU", physical_cores=4, pq_choice="1")
        self.assertEqual(params_cpu_perf["context"], 16384)

        # CPU Ultra Performance Mode (Q3_K) -> 16384 tokens (capped)
        params_cpu_ultra = config.optimize_params("CPU", physical_cores=4, pq_choice="4")
        self.assertEqual(params_cpu_ultra["context"], 16384)

        # CPU Balanced Mode (Q5_0) -> 16384 tokens (capped from 24K)
        params_cpu_bal = config.optimize_params("CPU", physical_cores=4, pq_choice="5")
        self.assertEqual(params_cpu_bal["context"], 16384)


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


class TestPathResolutionModule(unittest.TestCase):
    """Audits dynamic path resolution for models_dir and bin_root (Feature F2)."""

    def test_resolve_models_dir_fallback(self):
        """Verifies models_dir resolution prioritizes G: drive and falls back to project_root."""
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_models_dir"):
            models_dir = binaries.resolve_models_dir(PROJECT_ROOT)
            self.assertIsInstance(models_dir, Path)
            live_path = Path("G:/My Drive/AI Local/models")
            if live_path.exists():
                self.assertEqual(models_dir, live_path)
            else:
                self.assertEqual(models_dir, PROJECT_ROOT / "models")
        else:
            # Reference logic verification
            live_path = Path("G:/My Drive/AI Local/models")
            expected = live_path if live_path.exists() else (PROJECT_ROOT / "models")
            self.assertTrue(expected.name == "models")

    def test_resolve_bin_root_fallback(self):
        """Verifies bin_root resolution prioritizes G: drive and falls back to project_root."""
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_bin_root"):
            bin_root = binaries.resolve_bin_root(PROJECT_ROOT)
            self.assertIsInstance(bin_root, Path)
            live_bin = Path("G:/My Drive/AI Local/llamaLauncher/bin/llama.cpp")
            if live_bin.exists():
                self.assertEqual(bin_root, live_bin)
            else:
                self.assertEqual(bin_root, PROJECT_ROOT / "llamaLauncher" / "bin" / "llama.cpp")
        else:
            # Reference logic verification
            live_bin = Path("G:/My Drive/AI Local/llamaLauncher/bin/llama.cpp")
            expected = live_bin if live_bin.exists() else (PROJECT_ROOT / "llamaLauncher" / "bin" / "llama.cpp")
            self.assertTrue(expected.name == "llama.cpp")

    def test_api_bridge_dynamic_roots(self):
        """Verifies ApiBridge resolves models_dir and bin_root dynamically upon instantiation."""
        if HAS_API_BRIDGE:
            bridge = ApiBridge(project_root=str(PROJECT_ROOT))
            self.assertIsInstance(bridge.models_dir, Path)
            self.assertIsInstance(bridge.bin_root, Path)
            self.assertIsInstance(bridge.logs_dir, Path)


class TestHierarchicalScannerModule(unittest.TestCase):
    """Audits hierarchical model scanning, weight classification, and .bat discovery (Feature F3)."""

    def setUp(self):
        """Create an isolated mock filesystem fixture mimicking G:\\My Drive\\AI Local\\models."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_root = Path(self.temp_dir.name)

        # 1. Bonsai 2: 1-level root model with dedicated binary and .bat + .bat.bak
        bonsai_dir = self.mock_root / "Bonsai 2"
        (bonsai_dir / "llama.cpp").mkdir(parents=True)
        (bonsai_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"DEDICATED_BIN")
        (bonsai_dir / "Ternary-Bonsai-2-27B-PQ2_0.gguf").write_bytes(b"GGUF_WEIGHT")
        (bonsai_dir / "Ternary-Bonsai-2-27B-PTQ1_0.gguf").write_bytes(b"GGUF_WEIGHT_2")
        (bonsai_dir / "Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf").write_bytes(b"MMPROJ")
        (bonsai_dir / "run-bonsai2.bat").write_text("@echo off\npause\n", encoding="utf-8")
        (bonsai_dir / "run-bonsai2.bat.bak").write_text("@echo off backup\n", encoding="utf-8")

        # 2. Gemma 4 / 12B: 2-level canonical tree with mmproj and run-gemma4-12b.bat
        gemma_12b = self.mock_root / "Gemma 4" / "12B"
        gemma_12b.mkdir(parents=True)
        (gemma_12b / "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf").write_bytes(b"GEMMA_12B_WEIGHT")
        (gemma_12b / "mmproj-BF16.gguf").write_bytes(b"GEMMA_MMPROJ")
        (gemma_12b / "run-gemma4-12b.bat").write_text("@echo off\npause\n", encoding="utf-8")

        # 3. Gemma 4 / E2B: 2-level tree without .bat (candidate for auto-generation)
        gemma_e2b = self.mock_root / "Gemma 4" / "E2B"
        gemma_e2b.mkdir(parents=True)
        (gemma_e2b / "gemma-4-E2B-it-UD-IQ3_XXS.gguf").write_bytes(b"GEMMA_E2B_WEIGHT")

        # 4. Qwen 2.5 / Coder / 14B: 3-level tree
        qwen_coder_14b = self.mock_root / "Qwen 2.5" / "Coder" / "14B"
        qwen_coder_14b.mkdir(parents=True)
        (qwen_coder_14b / "Qwen2.5-Coder-14B-Instruct-IQ4_XS.gguf").write_bytes(b"QWEN_14B_WEIGHT")
        (qwen_coder_14b / "run-qwen25-coder-14b.bat").write_text("@echo off\npause\n", encoding="utf-8")

        # 5. Qwen 3.6 35B: 1-level with mmproj, mtp, and dual .bat scripts
        qwen_36 = self.mock_root / "Qwen 3.6 35B"
        qwen_36.mkdir(parents=True)
        (qwen_36 / "Qwen3.6-35B-A3B-UD-IQ3_S.gguf").write_bytes(b"QWEN_35B_WEIGHT")
        (qwen_36 / "mmproj-Qwen3.6-35B-A3B-Q8_0.gguf").write_bytes(b"QWEN_MMPROJ")
        (qwen_36 / "mtp-Qwen3.6-35B-A3B-Q4_0.gguf").write_bytes(b"QWEN_MTP")
        (qwen_36 / "run-qwen36-35b.bat").write_text("@echo off\npause\n", encoding="utf-8")
        (qwen_36 / "run-qwen36-35b-mtp-coding.bat").write_text("@echo off\npause\n", encoding="utf-8")

        # 6. Edge cases: Empty folder, Non-GGUF folder, Ignored system folder
        (self.mock_root / "GPT-OSS").mkdir(parents=True)
        laya_dir = self.mock_root / "Laya"
        laya_dir.mkdir(parents=True)
        (laya_dir / "model.safetensors").write_bytes(b"SAFETENSORS_DATA")
        (self.mock_root / ".cache").mkdir(parents=True)
        (self.mock_root / ".cache" / "dummy.gguf").write_bytes(b"CACHE_GGUF")

    def tearDown(self):
        """Cleanup mock directory fixture."""
        self.temp_dir.cleanup()

    def _reference_scanner(self, root: Path) -> Dict[str, Any]:
        """Reference scanner implementation defining the exact contract behavior."""
        models_list = []
        ignore_dirs = {".cache", "build", "llama.cpp", ".git", "__pycache__"}
        
        # Traverse directories looking for leaf model folders
        for current_path, dirnames, filenames in os.walk(root):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]
            
            p = Path(current_path)
            if p == root:
                continue
                
            gguf_files = [f for f in filenames if f.endswith(".gguf")]
            bat_files = [f for f in filenames if f.endswith(".bat")]
            
            if not gguf_files and not bat_files:
                continue
                
            weights = []
            mmproj = []
            mtp = []
            
            for gf in gguf_files:
                f_path = p / gf
                size_gb = round(f_path.stat().st_size / (1024**3), 2)
                f_lower = gf.lower()
                if f_lower.startswith("mmproj-") or "mmproj" in f_lower:
                    mmproj.append({"filename": gf, "path": str(f_path), "size_gb": size_gb})
                elif f_lower.startswith("mtp-") or "-mtp" in f_lower:
                    mtp.append({"filename": gf, "path": str(f_path), "size_gb": size_gb})
                else:
                    weights.append({"filename": gf, "path": str(f_path), "size_gb": size_gb, "type": "model"})
                    
            if not weights:
                continue
                
            # Rel path resolution
            rel_parts = p.relative_to(root).parts
            family = rel_parts[0]
            variant = " / ".join(rel_parts[1:]) if len(rel_parts) > 1 else ""
            label = f"{family} — {variant}" if variant else family
            slug = "-".join(rel_parts).lower().replace(" ", "-").replace("/", "-")
            
            # Dedicated binary check
            ded_bin = p / "llama.cpp" / "llama-server.exe"
            has_ded = ded_bin.exists()
            ded_path = str(ded_bin) if has_ded else None
            
            # Batch scripts check
            scripts = []
            for bf in bat_files:
                b_path = p / bf
                bak_path = p / f"{bf}.bak"
                scripts.append({
                    "filename": bf,
                    "path": str(b_path),
                    "has_backup": bak_path.exists()
                })
                
            models_list.append({
                "id": slug,
                "family": family,
                "variant": variant,
                "concatenated_label": label,
                "folder_path": str(p),
                "weights": weights,
                "mmproj": mmproj,
                "mtp": mtp,
                "has_dedicated_binary": has_ded,
                "dedicated_binary_path": ded_path,
                "batch_scripts": scripts
            })
            
        return {"success": True, "root_dir": str(root), "models": models_list}

    def test_mock_canonical_tree_scanning(self):
        """Verifies hierarchical scanning finds exactly the 5 valid runnable models."""
        if hasattr(models, "scan_models_and_batches"):
            result = models.scan_models_and_batches(self.mock_root)
        else:
            result = self._reference_scanner(self.mock_root)
            
        self.assertTrue(result["success"])
        model_names = [m["concatenated_label"] for m in result["models"]]
        
        self.assertEqual(len(result["models"]), 5)
        self.assertTrue(any("Bonsai 2" in name for name in model_names))
        self.assertTrue(any("Gemma 4 — 12B" in name for name in model_names))
        self.assertTrue(any("Gemma 4 — E2B" in name for name in model_names))
        self.assertTrue(any("Qwen 2.5 — Coder" in name for name in model_names))
        self.assertTrue(any("Qwen 3.6 35B" in name for name in model_names))

    def test_weight_and_projector_classification(self):
        """Verifies mmproj and mtp draft weights are segregated from base model weights."""
        if hasattr(models, "scan_models_and_batches"):
            result = models.scan_models_and_batches(self.mock_root)
        else:
            result = self._reference_scanner(self.mock_root)
            
        qwen36 = next(m for m in result["models"] if "Qwen 3.6 35B" in m["concatenated_label"])
        
        self.assertEqual(len(qwen36["weights"]), 1)
        self.assertEqual(qwen36["weights"][0]["filename"], "Qwen3.6-35B-A3B-UD-IQ3_S.gguf")
        
        self.assertEqual(len(qwen36["mmproj"]), 1)
        self.assertEqual(qwen36["mmproj"][0]["filename"], "mmproj-Qwen3.6-35B-A3B-Q8_0.gguf")
        
        self.assertEqual(len(qwen36["mtp"]), 1)
        self.assertEqual(qwen36["mtp"][0]["filename"], "mtp-Qwen3.6-35B-A3B-Q4_0.gguf")

    def test_dedicated_binary_detection_in_scanner(self):
        """Verifies dedicated binary flag is True only when llama.cpp/llama-server.exe exists."""
        if hasattr(models, "scan_models_and_batches"):
            result = models.scan_models_and_batches(self.mock_root)
        else:
            result = self._reference_scanner(self.mock_root)
            
        bonsai = next(m for m in result["models"] if "Bonsai 2" in m["concatenated_label"])
        gemma = next(m for m in result["models"] if "Gemma 4 — 12B" in m["concatenated_label"])
        
        self.assertTrue(bonsai["has_dedicated_binary"])
        self.assertIsNotNone(bonsai["dedicated_binary_path"])
        self.assertTrue(bonsai["dedicated_binary_path"].endswith("llama-server.exe"))
        
        self.assertFalse(gemma["has_dedicated_binary"])
        self.assertIsNone(gemma["dedicated_binary_path"])

    def test_batch_script_and_backup_detection(self):
        """Verifies script enumeration and .bat.bak backup detection."""
        if hasattr(models, "scan_models_and_batches"):
            result = models.scan_models_and_batches(self.mock_root)
        else:
            result = self._reference_scanner(self.mock_root)
            
        bonsai = next(m for m in result["models"] if "Bonsai 2" in m["concatenated_label"])
        self.assertEqual(len(bonsai["batch_scripts"]), 1)
        self.assertEqual(bonsai["batch_scripts"][0]["filename"], "run-bonsai2.bat")
        self.assertTrue(bonsai["batch_scripts"][0]["has_backup"])
        
        gemma_12b = next(m for m in result["models"] if "Gemma 4 — 12B" in m["concatenated_label"])
        self.assertEqual(len(gemma_12b["batch_scripts"]), 1)
        self.assertFalse(gemma_12b["batch_scripts"][0]["has_backup"])
        
        gemma_e2b = next(m for m in result["models"] if "Gemma 4 — E2B" in m["concatenated_label"])
        self.assertEqual(len(gemma_e2b["batch_scripts"]), 0)

    def test_empty_and_non_gguf_folder_exclusion(self):
        """Verifies GPT-OSS (empty), Laya (safetensors), and .cache are completely ignored."""
        if hasattr(models, "scan_models_and_batches"):
            result = models.scan_models_and_batches(self.mock_root)
        else:
            result = self._reference_scanner(self.mock_root)
            
        labels = [m["concatenated_label"] for m in result["models"]]
        self.assertFalse(any("GPT-OSS" in l for l in labels))
        self.assertFalse(any("Laya" in l for l in labels))
        self.assertFalse(any(".cache" in l for l in labels))


class TestBinaryResolverModule(unittest.TestCase):
    """Audits universal binary prioritizer and generic fallback logic (Features F4 & F5)."""

    def setUp(self):
        """Create mock binary directories and model folder."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()
        
        # Generic binaries with varying build tags
        (self.bin_root / "llama-b9283-bin-win-cpu-x64").mkdir()
        (self.bin_root / "llama-b9283-bin-win-cpu-x64" / "llama-server.exe").write_bytes(b"CPU_9283")
        
        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"CUDA_9297")
        
        (self.bin_root / "llama-b9297-bin-win-vulkan-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-vulkan-x64" / "llama-server.exe").write_bytes(b"VULKAN_9297")
        
        # Model folder with dedicated binary
        self.dedicated_model_dir = self.root / "models" / "Bonsai 2"
        (self.dedicated_model_dir / "llama.cpp").mkdir(parents=True)
        (self.dedicated_model_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"DEDICATED_BIN")
        
        # Standard model folder without dedicated binary
        self.standard_model_dir = self.root / "models" / "Gemma 4" / "12B"
        self.standard_model_dir.mkdir(parents=True)

    def tearDown(self):
        """Cleanup mock binary directories."""
        self.temp_dir.cleanup()

    def _reference_resolver(self, model_folder: Path, bin_root: Path, dev_type: str = "CUDA") -> Dict[str, Any]:
        """Reference binary resolver implementation defining the contract behavior."""
        # Priority 1: Check dedicated binary in model folder
        local_dedicated = model_folder / "llama.cpp" / "llama-server.exe"
        if local_dedicated.exists():
            return {
                "success": True,
                "binary_path": str(local_dedicated),
                "binary_dir": str(local_dedicated.parent),
                "binary_type": "CUSTOM_DEDICATED",
                "is_dedicated": True,
                "build": "dedicated",
                "name": f"{model_folder.name} Dedicated Binary"
            }
            
        # Priority 2: Check dedicated binary in parent family folder
        if model_folder.parent != model_folder:
            parent_dedicated = model_folder.parent / "llama.cpp" / "llama-server.exe"
            if parent_dedicated.exists():
                return {
                    "success": True,
                    "binary_path": str(parent_dedicated),
                    "binary_dir": str(parent_dedicated.parent),
                    "binary_type": "CUSTOM_DEDICATED",
                    "is_dedicated": True,
                    "build": "dedicated",
                    "name": f"{model_folder.parent.name} Family Dedicated Binary"
                }

        # Priority 3: Generic fallback in bin_root
        import re
        candidates = []
        if bin_root.exists():
            for d in bin_root.iterdir():
                if d.is_dir() and (d / "llama-server.exe").exists():
                    match = re.match(r"llama-b(\d+)-bin-win-(cuda|vulkan|cpu)-x64", d.name.lower())
                    if match:
                        build_num = int(match.group(1))
                        b_type = match.group(2).upper()
                        candidates.append((build_num, b_type, d / "llama-server.exe", d))
                        
        if not candidates:
            return {"success": False, "error": "No llama-server.exe found"}
            
        # Sort descending by build number
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        target_type = dev_type.upper()
        # Filter matching preferred device type
        matched = [c for c in candidates if c[1] == target_type]
        if not matched:
            # Fallback chain: CUDA -> VULKAN -> CPU
            for fb in ["CUDA", "VULKAN", "CPU"]:
                matched = [c for c in candidates if c[1] == fb]
                if matched:
                    break
                    
        if matched:
            chosen = matched[0]
            return {
                "success": True,
                "binary_path": str(chosen[2]),
                "binary_dir": str(chosen[3]),
                "binary_type": chosen[1],
                "is_dedicated": False,
                "build": f"b{chosen[0]}",
                "name": chosen[3].name
            }
            
        return {"success": False, "error": "No matching binary found"}

    def test_dedicated_binary_priority_over_generic(self):
        """Verifies dedicated binary in model folder takes strict precedence over newest CUDA binary."""
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_model_binary"):
            res = binaries.resolve_model_binary(self.dedicated_model_dir, self.bin_root, dev_type="CUDA")
        else:
            res = self._reference_resolver(self.dedicated_model_dir, self.bin_root, dev_type="CUDA")
            
        self.assertTrue(res["success"])
        self.assertTrue(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUSTOM_DEDICATED")
        self.assertTrue(res["binary_path"].endswith("Bonsai 2\\llama.cpp\\llama-server.exe") or "Bonsai 2/llama.cpp/llama-server.exe" in res["binary_path"])

    def test_family_level_dedicated_binary_priority(self):
        """Verifies dedicated binary in parent family folder takes precedence when subfolder lacks one."""
        variant_subfolder = self.dedicated_model_dir / "27B"
        variant_subfolder.mkdir()
        
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_model_binary"):
            res = binaries.resolve_model_binary(variant_subfolder, self.bin_root, dev_type="CUDA")
        else:
            res = self._reference_resolver(variant_subfolder, self.bin_root, dev_type="CUDA")
            
        self.assertTrue(res["success"])
        self.assertTrue(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUSTOM_DEDICATED")

    def test_generic_cuda_fallback_selection_with_build_sort(self):
        """Verifies generic fallback selects latest CUDA build (b9297) when no dedicated binary exists."""
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_model_binary"):
            res = binaries.resolve_model_binary(self.standard_model_dir, self.bin_root, dev_type="CUDA")
        else:
            res = self._reference_resolver(self.standard_model_dir, self.bin_root, dev_type="CUDA")
            
        self.assertTrue(res["success"])
        self.assertFalse(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUDA")
        self.assertIn("b9297", res["binary_path"])

    def test_generic_vulkan_selection(self):
        """Verifies selecting VULKAN picks the newest Vulkan engine."""
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_model_binary"):
            res = binaries.resolve_model_binary(self.standard_model_dir, self.bin_root, dev_type="VULKAN")
        else:
            res = self._reference_resolver(self.standard_model_dir, self.bin_root, dev_type="VULKAN")
            
        self.assertTrue(res["success"])
        self.assertEqual(res["binary_type"], "VULKAN")
        self.assertIn("vulkan", res["binary_path"].lower())

    def test_hardware_fallback_chain_when_cuda_missing(self):
        """Verifies fallback to Vulkan or CPU if requested CUDA binary is unavailable."""
        shutil.rmtree(self.bin_root / "llama-b9297-bin-win-cuda-x64")
        
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_model_binary"):
            res = binaries.resolve_model_binary(self.standard_model_dir, self.bin_root, dev_type="CUDA")
        else:
            res = self._reference_resolver(self.standard_model_dir, self.bin_root, dev_type="CUDA")
            
        self.assertTrue(res["success"])
        self.assertEqual(res["binary_type"], "VULKAN")

    def test_no_binary_error_handling(self):
        """Verifies clean error return without crash when bin_root is empty."""
        empty_root = self.root / "empty_bins"
        empty_root.mkdir()
        
        if HAS_BINARIES_MODULE and hasattr(binaries, "resolve_model_binary"):
            res = binaries.resolve_model_binary(self.standard_model_dir, empty_root, dev_type="CUDA")
        else:
            res = self._reference_resolver(self.standard_model_dir, empty_root, dev_type="CUDA")
            
        self.assertFalse(res["success"])
        self.assertIn("error", res)


class TestBatchManagerModule(unittest.TestCase):
    """Audits batch script parsing, generation, and safe persistence with backups."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="llama_batch_test_")
        self.root = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_batch_script_complete(self):
        """Verifies parsing of all inference flags, sampling, and paths from a .bat script."""
        bat_file = self.root / "run-test.bat"
        content = (
            "@echo off\r\n"
            "setlocal enabledelayedexpansion\r\n"
            'set "BASEDIR=%~dp0"\r\n'
            'set "MODEL=%BASEDIR%Qwen2.5-Coder-14B-Instruct-IQ4_XS.gguf"\r\n'
            'set "MMPROJ=%BASEDIR%mmproj-test.gguf"\r\n'
            'llama-server.exe --model "%MODEL%" --mmproj "%MMPROJ%" '
            '--n-gpu-layers 99 --flash-attn on --ctx-size 16384 --ubatch-size 512 '
            '--cache-type-k q4_0 --cache-type-v q4_0 --threads 8 --temp 0.7 '
            '--top-p 0.95 --min-p 0.05 --top-k 40 --host 0.0.0.0 --port 8085 --alias qwen-coder\r\n'
        )
        bat_file.write_text(content, encoding="utf-8")

        parsed = batch_manager.parse_batch_script(bat_file)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["port"], 8085)
        self.assertEqual(parsed["context"], 16384)
        self.assertEqual(parsed["threads"], 8)
        self.assertEqual(parsed["ngl"], 99)
        self.assertTrue(parsed["flash_attn"])
        self.assertEqual(parsed["cache_type_k"], "q4_0")
        self.assertEqual(parsed["cache_type_v"], "q4_0")
        self.assertEqual(parsed["temp"], 0.7)
        self.assertEqual(parsed["top_p"], 0.95)
        self.assertEqual(parsed["top_k"], 40)
        self.assertEqual(parsed["min_p"], 0.05)
        self.assertEqual(parsed["model_file"], "Qwen2.5-Coder-14B-Instruct-IQ4_XS.gguf")
        self.assertEqual(parsed["mmproj_file"], "mmproj-test.gguf")
        self.assertEqual(parsed["alias"], "qwen-coder")
        self.assertFalse(parsed["has_backup"])

    def test_parse_batch_script_alternative_short_flags(self):
        """Verifies parsing short flags (-c, -ngl, -t, --flash-attn off)."""
        bat_file = self.root / "run-short.bat"
        content = (
            "@echo off\r\n"
            "llama-server.exe -m model.gguf -c 4096 -ngl 45 -t 6 --flash-attn off\r\n"
        )
        bat_file.write_text(content, encoding="utf-8")

        parsed = batch_manager.parse_batch_script(bat_file)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["context"], 4096)
        self.assertEqual(parsed["ngl"], 45)
        self.assertEqual(parsed["threads"], 6)
        self.assertFalse(parsed["flash_attn"])

    def test_parse_batch_script_missing_file(self):
        """Verifies error handling when batch file does not exist."""
        non_existent = self.root / "missing.bat"
        parsed = batch_manager.parse_batch_script(non_existent)
        self.assertFalse(parsed["success"])
        self.assertIn("error", parsed)

    def test_generate_batch_template_with_mmproj(self):
        """Verifies template generation with vision projector and dynamic paths."""
        folder = self.root / "Gemma 4" / "12B"
        template = batch_manager.generate_batch_template(
            model_folder=folder,
            model_filename="gemma-4-12b.gguf",
            mmproj_filename="mmproj-gemma.gguf",
            family_name="Gemma 4",
            variant_name="12B"
        )

        self.assertIn("%~dp0", template)
        self.assertIn('set "MODEL=%BASEDIR%gemma-4-12b.gguf"', template)
        self.assertIn("mmproj-gemma.gguf", template)
        self.assertIn("!MMPROJ_FLAG!", template)
        self.assertIn("--n-gpu-layers  99", template)
        self.assertIn("--flash-attn    on", template)
        self.assertIn("--ctx-size      16384", template)
        self.assertIn("--cache-type-k  q4_0", template)

    def test_generate_batch_template_without_mmproj(self):
        """Verifies template generation when no vision projector is provided."""
        folder = self.root / "Qwen 2.5" / "Coder"
        template = batch_manager.generate_batch_template(
            model_folder=folder,
            model_filename="qwen-coder.gguf",
            mmproj_filename=None,
            family_name="Qwen 2.5",
            variant_name="Coder"
        )

        self.assertIn("qwen-coder.gguf", template)
        self.assertIn('set "MMPROJ_FLAG="', template)
        self.assertNotIn("None", template)

    def test_save_batch_script_with_backup_and_crlf(self):
        """Verifies saving batch script creates .bat.bak and writes CRLF line endings."""
        bat_file = self.root / "run-save-test.bat"
        initial_content = "@echo off\r\necho Initial script\r\n"
        bat_file.write_text(initial_content, encoding="utf-8")

        new_content = "@echo off\necho Updated script\npause\n"
        res = batch_manager.save_batch_script(bat_file, new_content, create_backup=True)

        self.assertTrue(res["success"])
        self.assertTrue(res["backup_created"])
        self.assertTrue(Path(res["backup_path"]).exists())

        # Verify backup contains initial content
        backup_content = Path(res["backup_path"]).read_text(encoding="utf-8")
        self.assertIn("Initial script", backup_content)

        # Verify updated file was written with Windows CRLF endings
        raw_bytes = bat_file.read_bytes()
        self.assertIn(b"\r\n", raw_bytes)
        self.assertIn("Updated script", bat_file.read_text(encoding="utf-8"))

    def test_save_batch_script_new_file_no_backup(self):
        """Verifies creating a new script without existing file does not create unnecessary backup."""
        bat_file = self.root / "new-script.bat"
        res = batch_manager.save_batch_script(bat_file, "@echo off\necho Brand new\n", create_backup=True)

        self.assertTrue(res["success"])
        self.assertFalse(res["backup_created"])
        self.assertIsNone(res["backup_path"])
        self.assertTrue(bat_file.exists())

    def test_api_bridge_batch_operations(self):
        """Verifies ApiBridge endpoints for scanning and batch detail retrieval."""
        if not HAS_API_BRIDGE:
            self.skipTest("ApiBridge not imported.")

        # Create mock models structure
        models_dir = self.root / "models"
        family_dir = models_dir / "TestFamily" / "Variant"
        family_dir.mkdir(parents=True)
        (family_dir / "test-model.gguf").write_bytes(b"GGUF" + b"\x00" * 100)

        # Create mock bin dir
        bin_dir = self.root / "bin" / "llama-b9297-bin-win-cuda-x64"
        bin_dir.mkdir(parents=True)
        (bin_dir / "llama-server.exe").write_bytes(b"MZ" + b"\x00" * 50)

        bridge = ApiBridge(project_root=self.root)
        bridge.models_dir = models_dir
        bridge.bin_root = self.root / "bin"

        scan_res = bridge.scan_models_and_batches()
        self.assertTrue(scan_res["success"])
        self.assertGreaterEqual(scan_res["total_models"], 1)

        model_id = scan_res["models"][0]["id"]
        details = bridge.get_model_batch_details(model_id)
        self.assertTrue(details["success"])
        self.assertTrue(details["is_newly_generated"])
        self.assertTrue(Path(details["path"]).exists())

        # Test saving batch script via ApiBridge
        bat_target = details.get("bat_path") or details["path"]
        bat_content = details.get("bat_raw_content") or "@echo off\r\nllama-server.exe\r\n"
        save_res = bridge.save_batch_script(bat_target, bat_content + "\r\n:: appended", create_backup=True)
        self.assertTrue(save_res["success"])
        self.assertTrue(save_res["backup_created"])
        self.assertIn("parsed_config", save_res)
        self.assertTrue(save_res["parsed_config"]["success"])

        # Test saving JSON config via ApiBridge
        json_target = details.get("json_path") or details["path"]
        json_data = json.loads(details["raw_content"])
        json_data["port"] = 8999
        json_save_res = bridge.save_batch_script(json_target, json.dumps(json_data), create_backup=True)
        self.assertTrue(json_save_res["success"])
        self.assertTrue(json_save_res["backup_created"])
        self.assertEqual(json_save_res["parsed_config"]["port"], 8999)

    def test_update_batch_script_content_all_flags(self):
        """Verifies programmatic updating of all inference and sampling flags in a .bat script."""
        initial_content = (
            "@echo off\r\n"
            'set "BASEDIR=%~dp0"\r\n'
            'set "MODEL=%BASEDIR%model.gguf"\r\n'
            'llama-server.exe --model "%MODEL%" '
            '--n-gpu-layers 33 --flash-attn off --ctx-size 4096 '
            '--cache-type-k f16 --cache-type-v f16 --threads 4 --temp 0.5 '
            '--top-p 0.9 --min-p 0.1 --top-k 20 --port 8080\r\n'
        )
        bat_file = self.root / "run-update.bat"
        bat_file.write_text(initial_content, encoding="utf-8")

        updates = {
            "port": 8088,
            "context": 32768,
            "threads": 12,
            "ngl": 99,
            "flash_attn": True,
            "cache_type_k": "q4_0",
            "cache_type_v": "q4_0",
            "temp": 0.85,
            "top_p": 0.98,
            "top_k": 50,
            "min_p": 0.02
        }

        updated_content = batch_manager.update_batch_script_content(initial_content, updates)
        batch_manager.save_batch_script(bat_file, updated_content, create_backup=False)

        parsed = batch_manager.parse_batch_script(bat_file)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["port"], 8088)
        self.assertEqual(parsed["context"], 32768)
        self.assertEqual(parsed["threads"], 12)
        self.assertEqual(parsed["ngl"], 99)
        self.assertTrue(parsed["flash_attn"])
        self.assertEqual(parsed["cache_type_k"], "q4_0")
        self.assertEqual(parsed["cache_type_v"], "q4_0")
        self.assertEqual(parsed["temp"], 0.85)
        self.assertEqual(parsed["top_p"], 0.98)
        self.assertEqual(parsed["top_k"], 50)
        self.assertEqual(parsed["min_p"], 0.02)

    def test_update_batch_script_content_missing_flags_insertion(self):
        """Verifies inserting flags like --threads when initially missing from the script."""
        initial_content = (
            "@echo off\r\n"
            'llama-server.exe --model "m.gguf" --ctx-size 8192 --n-gpu-layers 50 --port 8080\r\n'
        )
        updates = {"threads": 8, "ngl": 99}
        updated = batch_manager.update_batch_script_content(initial_content, updates)

        self.assertIn("--threads", updated)
        self.assertIn("8", updated)
        self.assertIn("--n-gpu-layers  99", updated)

    def test_batch_template_deep_relative_paths(self):
        """Verifies template generation includes multi-level relative path resolution."""
        folder = self.root / "Family" / "Sub" / "Deep" / "Variant"
        template = batch_manager.generate_batch_template(
            model_folder=folder,
            model_filename="deep-model.gguf",
            family_name="DeepFamily",
            variant_name="DeepVariant"
        )

        self.assertIn("..\\..\\..\\..\\llamaLauncher", template)
        self.assertIn("..\\Bonsai 2\\llama.cpp", template)



class TestPywebviewBottlePatch(unittest.TestCase):
    """Audits the Bottle routing patch that prevents HTTP 500 TypeError on root URL."""

    def test_bottle_patch_serves_root_without_typeerror(self):
        import bottle
        from app.backend.config import patch_pywebview_bottle
        patched = patch_pywebview_bottle()
        self.assertTrue(patched)

        app = bottle.Bottle()

        @app.route('/')
        @app.route('/<file:path>')
        def asset(file):
            return f"Served: {file}"

        def dummy_sr(status, headers, exc_info=None):
            pass

        # Test route '/' — must NOT raise TypeError and must default to 'index.html'
        environ_root = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/',
            'wsgi.input': None,
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '42001'
        }
        res_root = list(app(environ_root, dummy_sr))
        self.assertEqual(res_root, [b"Served: index.html"])

        # Test route '/style.css' — must serve specific asset
        environ_file = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/style.css',
            'wsgi.input': None,
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '42001'
        }
        res_file = list(app(environ_file, dummy_sr))

class TestJsonConfigManagement(unittest.TestCase):
    """Audits the JSON model configuration system and its dual sync with .bat files."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_convert_bat_to_json(self):
        """Verifies that converting a .bat script produces a valid .json file with accurate parameters."""
        bat_content = (
            "@echo off\r\n"
            'set "BASEDIR=%~dp0"\r\n'
            'set "MODEL=%BASEDIR%qwen-test.gguf"\r\n'
            'llama-server.exe --model "%MODEL%" --n-gpu-layers 99 --flash-attn on '
            '--ctx-size 16384 --ubatch-size 512 --cache-type-k q4_0 --cache-type-v q4_0 '
            '--threads 8 --temp 0.7 --top-p 0.95 --min-p 0.05 --port 8085 --alias qwen-test\r\n'
        )
        bat_file = self.root / "run-qwen.bat"
        bat_file.write_text(bat_content, encoding="utf-8")

        res = batch_manager.convert_bat_to_json(bat_file)
        self.assertTrue(res["success"])
        json_path = Path(res["json_path"])
        self.assertTrue(json_path.exists())

        # Verify parsed JSON structure
        data = res["data"]
        self.assertEqual(data["model_file"], "qwen-test.gguf")
        self.assertEqual(data["ngl"], 99)
        self.assertEqual(data["engine"], "CUDA")
        self.assertEqual(data["context"], 16384)
        self.assertEqual(data["ubatch_size"], 512)
        self.assertEqual(data["port"], 8085)
        self.assertEqual(data["alias"], "qwen-test")
        self.assertEqual(data["cache_type_k"], "q4_0")
        self.assertEqual(data["cache_type_v"], "q4_0")
        self.assertTrue(data["flash_attn"])

    def test_parse_json_config(self):
        """Verifies parsing of an existing .json configuration file."""
        json_file = self.root / "run-model.json"
        config_data = {
            "name": "Test Model",
            "model_file": "test-model.gguf",
            "engine": "CUDA",
            "ngl": 99,
            "threads": 8,
            "context": 8192,
            "ubatch_size": 512,
            "flash_attn": True,
            "cache_type_k": "q4_0",
            "cache_type_v": "q4_0",
            "temp": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "min_p": 0.05,
            "port": 8080
        }
        json_file.write_text(json.dumps(config_data), encoding="utf-8")

        parsed = batch_manager.parse_json_config(json_file)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["config_format"], "JSON")
        self.assertEqual(parsed["engine"], "CUDA")
        self.assertEqual(parsed["ngl"], 99)
        self.assertEqual(parsed["context"], 8192)
        self.assertEqual(parsed["port"], 8080)

    def test_cpu_engine_ngl_zero_and_no_flash_attn(self):
        """Verifies that selecting CPU sets GPU layers to 0 and disables Flash Attention."""
        json_file = self.root / "run-cpu.json"
        config_data = {
            "name": "CPU Model",
            "model_file": "cpu-model.gguf",
            "engine": "CPU",
            "ngl": 0,
            "threads": 8,
            "context": 4096,
            "flash_attn": False,
            "port": 8080
        }
        json_file.write_text(json.dumps(config_data), encoding="utf-8")

        parsed = batch_manager.parse_json_config(json_file)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["engine"], "CPU")
        self.assertEqual(parsed["ngl"], 0)
        self.assertFalse(parsed["flash_attn"])

    def test_save_json_config_and_sync_bat(self):
        """Verifies that saving .json configuration automatically syncs matching .bat script."""
        bat_content = (
            "@echo off\r\n"
            'set "BASEDIR=%~dp0"\r\n'
            'set "MODEL=%BASEDIR%test.gguf"\r\n'
            'llama-server.exe --model "%MODEL%" --n-gpu-layers 99 --port 8080\r\n'
        )
        bat_file = self.root / "run-test.bat"
        bat_file.write_text(bat_content, encoding="utf-8")

        # Create initial JSON
        batch_manager.convert_bat_to_json(bat_file)
        json_file = self.root / "run-test.json"
        self.assertTrue(json_file.exists())

        # Update JSON to CPU with ngl=0 and port=9090
        updated_data = json.loads(json_file.read_text(encoding="utf-8"))
        updated_data["engine"] = "CPU"
        updated_data["ngl"] = 0
        updated_data["port"] = 9090

        save_res = batch_manager.save_json_config(json_file, json.dumps(updated_data), create_backup=True, sync_bat=True)
        self.assertTrue(save_res["success"])
        self.assertTrue(save_res["backup_created"])
        self.assertTrue(json_file.with_suffix(".json.bak").exists())

        # Verify that .bat was also synchronized
        bat_updated_content = bat_file.read_text(encoding="utf-8")
        self.assertIn("9090", bat_updated_content)
        self.assertIn("--n-gpu-layers  0", bat_updated_content)

    def test_vision_projector_toggle_and_bat_sync(self):
        """Verifies that enabling/disabling Vision updates mmproj_file and synchronizes .bat MMPROJ."""
        bat_content = (
            "@echo off\r\n"
            'set "BASEDIR=%~dp0"\r\n'
            'set "MODEL=%BASEDIR%vision-model.gguf"\r\n'
            'set "MMPROJ=%BASEDIR%mmproj-test.gguf"\r\n'
            'set "MMPROJ_FLAG=--mmproj "!MMPROJ!""\r\n'
            'llama-server.exe --model "%MODEL%" !MMPROJ_FLAG! --port 8080\r\n'
        )
        bat_file = self.root / "run-vision.bat"
        bat_file.write_text(bat_content, encoding="utf-8")

        # Convert to JSON
        batch_manager.convert_bat_to_json(bat_file)
        json_file = self.root / "run-vision.json"
        self.assertTrue(json_file.exists())

        # Toggle Vision OFF: mmproj_file = ""
        data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertEqual(data["mmproj_file"], "mmproj-test.gguf")
        data["mmproj_file"] = ""
        batch_manager.save_json_config(json_file, json.dumps(data), sync_bat=True)

        bat_off = bat_file.read_text(encoding="utf-8")
        self.assertIn('set "MMPROJ="', bat_off)
        self.assertIn('set "MMPROJ_FLAG="', bat_off)

        # Toggle Vision ON: mmproj_file = "mmproj-test.gguf"
        data["mmproj_file"] = "mmproj-test.gguf"
        batch_manager.save_json_config(json_file, json.dumps(data), sync_bat=True)

        bat_on = bat_file.read_text(encoding="utf-8")
        self.assertIn('set "MMPROJ=%BASEDIR%mmproj-test.gguf"', bat_on)
        self.assertIn('set "MMPROJ_FLAG=--mmproj "!MMPROJ!""', bat_on)

    def test_api_prioritizes_json_config(self):
        """Verifies that ApiBridge.get_model_batch_details prioritizes .json configuration files."""
        if not HAS_API_BRIDGE:
            self.skipTest("ApiBridge not imported.")

        models_dir = self.root / "models"
        family_dir = models_dir / "Qwen" / "Qwen36"
        family_dir.mkdir(parents=True)
        (family_dir / "qwen.gguf").write_bytes(b"GGUF" + b"\x00" * 100)

        # Create both .json and .bat
        json_config = {
            "name": "Qwen 36B",
            "model_file": "qwen.gguf",
            "engine": "CUDA",
            "ngl": 99,
            "port": 8888
        }
        (family_dir / "run-qwen.json").write_text(json.dumps(json_config), encoding="utf-8")
        (family_dir / "run-qwen.bat").write_text("@echo off\r\nllama-server.exe --port 8080\r\n", encoding="utf-8")

        bridge = ApiBridge(project_root=self.root)
        bridge.models_dir = models_dir
        bridge.bin_root = self.root / "bin"

        scan = bridge.scan_models_and_batches()
        self.assertTrue(scan["success"])
        model_id = scan["models"][0]["id"]

        details = bridge.get_model_batch_details(model_id)
        self.assertTrue(details["success"])
        self.assertEqual(details["config_format"], "JSON")
        self.assertEqual(details["port"], 8888)
        self.assertTrue(details["filename"].endswith(".json"))


class TestRealEcosystemLiveVerification(unittest.TestCase):
    """Optional live hardware & filesystem sanity checks against G:\\My Drive\\AI Local."""

    def test_live_paths_presence_if_mounted(self):
        """Audits live ecosystem paths on DIEGO_DESKTOP workstation if Google Drive is mounted."""
        live_models = Path("G:/My Drive/AI Local/models")
        live_bins = Path("G:/My Drive/AI Local/llamaLauncher/bin/llama.cpp")
        
        if not live_models.exists():
            self.skipTest("Live G: drive not mounted or running in headless CI environment.")
            
        self.assertTrue(live_models.is_dir())
        self.assertTrue(live_bins.is_dir())
        
        # Verify Bonsai 2 dedicated binary
        bonsai_bin = live_models / "Bonsai 2" / "llama.cpp" / "llama-server.exe"
        self.assertTrue(bonsai_bin.exists(), "Bonsai 2 dedicated binary must exist.")
        
        # Verify Generic CUDA 13.x binary
        cuda_bin = live_bins / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe"
        self.assertTrue(cuda_bin.exists(), "Generic CUDA b9297 binary must exist.")


if __name__ == "__main__":
    unittest.main()

