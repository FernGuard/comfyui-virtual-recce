from __future__ import annotations

import ast
import importlib.util
import json
import re
import struct
import sys
import traceback
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"
EXAMPLE_DIR = ROOT / "examples"
WORKFLOW_NAME = "virtual_recce_story.json"
EXPECTED_IMAGES = {
    "ref_env_scifi_lab.png",
    "ref_char_hero.png",
    "ref_char_woman.png",
}
EXPECTED_RECCE_NODES = {
    "VRGoogleMapsKey",
    "VRShootTime",
    "VRLocationPicker",
    "VRSetAndCast",
    "VRGeocodeAddress",
    "VRStreetViewReference",
    "VRSunPosition",
    "VRLocationWeather",
    "VRReccePromptBuilder",
}
EXPECTED_WORKFLOW_RECCE_NODES = EXPECTED_RECCE_NODES - {"VRGeocodeAddress"}
EXPECTED_BUILT_INS = {"LoadImage", "SaveImage", "GeminiNodeV2", "GeminiImage2Node"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".mjs", ".txt", ".yml", ".yaml"}


def load_workflow() -> dict:
    return json.loads((WORKFLOW_DIR / WORKFLOW_NAME).read_text(encoding="utf-8"))


def mapping_keys() -> set[str]:
    tree = ast.parse((ROOT / "nodes.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS" for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            break
        return {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    raise AssertionError("NODE_CLASS_MAPPINGS was not found")


def png_chunks(path: Path) -> list[bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"{path.name} is not a PNG")
    chunks: list[bytes] = []
    offset = 8
    while offset < len(data):
        if offset + 12 > len(data):
            raise AssertionError(f"{path.name} has a truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunks.append(kind)
        offset += 12 + length
        if kind == b"IEND":
            break
    return chunks


def load_nodes_for_tests():
    module_name = "_virtual_recce_test_nodes"
    if module_name in sys.modules:
        return sys.modules[module_name]

    numpy_stub = types.ModuleType("numpy")
    setattr(numpy_stub, "float32", float)
    setattr(numpy_stub, "asarray", lambda *args, **kwargs: None)
    setattr(numpy_stub, "zeros", lambda *args, **kwargs: None)

    torch_stub = types.ModuleType("torch")
    setattr(torch_stub, "Tensor", type("Tensor", (), {}))
    setattr(torch_stub, "from_numpy", lambda *args, **kwargs: None)
    setattr(torch_stub, "cat", lambda *args, **kwargs: None)

    pillow_stub = types.ModuleType("PIL")
    image_stub = types.ModuleType("PIL.Image")
    setattr(image_stub, "Image", type("Image", (), {}))
    setattr(pillow_stub, "Image", image_stub)

    sys.modules.setdefault("numpy", numpy_stub)
    sys.modules.setdefault("torch", torch_stub)
    sys.modules.setdefault("PIL", pillow_stub)
    sys.modules.setdefault("PIL.Image", image_stub)

    spec = importlib.util.spec_from_file_location(module_name, ROOT / "nodes.py")
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load nodes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.nodes = load_nodes_for_tests()

    def test_request_failure_does_not_reveal_key(self) -> None:
        secret = "TEST_MAPS_KEY_MUST_NOT_APPEAR"

        class FailingRequests:
            @staticmethod
            def get(url, params, timeout):
                raise RuntimeError(f"failed URL: {url}?key={secret}")

        with self.assertRaises(RuntimeError) as caught:
            self.nodes._safe_get(
                FailingRequests,
                "https://maps.example.invalid/request",
                {"key": secret},
                1,
                "Maps test",
            )

        rendered = "".join(
            traceback.format_exception(
                type(caught.exception),
                caught.exception,
                caught.exception.__traceback__,
            )
        )
        self.assertNotIn(secret, rendered)
        self.assertNotIn("maps.example.invalid", rendered)
        self.assertIn("Maps test: request failed", rendered)

    def test_blank_shoot_time_resolves_to_explicit_values(self) -> None:
        date, time = self.nodes.VRShootTime().provide("", "")
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(time, r"^\d{2}:\d{2}$")
        self.assertEqual(
            self.nodes.VRShootTime().provide(" 2030-01-02 ", " 09:45 "),
            ("2030-01-02", "09:45"),
        )

    def test_weather_failure_does_not_include_exception_text(self) -> None:
        class ExplodingRequests:
            @staticmethod
            def get(url, params, timeout):
                raise RuntimeError("secret weather detail")

        original_require = self.nodes._require

        def fake_require(mod_name, pip_name=None):
            if mod_name == "requests":
                return ExplodingRequests
            return original_require(mod_name, pip_name)

        setattr(self.nodes, "_require", fake_require)
        try:
            description, cloud = self.nodes.VRLocationWeather().fetch(34.1, -118.3, "2026-09-05", "17:30")
        finally:
            setattr(self.nodes, "_require", original_require)

        self.assertEqual(description, "weather unavailable.")
        self.assertEqual(cloud, 0.0)
        self.assertNotIn("secret weather detail", description)


class RepositoryStructureTests(unittest.TestCase):
    def test_exactly_one_comfyui_workflow(self) -> None:
        names = {path.name for path in WORKFLOW_DIR.glob("*.json")}
        self.assertEqual(names, {WORKFLOW_NAME})

    def test_exactly_three_required_images(self) -> None:
        names = {path.name for path in EXAMPLE_DIR.glob("*.png")}
        self.assertEqual(names, EXPECTED_IMAGES)

    def test_all_nine_recce_nodes_remain_registered(self) -> None:
        self.assertEqual(mapping_keys(), EXPECTED_RECCE_NODES)

    def test_required_documentation_exists(self) -> None:
        self.assertTrue((ROOT / "WORKFLOW_GUIDE.md").is_file())
        self.assertTrue((ROOT / "THIRD_PARTY_NOTICES.md").is_file())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)", readme)
        self.assertIn("[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)", readme)

    def test_globe_dependencies_are_vendored(self) -> None:
        vendor = ROOT / "web" / "vendor"
        expected = {
            "globe.gl-2.46.2.bundle.mjs",
            "earth-blue-marble.jpg",
            "earth-topology.png",
        }
        self.assertEqual({path.name for path in vendor.iterdir() if path.is_file()}, expected)
        frontend = (ROOT / "web" / "vr_location_globe.js").read_text(encoding="utf-8")
        self.assertIn('new URL("./vendor/", import.meta.url)', frontend)
        self.assertNotIn("https://esm.sh", frontend)
        self.assertNotIn("https://unpkg.com", frontend)


class WorkflowIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_workflow()
        cls.nodes = cls.workflow["nodes"]
        cls.by_id = {node["id"]: node for node in cls.nodes}

    def test_node_ids_are_unique_and_last_id_is_correct(self) -> None:
        self.assertEqual(len(self.by_id), len(self.nodes))
        self.assertEqual(self.workflow["last_node_id"], max(self.by_id))

    def test_all_links_reference_valid_nodes_and_slots(self) -> None:
        link_ids: list[int] = []
        for link_id, source_id, source_slot, target_id, target_slot, _type in self.workflow["links"]:
            link_ids.append(link_id)
            self.assertIn(source_id, self.by_id)
            self.assertIn(target_id, self.by_id)
            self.assertLess(source_slot, len(self.by_id[source_id].get("outputs", [])))
            self.assertLess(target_slot, len(self.by_id[target_id].get("inputs", [])))
        self.assertEqual(len(link_ids), len(set(link_ids)))
        self.assertEqual(self.workflow["last_link_id"], max(link_ids))

    def test_workflow_uses_expected_node_types(self) -> None:
        types = {node["type"] for node in self.nodes}
        recce = {name for name in types if name.startswith("VR")}
        built_ins = types - recce
        self.assertEqual(recce, EXPECTED_WORKFLOW_RECCE_NODES)
        self.assertEqual(built_ins, EXPECTED_BUILT_INS)
        self.assertTrue(recce <= mapping_keys())

    def test_maps_key_widget_is_blank(self) -> None:
        key_nodes = [node for node in self.nodes if node["type"] == "VRGoogleMapsKey"]
        self.assertEqual(len(key_nodes), 1)
        self.assertEqual(key_nodes[0].get("widgets_values"), [""])

    def test_workflow_references_exactly_the_bundled_images(self) -> None:
        names = {
            node["widgets_values"][0]
            for node in self.nodes
            if node["type"] == "LoadImage"
        }
        self.assertEqual(names, EXPECTED_IMAGES)
        for name in names:
            self.assertTrue((EXAMPLE_DIR / name).is_file())

    def test_saved_model_and_output_settings(self) -> None:
        gemini_text = next(node for node in self.nodes if node["type"] == "GeminiNodeV2")
        gemini_image = next(node for node in self.nodes if node["type"] == "GeminiImage2Node")
        save = next(node for node in self.nodes if node["type"] == "SaveImage")
        self.assertEqual(gemini_text["widgets_values"][1], "Gemini 3.1 Pro")
        self.assertEqual(gemini_text["widgets_values"][2], "HIGH")
        self.assertEqual(gemini_text["widgets_values"][5], 32768)
        self.assertEqual(gemini_image["widgets_values"][1], "gemini-3-pro-image-preview")
        self.assertEqual(gemini_image["widgets_values"][4:7], ["16:9", "2K", "IMAGE"])
        self.assertEqual(save["widgets_values"], ["VirtualRecce_story"])


class PrivacyAndAssetTests(unittest.TestCase):
    def test_pngs_have_no_text_or_workflow_metadata(self) -> None:
        forbidden_chunks = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
        for path in sorted(EXAMPLE_DIR.glob("*.png")):
            self.assertTrue(forbidden_chunks.isdisjoint(png_chunks(path)), path.name)

    def test_no_personal_absolute_paths_or_email_addresses(self) -> None:
        mac_home = "/" + "Users" + "/"
        windows_home = "C:" + "\\" + "Users" + "\\"
        private_folder = "Job" + "Search"
        email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".gitignore":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn(mac_home, text, str(path.relative_to(ROOT)))
            self.assertNotIn(windows_home, text, str(path.relative_to(ROOT)))
            self.assertNotIn(private_folder, text, str(path.relative_to(ROOT)))
            self.assertIsNone(email.search(text), str(path.relative_to(ROOT)))

    def test_no_google_key_shaped_value(self) -> None:
        key_pattern = re.compile(r"AIza[0-9A-Za-z_-]{30,}")
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(key_pattern.search(text), str(path.relative_to(ROOT)))


if __name__ == "__main__":
    unittest.main()
