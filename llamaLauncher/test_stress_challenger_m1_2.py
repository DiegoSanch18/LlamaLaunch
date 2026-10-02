#!/usr/bin/env python3
"""
Adversarial Empirical Stress Test Suite for Milestone 1 (M1)
Challenger Agent: teamwork_preview_challenger_m1_2
=============================================================
Stress-tests:
1. Dedicated binary precedence under extreme conditions (older dedicated vs newer b10000+ CUDA).
2. Priority 2 family parent folder resolution across different folder depths (1, 2, 3, 4 levels) & neighbor isolation.
3. Integer build sorting with future build numbers (b10000+, b99999, b800, leading zeroes, multi-backend mix).
4. Non-standard folder names, empty folders, missing executables, directory-as-exe, and files in bin_root.
5. Windows CUDA DLL verification (runtime present, runtime absent, empty runtime, already present).
6. ApiBridge facade robustness across edge-case parameters (None, file paths, non-existent directories).
"""

import unittest
import sys
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any

# Ensure project root and llamaLauncher are in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import app.backend.binaries as binaries
import app.backend.hardware as hardware
from app.backend.api import ApiBridge


class TestDedicatedPrecedenceStress(unittest.TestCase):
    """Stress-tests dedicated binary precedence over generic binaries under adversarial conditions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()
        self.models_dir = self.root / "models"
        self.models_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dedicated_takes_priority_over_future_higher_build_cuda(self):
        """
        Adversarial Scenario:
        Model has an old/custom dedicated binary.
        Generic bin_root has an ultra-new future CUDA binary (b99999).
        Expectation: Dedicated binary MUST be selected, NOT the b99999 generic CUDA binary.
        """
        # Create ultra-new generic CUDA binary
        future_cuda = self.bin_root / "llama-b99999-bin-win-cuda-x64"
        future_cuda.mkdir()
        (future_cuda / "llama-server.exe").write_bytes(b"GENERIC_B99999_CUDA")

        # Create model with dedicated binary
        model_dir = self.models_dir / "Bonsai 2"
        (model_dir / "llama.cpp").mkdir(parents=True)
        (model_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"OLD_DEDICATED_TERNARY")

        res = binaries.resolve_model_binary(model_dir, self.bin_root, dev_type="CUDA")
        self.assertTrue(res["success"], f"Resolution failed: {res.get('error')}")
        self.assertTrue(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUSTOM_DEDICATED")
        self.assertEqual(Path(res["binary_path"]), (model_dir / "llama.cpp" / "llama-server.exe").resolve())

    def test_force_generic_bypasses_dedicated(self):
        """
        Scenario:
        Model has dedicated binary, but force_generic=True is passed.
        Expectation: Generic binary is selected, dedicated is ignored.
        """
        gen_cuda = self.bin_root / "llama-b9297-bin-win-cuda-x64"
        gen_cuda.mkdir()
        (gen_cuda / "llama-server.exe").write_bytes(b"CUDA_9297")

        model_dir = self.models_dir / "Bonsai 2"
        (model_dir / "llama.cpp").mkdir(parents=True)
        (model_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"DEDICATED")

        res = binaries.resolve_model_binary(model_dir, self.bin_root, dev_type="CUDA", force_generic=True)
        self.assertTrue(res["success"])
        self.assertFalse(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUDA")
        self.assertEqual(Path(res["binary_path"]), (gen_cuda / "llama-server.exe").resolve())


class TestFamilyDepthAndIsolationStress(unittest.TestCase):
    """Stress-tests family folder traversal across different directory depths and isolation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()
        # Add a generic fallback
        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"CUDA")

        self.models_dir = self.root / "models"
        self.models_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_depth_1_direct_dedicated(self):
        """Depth 1: models/Family has dedicated binary."""
        family_dir = self.models_dir / "SingleFamily"
        (family_dir / "llama.cpp").mkdir(parents=True)
        (family_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"EXE")

        res = binaries.resolve_model_binary(family_dir, self.bin_root)
        self.assertTrue(res["is_dedicated"])
        self.assertEqual(Path(res["binary_path"]), (family_dir / "llama.cpp" / "llama-server.exe").resolve())

    def test_depth_2_variant_inherits_family_dedicated(self):
        """Depth 2: models/Family/Variant inherits from models/Family."""
        family_dir = self.models_dir / "Gemma 4"
        variant_dir = family_dir / "12B"
        variant_dir.mkdir(parents=True)
        (family_dir / "llama.cpp").mkdir(parents=True)
        (family_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"FAMILY_EXE")

        res = binaries.resolve_model_binary(variant_dir, self.bin_root)
        self.assertTrue(res["is_dedicated"])
        self.assertEqual(Path(res["binary_path"]), (family_dir / "llama.cpp" / "llama-server.exe").resolve())

    def test_depth_3_subvariant_inherits_family_dedicated(self):
        """Depth 3: models/Family/Category/Variant (e.g. Qwen 2.5/Coder/14B) inherits from models/Family."""
        family_dir = self.models_dir / "Qwen 2.5"
        subvariant_dir = family_dir / "Coder" / "14B"
        subvariant_dir.mkdir(parents=True)
        (family_dir / "llama.cpp").mkdir(parents=True)
        (family_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"FAMILY_EXE")

        res = binaries.resolve_model_binary(subvariant_dir, self.bin_root)
        self.assertTrue(res["is_dedicated"])
        self.assertEqual(Path(res["binary_path"]), (family_dir / "llama.cpp" / "llama-server.exe").resolve())

    def test_depth_4_boundary_check(self):
        """
        Depth 4: models/Family/Cat1/Cat2/Variant (3 levels above variant).
        find_dedicated_binary loops range(2), checking variant.parent (Cat2) and variant.parent.parent (Cat1).
        It will not reach Family. Documents boundary behavior.
        """
        family_dir = self.models_dir / "DeepFamily"
        deep_dir = family_dir / "Cat1" / "Cat2" / "Variant"
        deep_dir.mkdir(parents=True)
        (family_dir / "llama.cpp").mkdir(parents=True)
        (family_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"FAMILY_EXE")

        res = binaries.resolve_model_binary(deep_dir, self.bin_root)
        # Depth 4 exceeds the 2-level parent traversal, falls back to generic
        self.assertFalse(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUDA")

    def test_neighbor_family_isolation(self):
        """Neighbor family's dedicated binary must NOT be picked by a model without dedicated binary."""
        family_a = self.models_dir / "FamilyA"
        (family_a / "llama.cpp").mkdir(parents=True)
        (family_a / "llama.cpp" / "llama-server.exe").write_bytes(b"FAMILY_A_EXE")

        family_b = self.models_dir / "FamilyB" / "Variant"
        family_b.mkdir(parents=True)

        res = binaries.resolve_model_binary(family_b, self.bin_root)
        self.assertFalse(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUDA")

    def test_models_root_guard(self):
        """
        If models/llama.cpp/llama-server.exe exists at the root models directory,
        it should NOT be treated as a dedicated model binary.
        """
        (self.models_dir / "llama.cpp").mkdir(parents=True)
        (self.models_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"ROOT_EXE")

        model_dir = self.models_dir / "TestModel"
        model_dir.mkdir()

        res = binaries.resolve_model_binary(model_dir, self.bin_root)
        self.assertFalse(res["is_dedicated"])
        self.assertEqual(res["binary_type"], "CUDA")


class TestIntegerBuildSortingStress(unittest.TestCase):
    """Stress-tests integer build number extraction and sorting, especially b10000+ vs b9297."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_b10000_sorts_strictly_before_b9297(self):
        """
        Lexicographical vs Integer Sorting:
        Lexicographically, 'b9297' > 'b10000' (because '9' > '1').
        Integer sorting must place b10000 before b9297.
        """
        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"B9297")

        (self.bin_root / "llama-b10000-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b10000-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"B10000")

        (self.bin_root / "llama-b9283-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9283-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"B9283")

        bins = binaries.scan_generic_binaries(self.bin_root)
        self.assertEqual(len(bins), 3)
        build_nums = [b["build_num"] for b in bins]
        self.assertEqual(build_nums, [10000, 9297, 9283])
        self.assertEqual(bins[0]["build"], "b10000")

        # Resolving CUDA must pick b10000
        res = binaries.resolve_model_binary(None, self.bin_root, dev_type="CUDA")
        self.assertTrue(res["success"])
        self.assertEqual(res["build"], "b10000")
        self.assertIn("b10000", res["binary_path"])

    def test_multi_digit_spectrum_sorting(self):
        """Tests build spectrum: b800, b9283, b9297, b10500, b99999."""
        builds = [800, 9283, 9297, 10500, 99999]
        for b in builds:
            d = self.bin_root / f"llama-b{b}-bin-win-cuda-x64"
            d.mkdir()
            (d / "llama-server.exe").write_bytes(b"EXE")

        scanned = binaries.scan_generic_binaries(self.bin_root)
        scanned_nums = [s["build_num"] for s in scanned]
        self.assertEqual(scanned_nums, [99999, 10500, 9297, 9283, 800])

    def test_multi_backend_build_competition(self):
        """
        Scenario:
        CPU build is b15000 (higher number), but CUDA build is b9297.
        When dev_type='CUDA' is requested, it MUST select CUDA b9297, not CPU b15000.
        When dev_type='CPU' is requested, it MUST select CPU b15000.
        """
        (self.bin_root / "llama-b15000-bin-win-cpu-x64").mkdir()
        (self.bin_root / "llama-b15000-bin-win-cpu-x64" / "llama-server.exe").write_bytes(b"CPU_15000")

        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"CUDA_9297")

        res_cuda = binaries.resolve_model_binary(None, self.bin_root, dev_type="CUDA")
        self.assertEqual(res_cuda["binary_type"], "CUDA")
        self.assertEqual(res_cuda["build"], "b9297")

        res_cpu = binaries.resolve_model_binary(None, self.bin_root, dev_type="CPU")
        self.assertEqual(res_cpu["binary_type"], "CPU")
        self.assertEqual(res_cpu["build"], "b15000")


class TestNonStandardDirectoriesStress(unittest.TestCase):
    """Stress-tests bin_root with corruptions, non-standard names, empty folders, and stray files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_non_standard_folder_names(self):
        """
        Folders like:
        - 'llama-custom-build-cuda' (matches fallback heuristic)
        - 'my-engine-vulkan' (matches fallback heuristic)
        - 'plain-folder' (fallback GENERIC)
        """
        (self.bin_root / "llama-custom-build-cuda").mkdir()
        (self.bin_root / "llama-custom-build-cuda" / "llama-server.exe").write_bytes(b"EXE1")

        (self.bin_root / "my-engine-vulkan").mkdir()
        (self.bin_root / "my-engine-vulkan" / "llama-server.exe").write_bytes(b"EXE2")

        (self.bin_root / "plain-engine").mkdir()
        (self.bin_root / "plain-engine" / "llama-server.exe").write_bytes(b"EXE3")

        bins = binaries.scan_generic_binaries(self.bin_root)
        self.assertEqual(len(bins), 3)

        type_map = {b["name"]: b["binary_type"] for b in bins}
        self.assertEqual(type_map["llama-custom-build-cuda"], "CUDA")
        self.assertEqual(type_map["my-engine-vulkan"], "VULKAN")
        self.assertEqual(type_map["plain-engine"], "GENERIC")

        # Resolving CUDA should find llama-custom-build-cuda
        res = binaries.resolve_model_binary(None, self.bin_root, dev_type="CUDA")
        self.assertTrue(res["success"])
        self.assertEqual(res["name"], "llama-custom-build-cuda")

    def test_missing_server_exe_folders_ignored(self):
        """Folders without llama-server.exe (e.g. empty or only notes) must be cleanly ignored."""
        (self.bin_root / "empty-folder").mkdir()
        (self.bin_root / "llama-b9999-missing-exe").mkdir()
        (self.bin_root / "llama-b9999-missing-exe" / "readme.txt").write_text("no exe")

        # Add 1 valid folder
        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"VALID")

        bins = binaries.scan_generic_binaries(self.bin_root)
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0]["name"], "llama-b9297-bin-win-cuda-x64")

    def test_stray_files_in_bin_root_ignored(self):
        """Stray files (including a stray llama-server.exe in bin_root directly) should not crash."""
        (self.bin_root / "notes.txt").write_text("some notes")
        (self.bin_root / "llama-server.exe").write_bytes(b"STRAY_EXE")

        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"VALID")

        bins = binaries.scan_generic_binaries(self.bin_root)
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0]["name"], "llama-b9297-bin-win-cuda-x64")

    def test_directory_named_llama_server_exe_ignored(self):
        """Adversarial case: a directory named 'llama-server.exe' inside a binary folder."""
        bogus_folder = self.bin_root / "llama-b9999-bogus"
        bogus_folder.mkdir()
        (bogus_folder / "llama-server.exe").mkdir() # directory, not file!

        bins = binaries.scan_generic_binaries(self.bin_root)
        self.assertEqual(len(bins), 0, "Directory named llama-server.exe must not be treated as executable file.")


