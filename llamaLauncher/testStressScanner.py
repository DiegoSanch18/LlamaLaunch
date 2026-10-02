#!/usr/bin/env python3
"""
Empirical Stress Testing Harness for LlamaLaunch Model Scanner and Binary Resolver
===================================================================================
Challenger M1-1 test suite executing adversarial boundary conditions:
- Deeply nested directory trees (4+ levels deep)
- Unicode, accents, non-Latin scripts (CJK, Cyrillic), emojis, and special symbols
- Malformed, temporary, and edge-case filenames (.gguf.tmp, .incomplete, .lock, 0-byte)
- Directory junctions, missing paths, and non-directory inputs
- High-integer build number sorting and backend fallback chains
- Schema contract verification
"""

import os
import sys
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import Dict, Any, List

# Locate project paths
CURRENT_FILE = Path(__file__).resolve()
SCRIPT_DIR = CURRENT_FILE.parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.backend import models, binaries


class TestDeepDirectoryNesting(unittest.TestCase):
    """Stress tests deep hierarchy scanning and dedicated binary resolution."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deep_nesting_four_levels(self):
        """Verifies scanner discovers models nested 4 levels deep."""
        deep_folder = self.root / "FamilyA" / "Sub1" / "Sub2" / "Sub3"
        deep_folder.mkdir(parents=True)
        (deep_folder / "model-Q4_K_M.gguf").write_bytes(b"GGUF_DATA")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertEqual(m["family"], "FamilyA")
        self.assertEqual(m["variant"], "Sub1 Sub2 Sub3")
        self.assertIn("FamilyA — Sub1 Sub2 Sub3", m["concatenated_label"])

    def test_deep_nesting_six_levels(self):
        """Verifies scanner discovers models nested 6 levels deep without crashing."""
        deep_folder = self.root / "UltraDeep" / "L1" / "L2" / "L3" / "L4" / "L5"
        deep_folder.mkdir(parents=True)
        (deep_folder / "model-Q8_0.gguf").write_bytes(b"GGUF_DATA")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertEqual(m["family"], "UltraDeep")
        self.assertEqual(m["variant"], "L1 L2 L3 L4 L5")

    def test_intermediate_dedicated_binary_divergence(self):
        """
        Adversarial test: checks if models.py and binaries.py agree on dedicated binary
        when placed at intermediate folder level (Qwen / Coder / llama.cpp).
        Demonstrates Bug 1 (divergence between models.py and binaries.py).
        """
        model_dir = self.root / "Qwen 2.5" / "Coder" / "14B"
        model_dir.mkdir(parents=True)
        (model_dir / "model-Q4_K_M.gguf").write_bytes(b"GGUF_DATA")

        inter_bin = self.root / "Qwen 2.5" / "Coder" / "llama.cpp"
        inter_bin.mkdir(parents=True)
        (inter_bin / "llama-server.exe").write_bytes(b"EXE")

        scan_res = models.scan_models_and_batches(self.root)
        m = scan_res["models"][0]

        bin_res = binaries.resolve_model_binary(model_dir, self.root / "bins", dev_type="CUDA")

        # Empirical observation: binaries.py detects intermediate parent dedicated binary,
        # but models.py._resolve_dedicated_binary only checks direct folder and family root.
        models_detected = m["has_dedicated_binary"]
        binaries_detected = bin_res["is_dedicated"]
        
        # We record the divergence assertion
        self.assertEqual(
            models_detected, binaries_detected,
            f"Divergence detected! models.py says dedicated={models_detected}, but binaries.py says dedicated={binaries_detected}"
        )

    def test_family_root_dedicated_binary_at_four_levels_divergence(self):
        """
        Adversarial test: checks if binaries.py finds family root binary when model is 4 levels deep.
        Demonstrates Bug 1 inverse (binaries.py range(2) stops before family root).
        """
        model_dir = self.root / "DeepFamily" / "L1" / "L2" / "L3"
        model_dir.mkdir(parents=True)
        (model_dir / "model-Q4_K_M.gguf").write_bytes(b"GGUF_DATA")

        fam_bin = self.root / "DeepFamily" / "llama.cpp"
        fam_bin.mkdir(parents=True)
        (fam_bin / "llama-server.exe").write_bytes(b"EXE")

        scan_res = models.scan_models_and_batches(self.root)
        m = scan_res["models"][0]

        bin_res = binaries.resolve_model_binary(model_dir, self.root / "bins", dev_type="CUDA")

        models_detected = m["has_dedicated_binary"]
        binaries_detected = bin_res["is_dedicated"]

        self.assertEqual(
            models_detected, binaries_detected,
            f"Divergence detected at 4-levels! models.py says dedicated={models_detected}, but binaries.py says dedicated={binaries_detected}"
        )


class TestUnicodeAndSpecialCharacters(unittest.TestCase):
    """Stress tests internationalization, unicode, emojis, and punctuation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_spanish_accents_and_tildes(self):
        """Verifies directories with accents and ñ are scanned without crashes."""
        f = self.root / "Modelos Españoles" / "Versión Ñandú"
        f.mkdir(parents=True)
        (f / "ñandú-7b-Q4_K_M.gguf").write_bytes(b"GGUF")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertEqual(m["family"], "Modelos Españoles")
        self.assertEqual(m["variant"], "Versión Ñandú")
        self.assertTrue(len(m["id"]) > 0)

    def test_emoji_and_symbols_in_paths(self):
        """Verifies directories with emojis and symbols are scanned."""
        f = self.root / "🦙 Llama Family 🚀" / "⚡ Fast Variant 🌟"
        f.mkdir(parents=True)
        (f / "model-Q4_K_M.gguf").write_bytes(b"GGUF")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertIn("🦙 Llama Family 🚀", m["family"])
        self.assertTrue(len(m["id"]) > 0)

    def test_cjk_pure_non_ascii_empty_slug_bug(self):
        """
        Adversarial test: checks if single-level Chinese/CJK model folder generates a non-empty slug id.
        Demonstrates Bug 3 (re.sub strips all non-ASCII chars leaving id='').
        """
        f = self.root / "通义千问"
        f.mkdir(parents=True)
        (f / "qwen-7b-Q4_K_M.gguf").write_bytes(b"GGUF")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertNotEqual(
            m["id"], "",
            f"Bug 3 reproduced: Pure non-ASCII model '{m['family']}' produced empty string slug ID: {repr(m['id'])}"
        )

    def test_punctuation_and_special_symbols(self):
        """Verifies special punctuation in path names (dots, parentheses, brackets, plus)."""
        f = self.root / "Model (v1.0) [Final]" / "Sub+Variant & Test"
        f.mkdir(parents=True)
        (f / "model-Q4_0.gguf").write_bytes(b"GGUF")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertTrue(len(m["id"]) > 0)


