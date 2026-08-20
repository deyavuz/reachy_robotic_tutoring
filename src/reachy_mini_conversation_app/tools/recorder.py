"""Session audio recording, with graceful degradation.

Tries sounddevice first, falls back to ffmpeg, and if neither is available
logs a clear warning and lets the session continue. Recording failing should
never stop a participant session — use a phone as backup.

Run this file directly to see which backend is available and list devices:

    python recorder.py
"""

import os
import queue
import shutil
import subprocess
import threading
from datetime import datetime

DEVICE = 0
SAMPLE_RATE = 44100
CHANNELS = 1

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(HERE, "recordings")

try:
    import sounddevice as sd
    import soundfile as sf
    BACKEND = "sounddevice"
except Exception:
    BACKEND = "ffmpeg" if shutil.which("ffmpeg") else None


class SessionRecorder:
    """Records continuously, writing incrementally so a crash still leaves a file."""

    def __init__(self, participant_id, device=DEVICE):
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(RECORDINGS_DIR, f"{participant_id}_{stamp}.wav")
        self.device = device
        self.started_at = None
        self.backend = BACKEND
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self._proc = None

    # -- sounddevice ------------------------------------------------------

    def _cb(self, indata, frames, time_info, status):
        if status:
            print(f"[recorder] {status}")
        self._q.put(indata.copy())

    def _writer(self):
        with sf.SoundFile(self.path, mode="w", samplerate=SAMPLE_RATE,
                          channels=CHANNELS, subtype="PCM_16") as f:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                                device=self.device, callback=self._cb):
                while not self._stop.is_set():
                    try:
                        f.write(self._q.get(timeout=0.5))
                    except queue.Empty:
                        continue
                while not self._q.empty():
                    f.write(self._q.get())

    # -- public -----------------------------------------------------------

    def start(self):
        self.started_at = datetime.now().isoformat(timespec="seconds")

        if self.backend == "sounddevice":
            self._thread = threading.Thread(target=self._writer, daemon=True)
            self._thread.start()

        elif self.backend == "ffmpeg":
            dev = f":{self.device}" if self.device is not None else ":default"
            self._proc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-f", "avfoundation",
                 "-i", dev, "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
                 "-y", self.path],
                stdin=subprocess.PIPE,
            )
        else:
            print("[recorder] NO AUDIO BACKEND — session will not be recorded. "
                  "Use a phone as backup.")
            return None

        print(f"[recorder] recording via {self.backend} to {self.path}")
        return self.path

    def stop(self):
        if self.backend == "sounddevice" and self._thread:
            self._stop.set()
            self._thread.join(timeout=5)
        elif self.backend == "ffmpeg" and self._proc:
            try:
                self._proc.communicate(input=b"q", timeout=5)
            except Exception:
                self._proc.terminate()
        else:
            return None

        size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        print(f"[recorder] saved {self.path} ({size/1_048_576:.1f} MB)")
        if size < 10_000:
            print("[recorder] WARNING: file is suspiciously small — check the mic.")
        return self.path


def status():
    print(f"backend: {BACKEND or 'NONE — install sounddevice+soundfile, or ffmpeg'}")
    if BACKEND == "sounddevice":
        print(sd.query_devices())
        print("\ndefault input index:", sd.default.device[0])
        print("\nSet DEVICE at the top of this file to an index that is NOT the "
              "robot's microphone.")
    elif BACKEND == "ffmpeg":
        print("\nListing avfoundation devices:")
        subprocess.run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true",
                        "-i", ""], stderr=subprocess.STDOUT)


if __name__ == "__main__":
    status()