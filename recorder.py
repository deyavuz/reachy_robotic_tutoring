"""Session audio recording.

Records continuously in a background thread, writing incrementally to disk
so that a crash mid-session still leaves a playable file.

IMPORTANT: use a different input device from the one the Reachy conversation
app is using. Two processes competing for the same mic fails quietly and you
won't find out until you check the file. Run this module directly to list
devices and pick an index:

    python recorder.py
"""

import os
import queue
import threading
from datetime import datetime

import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 44100
CHANNELS = 1
DEVICE = None          # None = system default. Set to an index from list_devices().

RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")


class SessionRecorder:
    def __init__(self, participant_id, device=DEVICE):
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(RECORDINGS_DIR, f"{participant_id}_{stamp}.wav")
        self.device = device
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self.started_at = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[recorder] {status}")
        self._q.put(indata.copy())

    def _writer(self):
        with sf.SoundFile(self.path, mode="w", samplerate=SAMPLE_RATE,
                          channels=CHANNELS, subtype="PCM_16") as f:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                                device=self.device, callback=self._callback):
                while not self._stop.is_set():
                    try:
                        f.write(self._q.get(timeout=0.5))
                    except queue.Empty:
                        continue
                # drain whatever is left
                while not self._q.empty():
                    f.write(self._q.get())

    def start(self):
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()
        print(f"[recorder] recording to {self.path}")
        return self.path

    def stop(self):
        if self._thread is None:
            return None
        self._stop.set()
        self._thread.join(timeout=5)
        print(f"[recorder] saved {self.path}")
        return self.path


def list_devices():
    print(sd.query_devices())
    print("\nDefault input:", sd.default.device[0])


if __name__ == "__main__":
    list_devices()