class TestWindowsCudaDllVerificationStress(unittest.TestCase):
    """Stress-tests Windows CUDA acceleration DLL copy logic and missing source behavior."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()
        self.cuda_dir = self.bin_root / "llama-b9297-bin-win-cuda-x64"
        self.cuda_dir.mkdir()
        (self.cuda_dir / "llama-server.exe").write_bytes(b"CUDA_EXE")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dlls_already_present_requires_no_copy(self):
        """When cublas64_*.dll and cublasLt64_*.dll exist, returns True without copying."""
        (self.cuda_dir / "cublas64_12.dll").write_bytes(b"CUBLAS")
        (self.cuda_dir / "cublasLt64_12.dll").write_bytes(b"CUBLAS_LT")

        verified = hardware.check_and_copy_cuda_dlls(self.cuda_dir, self.bin_root)
        self.assertTrue(verified)

        res = binaries.resolve_model_binary(None, self.bin_root, dev_type="CUDA")
        self.assertTrue(res["success"])
        self.assertTrue(res["cuda_dlls_verified"])

    def test_missing_dlls_with_source_copies_successfully(self):
        """When DLLs are missing and source cudart dir is present, copies all DLLs."""
        source_dir = self.bin_root / "cudart-llama-bin-win-cuda-13.1-x64"
        source_dir.mkdir()
        (source_dir / "cublas64_12.dll").write_bytes(b"SOURCE_CUBLAS")
        (source_dir / "cublasLt64_12.dll").write_bytes(b"SOURCE_CUBLAS_LT")
        (source_dir / "cudart64_13.dll").write_bytes(b"SOURCE_CUDART")

        verified = hardware.check_and_copy_cuda_dlls(self.cuda_dir, self.bin_root)
        self.assertTrue(verified)
        self.assertTrue((self.cuda_dir / "cublas64_12.dll").exists())
        self.assertTrue((self.cuda_dir / "cublasLt64_12.dll").exists())
        self.assertTrue((self.cuda_dir / "cudart64_13.dll").exists())

    def test_missing_dlls_without_source_returns_false_safely(self):
        """When DLLs are missing and source cudart dir is absent, returns False without crashing."""
        # Note: self.cuda_dir has no DLLs, and self.bin_root has no cudart folder
        verified = hardware.check_and_copy_cuda_dlls(self.cuda_dir, self.bin_root)
        if sys.platform == "win32":
            self.assertFalse(verified)

        # resolve_model_binary should succeed with cuda_dlls_verified=False
        res = binaries.resolve_model_binary(None, self.bin_root, dev_type="CUDA")
        self.assertTrue(res["success"])
        if sys.platform == "win32":
            self.assertFalse(res["cuda_dlls_verified"])


class TestApiBridgeFacadeStress(unittest.TestCase):
    """Stress-tests ApiBridge integration with binary resolution endpoints."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bridge = ApiBridge(project_root=str(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_model_binary_empty_inputs(self):
        """Tests ApiBridge.resolve_model_binary with empty string, non-existent folder."""
        # Non-existent folder
        res_nonexistent = self.bridge.resolve_model_binary(str(self.root / "nonexistent"))
        # Should fall back to generic or return no binary if empty
        self.assertIsInstance(res_nonexistent, dict)

        # Empty folder_path
        res_empty = self.bridge.resolve_model_binary("")
        self.assertIsInstance(res_empty, dict)

    def test_get_available_binaries_serializability(self):
        """Verifies get_available_binaries returns JSON-serializable output."""
        res = self.bridge.get_available_binaries()
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success", False) or "error" in res)
        # Verify all elements in 'binaries' are strings/primitives, not Path objects
        for b in res.get("binaries", []):
            self.assertIsInstance(b["dir_path"], str)
            self.assertIsInstance(b["exe_path"], str)


