import subprocess
from pathlib import Path

import pytest

from autocut import ffmpeg

# 1.2s of 440Hz tone every 3s, 12s total -> four tone bursts separated by 1.8s of silence
_BURSTS = "aevalsrc='if(lt(mod(t,3),1.2),0.5*sin(2*PI*440*t),0)':s=44100:d=12"
SCRIPT = "The city traffic never stops at night. Then we drive to the ocean and watch the waves. Finally the forest trees are quiet."


def _ff(*args: str) -> None:
    subprocess.run([ffmpeg.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory) -> dict:
    d = tmp_path_factory.mktemp("fixtures")
    assets = d / "assets"
    assets.mkdir()
    _ff("-f", "lavfi", "-i", _BURSTS, str(d / "voice.wav"))
    _ff(
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:d=12", "-f", "lavfi", "-i", _BURSTS,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "cam.mp4"),
    )
    _ff("-f", "lavfi", "-i", "color=c=red:s=320x180:r=30:d=3", "-pix_fmt", "yuv420p", str(assets / "city_traffic_night.mp4"))
    _ff("-f", "lavfi", "-i", "color=c=blue:s=180x320:r=30:d=6", "-pix_fmt", "yuv420p", str(assets / "ocean_waves.mp4"))
    _ff("-f", "lavfi", "-i", "color=c=green:s=400x300:d=1", "-frames:v", "1", str(assets / "forest_trees.png"))
    _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=4", str(d / "music.wav"))
    (d / "script.txt").write_text(SCRIPT)
    return {"dir": d, "voice": d / "voice.wav", "cam": d / "cam.mp4", "assets": assets, "script": d / "script.txt", "music": d / "music.wav"}
