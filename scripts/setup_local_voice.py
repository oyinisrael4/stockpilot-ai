import hashlib
from pathlib import Path

from faster_whisper.utils import download_model

root = Path(__file__).resolve().parents[1]
destination = root / ".local" / "whisper-tiny.en"
revision = "0d3d19a32d3338f10357c0889762bd8d64bbdeba"
model_sha256 = "1a5afae06a4db91c975c9a9d78be5cc110ee4ea022ad57d55492e4550e936b2a"

if not all((destination / name).is_file() for name in ("config.json", "tokenizer.json", "model.bin", "vocabulary.txt")):
    download_model("tiny.en", output_dir=str(destination), revision=revision)
with (destination / "model.bin").open("rb") as model:
    if hashlib.file_digest(model, "sha256").hexdigest() != model_sha256:
        raise SystemExit("Model checksum did not match. Remove the incomplete model folder and retry setup.")
print("Offline speech model verified.")