class TestPathResolutionAndAutoStress(unittest.TestCase):
    """Stress-tests dev_type='AUTO', case-insensitivity, and missing/invalid bin_root paths."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()

        # Add CUDA and Vulkan builds
        (self.bin_root / "llama-b9297-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"CUDA")
        (self.bin_root / "llama-b9297-bin-win-vulkan-x64").mkdir()
        (self.bin_root / "llama-b9297-bin-win-vulkan-x64" / "llama-server.exe").write_bytes(b"VULKAN")
        (self.bin_root / "llama-b9283-bin-win-cpu-x64").mkdir()
        (self.bin_root / "llama-b9283-bin-win-cpu-x64" / "llama-server.exe").write_bytes(b"CPU")

    def tearDown(self):
        self.tmp.cleanup()

    def test_auto_dev_type_selects_nvidia_if_present(self):
        """When dev_type='AUTO', hardware detection dictates preference."""
        has_nvidia, has_vulkan = hardware.detect_gpus()
        res = binaries.resolve_model_binary(None, self.bin_root, dev_type="AUTO")
        self.assertTrue(res["success"])
        if has_nvidia:
            self.assertEqual(res["binary_type"], "CUDA")
        elif has_vulkan:
            self.assertEqual(res["binary_type"], "VULKAN")
        else:
            self.assertEqual(res["binary_type"], "CPU")

    def test_dev_type_case_insensitivity_and_whitespace(self):
        """Verifies 'cuda', 'CuDa', '  cuda  ', '  VULKAN  ' resolve properly."""
        for dt in ["cuda", "CuDa", "  cuda  ", "  CUDA\n"]:
            res = binaries.resolve_model_binary(None, self.bin_root, dev_type=dt)
            self.assertEqual(res["binary_type"], "CUDA", f"Failed for dev_type='{dt}'")

        for dt in ["vulkan", "Vulkan", "  vulkan  "]:
            res = binaries.resolve_model_binary(None, self.bin_root, dev_type=dt)
            self.assertEqual(res["binary_type"], "VULKAN", f"Failed for dev_type='{dt}'")

    def test_bin_root_is_file_not_dir(self):
        """If bin_root points to a file instead of a directory, returns graceful failure."""
        fake_bin_root_file = self.root / "fake_bin_file.txt"
        fake_bin_root_file.write_text("not a directory")
        res = binaries.resolve_model_binary(None, fake_bin_root_file, dev_type="CUDA")
        self.assertFalse(res["success"])
        self.assertIn("No valid generic", res["error"])

    def test_bin_root_does_not_exist(self):
        """If bin_root path does not exist, returns graceful failure."""
        nonexistent = self.root / "does_not_exist"
        res = binaries.resolve_model_binary(None, nonexistent, dev_type="CUDA")
        self.assertFalse(res["success"])
        self.assertIn("No valid generic", res["error"])


class TestMalformedBuildsStress(unittest.TestCase):
    """Stress-tests build folders with malformed or unversioned names."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_unversioned_generic_names_preference_fallback(self):
        """
        When all generic folders have build_num=0 (no build numbers in names):
        e.g. 'llama-bin-win-cuda-x64', 'llama-bin-win-vulkan-x64', 'llama-bin-win-cpu-x64'
        Preferences (CUDA > VULKAN > CPU) must still be respected.
        """
        (self.bin_root / "llama-bin-win-cpu-x64").mkdir()
        (self.bin_root / "llama-bin-win-cpu-x64" / "llama-server.exe").write_bytes(b"CPU")

        (self.bin_root / "llama-bin-win-cuda-x64").mkdir()
        (self.bin_root / "llama-bin-win-cuda-x64" / "llama-server.exe").write_bytes(b"CUDA")

        (self.bin_root / "llama-bin-win-vulkan-x64").mkdir()
        (self.bin_root / "llama-bin-win-vulkan-x64" / "llama-server.exe").write_bytes(b"VULKAN")

        scanned = binaries.scan_generic_binaries(self.bin_root)
        self.assertEqual(len(scanned), 3)
        for s in scanned:
            self.assertEqual(s["build_num"], 0)
            self.assertEqual(s["build"], "unknown")

        res_cuda = binaries.resolve_model_binary(None, self.bin_root, dev_type="CUDA")
        self.assertEqual(res_cuda["binary_type"], "CUDA")

        res_vulkan = binaries.resolve_model_binary(None, self.bin_root, dev_type="VULKAN")
        self.assertEqual(res_vulkan["binary_type"], "VULKAN")

        res_cpu = binaries.resolve_model_binary(None, self.bin_root, dev_type="CPU")
        self.assertEqual(res_cpu["binary_type"], "CPU")


if __name__ == "__main__":
    unittest.main()