class TestMalformedAndBoundaryFiles(unittest.TestCase):
    """Stress tests malformed, temporary, and boundary condition files."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_temporary_and_lock_files_exclusion(self):
        """Verifies temporary and lock files are not classified as valid weights."""
        f = self.root / "FamilyA" / "1B"
        f.mkdir(parents=True)
        (f / "weight.gguf.tmp").write_bytes(b"TMP")
        (f / "weight.gguf.incomplete").write_bytes(b"INC")
        (f / "weight.gguf.lock").write_bytes(b"LOCK")
        (f / "real-model-Q4_0.gguf").write_bytes(b"REAL")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        m = res["models"][0]
        filenames = [w["filename"] for w in m["weights"]]
        self.assertEqual(filenames, ["real-model-Q4_0.gguf"])

    def test_zero_byte_weight_file(self):
        """Verifies 0-byte weight file is handled safely without division by zero."""
        f = self.root / "ZeroFamily" / "1B"
        f.mkdir(parents=True)
        (f / "zero-Q4_0.gguf").write_bytes(b"")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        m = res["models"][0]
        self.assertEqual(m["weights"][0]["size_bytes"], 0)
        self.assertEqual(m["weights"][0]["size_gb"], 0.0)

    def test_uppercase_gguf_extension(self):
        """Verifies files with uppercase .GGUF extension are discovered on Windows."""
        f = self.root / "UpperFamily" / "1B"
        f.mkdir(parents=True)
        (f / "model-Q4_0.GGUF").write_bytes(b"UPPER")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 1)
        m = res["models"][0]
        self.assertEqual(len(m["weights"]), 1)

    def test_projector_without_extension_ignored(self):
        """Verifies mmproj file without extension is ignored and not treated as model weight."""
        f = self.root / "ProjectorFamily" / "1B"
        f.mkdir(parents=True)
        (f / "mmproj-vision").write_bytes(b"NO_EXT")
        (f / "model-Q4_0.gguf").write_bytes(b"WEIGHT")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        m = res["models"][0]
        self.assertEqual(len(m["mmproj"]), 0)


class TestInvalidPathsAndJunctions(unittest.TestCase):
    """Stress tests boundary paths, non-directory inputs, and directory junctions."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_nonexistent_models_dir(self):
        """Verifies non-existent directory returns success=False without crashing."""
        fake_path = self.root / "non_existent_path_98765"
        res = models.scan_models_and_batches(fake_path)
        self.assertFalse(res["success"])
        self.assertIn("error", res)
        self.assertEqual(res["total_models"], 0)

    def test_file_passed_as_models_dir_crash_bug(self):
        """
        Adversarial test: checks if passing an existing file path as models_dir crashes.
        Demonstrates Bug 2 (NotADirectoryError when iterating models_root.iterdir()).
        """
        fake_file = self.root / "some_file.txt"
        fake_file.write_text("Hello", encoding="utf-8")

        try:
            res = models.scan_models_and_batches(fake_file)
            self.assertFalse(
                res["success"],
                "Expected scan_models_and_batches to return success=False when given a file."
            )
        except NotADirectoryError as e:
            self.fail(f"Bug 2 reproduced: scan_models_and_batches crashed with NotADirectoryError: {e}")

    def test_directory_junction_traversal(self):
        """Verifies valid NTFS directory junction is traversed and models discovered."""
        real_family = self.root / "TargetFamily" / "12B"
        real_family.mkdir(parents=True)
        (real_family / "model-Q4_K_M.gguf").write_bytes(b"GGUF")

        junction_family = self.root / "JunctionFamily"
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction_family), str(self.root / "TargetFamily")],
            capture_output=True
        )

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 2)

    def test_broken_directory_junction_handled_safely(self):
        """Verifies broken directory junction does not raise exception."""
        to_delete = self.root / "TempFamily"
        to_delete.mkdir(parents=True)
        (to_delete / "model.gguf").write_bytes(b"GGUF")

        broken_junc = self.root / "BrokenJunction"
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(broken_junc), str(to_delete)],
            capture_output=True
        )
        shutil.rmtree(to_delete)

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["models"]), 0)


