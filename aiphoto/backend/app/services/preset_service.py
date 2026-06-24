import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict

# All 12 parameter keys
PARAM_KEYS = [
    "brightness", "contrast", "saturation", "temperature",
    "sharpness", "highlights", "shadows", "vignette",
    "grain", "tint", "fade", "hue_shift",
]


class PresetService:
    """Simple JSON-file based preset store for user custom styles."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self._file = os.path.join(data_dir, "custom_presets.json")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._file):
            self._write([])

    def _read(self) -> list:
        with open(self._file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: list):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list(self) -> List[dict]:
        return self._read()

    def get(self, preset_id: str) -> Optional[dict]:
        presets = self._read()
        for p in presets:
            if p["id"] == preset_id:
                return p
        return None

    def create(self, name: str, **params) -> dict:
        presets = self._read()
        preset = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        for k in PARAM_KEYS:
            val = float(params.get(k, 0.0))
            preset[k] = val
        presets.append(preset)
        self._write(presets)
        return preset

    def update(self, preset_id: str, **kwargs) -> Optional[dict]:
        presets = self._read()
        for p in presets:
            if p["id"] == preset_id:
                if "name" in kwargs and kwargs["name"] is not None:
                    p["name"] = kwargs["name"]
                for k in PARAM_KEYS:
                    if k in kwargs and kwargs[k] is not None:
                        p[k] = float(kwargs[k])
                self._write(presets)
                return p
        return None

    def delete(self, preset_id: str) -> bool:
        presets = self._read()
        new_list = [p for p in presets if p["id"] != preset_id]
        if len(new_list) == len(presets):
            return False
        self._write(new_list)
        return True
