from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Tuple
import json

CONFIG_DIR = Path.home() / ".sparx_pro"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    theme: str = "dark"
    color_theme: str = "blue"
    rounds: int = 25
    round_delay: float = 0.8
    repeat_delay: float = 0.25
    type_delay: float = 0.05
    ocr_confidence: float = 0.3
    region: Optional[Tuple[int, int, int, int]] = None
    macos_permissions_ack: bool = False

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                if data.get("region"):
                    data["region"] = tuple(data["region"])
                valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                return cls(**valid)
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        CONFIG_FILE.write_text(json.dumps(data, indent=2))