class TestBinaryResolverPrioritiesAndSorting(unittest.TestCase):
    """Stress tests integer build number sorting and backend fallback preferences."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bin_root = self.root / "bin_root"
        self.bin_root.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_integer_build_sorting_large_numbers(self):
        """Verifies b10000 sorts before b9297 (integer vs lexicographic sort)."""
        for b_tag in ["b9283", "b9297", "b10000", "b9500"]:
            d = self.bin_root / f"llama-{b_tag}-bin-win-cuda-x64"
            d.mkdir()
            (d / "llama-server.exe").write_bytes(b"EXE")

        scanned = binaries.scan_generic_binaries(self.bin_root)
        build_nums = [b["build_num"] for b in scanned]
        self.assertEqual(build_nums, [10000, 9500, 9297, 9283])

    def test_unusual_dev_type_strings(self):
        """Verifies exotic dev_type strings (None, empty, whitespace, unknown) fall back safely."""
        d = self.bin_root / "llama-b9297-bin-win-cpu-x64"
        d.mkdir()
        (d / "llama-server.exe").write_bytes(b"EXE")

        for dt in [None, "", "   ", "UNKNOWN", "ROCM", "METAL"]:
            res = binaries.resolve_model_binary(self.root / "m", self.bin_root, dev_type=dt)
            self.assertTrue(res["success"])
            self.assertEqual(res["binary_type"], "CPU")

    def test_force_generic_bypasses_dedicated_binary(self):
        """Verifies force_generic=True ignores dedicated binary."""
        model_dir = self.root / "DedicatedModel"
        (model_dir / "llama.cpp").mkdir(parents=True)
        (model_dir / "llama.cpp" / "llama-server.exe").write_bytes(b"DEDICATED")

        bin_dir = self.bin_root / "llama-b9297-bin-win-cpu-x64"
        bin_dir.mkdir(parents=True)
        (bin_dir / "llama-server.exe").write_bytes(b"GENERIC")

        res_dedicated = binaries.resolve_model_binary(model_dir, self.bin_root, force_generic=False)
        self.assertTrue(res_dedicated["is_dedicated"])
        self.assertEqual(res_dedicated["binary_type"], "CUSTOM_DEDICATED")

        res_generic = binaries.resolve_model_binary(model_dir, self.bin_root, force_generic=True)
        self.assertFalse(res_generic["is_dedicated"])
        self.assertEqual(res_generic["binary_type"], "CPU")


class TestSchemaContractIntegrity(unittest.TestCase):
    """Stress tests strict adherence to the schema dictionary contracts."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scanner_and_binary_schema_contracts(self):
        """Validates all required keys and types are present in returned dictionaries."""
        m_dir = self.root / "Gemma 4" / "12B"
        m_dir.mkdir(parents=True)
        (m_dir / "model-Q4_K_M.gguf").write_bytes(b"GGUF")
        (m_dir / "mmproj-BF16.gguf").write_bytes(b"MMPROJ")
        (m_dir / "mtp-draft.gguf").write_bytes(b"MTP")
        (m_dir / "run.bat").write_text("@echo off\n", encoding="utf-8")
        (m_dir / "run.bat.bak").write_text("@echo off bak\n", encoding="utf-8")

        res = models.scan_models_and_batches(self.root)
        self.assertTrue(res["success"])
        self.assertIsInstance(res["models"], list)
        self.assertIsInstance(res["pending_models"], list)

        model = res["models"][0]
        required_model_keys = {
            "id", "family", "variant", "concatenated_label", "display_name",
            "folder_path", "has_dedicated_binary", "dedicated_binary_path",
            "dedicated_binary_dir", "weights", "mmproj", "mtp", "batch_scripts",
            "default_batch", "last_used"
        }
        self.assertTrue(required_model_keys.issubset(model.keys()))

        weight = model["weights"][0]
        required_weight_keys = {"filename", "path", "size_gb", "size_bytes", "modified_time", "type", "quantization"}
        self.assertTrue(required_weight_keys.issubset(weight.keys()))

        batch = model["batch_scripts"][0]
        required_batch_keys = {"filename", "path", "has_backup", "last_modified"}
        self.assertTrue(required_batch_keys.issubset(batch.keys()))

        bin_res = binaries.resolve_model_binary(m_dir, self.root / "bins", dev_type="CPU")
        required_bin_keys = {"success", "binary_path", "binary_dir", "binary_type", "is_dedicated", "build", "name", "cuda_dlls_verified", "error"}
        self.assertTrue(required_bin_keys.issubset(bin_res.keys()))


if __name__ == "__main__":
    unittest.main()
