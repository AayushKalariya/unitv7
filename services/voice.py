import os
import threading

import numpy as np
from pvrecorder import PvRecorder

_FRAME_LENGTH = 1280               # 80ms @ 16kHz, openWakeWord's expected chunk size
_WAKE_THRESHOLD = 0.5              # openWakeWord confidence score to trigger
_SILENCE_RMS_THRESHOLD = 150
_SILENCE_FRAMES_TO_STOP = 12       # ~1s of silence at 1280-sample/16kHz frames
_MAX_RECORD_FRAMES = 150           # ~12s safety cap
_MIN_SPEECH_FRAMES = 3             # ignore instant noise blips

_whisper_model = None
_whisper_lock = threading.Lock()


def preload_whisper_model():
    """Warm up the faster-whisper model ahead of first use, off the caller's thread."""
    _get_whisper_model()


def _get_whisper_model():
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            size = os.environ.get("WHISPER_MODEL_SIZE", "base")
            _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


def _rms(frame) -> float:
    arr = np.asarray(frame, dtype=np.int16)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))


def transcribe_frames(frames: list) -> str:
    if not frames:
        return ""
    pcm = np.concatenate([np.asarray(f, dtype=np.int16) for f in frames])
    audio = pcm.astype(np.float32) / 32768.0
    model = _get_whisper_model()
    segments, _ = model.transcribe(audio, language="en", vad_filter=True)
    return "".join(seg.text for seg in segments).strip()


class VoiceAssistant:
    """
    Background wake-word listener: IDLE (listening for wake word) ->
    RECORDING (until silence) -> TRANSCRIBING -> back to IDLE.
    Runs entirely on its own thread; all callbacks fire off that thread,
    so callers must marshal back to the UI thread themselves (e.g. Qt signals).
    """

    def __init__(self, on_wake=None, on_transcript=None, on_error=None):
        self._on_wake = on_wake
        self._on_transcript = on_transcript
        self._on_error = on_error
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()

    def _run(self):
        try:
            from openwakeword.model import Model as OWWModel
            # Bundled pretrained keyword — no account/key needed. Say "Hey Jarvis".
            # Swap to a custom-trained "Hey Orb" .onnx later via OPENWAKEWORD_MODEL_PATH.
            model_path = os.environ.get("OPENWAKEWORD_MODEL_PATH", "")
            wakeword_models = [model_path] if model_path else ["hey_jarvis"]
            oww = OWWModel(wakeword_models=wakeword_models, inference_framework="onnx")
            model_key = next(iter(oww.models.keys()))
        except Exception as e:
            if self._on_error:
                self._on_error(f"Wake-word init failed: {e}")
            return

        recorder = PvRecorder(frame_length=_FRAME_LENGTH, device_index=-1)
        recorder.start()

        try:
            while not self._stop_flag.is_set():
                pcm = recorder.read()
                scores = oww.predict(np.asarray(pcm, dtype=np.int16))
                if scores.get(model_key, 0.0) >= _WAKE_THRESHOLD:
                    oww.reset()
                    if self._on_wake:
                        self._on_wake()
                    text = self._record_and_transcribe(recorder)
                    if text and self._on_transcript:
                        self._on_transcript(text)
        except Exception as e:
            if self._on_error:
                self._on_error(str(e))
        finally:
            recorder.stop()
            recorder.delete()

    def _record_and_transcribe(self, recorder: PvRecorder) -> str:
        frames = []
        silent_run = 0
        for _ in range(_MAX_RECORD_FRAMES):
            if self._stop_flag.is_set():
                break
            pcm = recorder.read()
            frames.append(pcm)
            if _rms(pcm) < _SILENCE_RMS_THRESHOLD:
                silent_run += 1
            else:
                silent_run = 0
            if len(frames) > _MIN_SPEECH_FRAMES and silent_run >= _SILENCE_FRAMES_TO_STOP:
                break

        try:
            return transcribe_frames(frames)
        except Exception as e:
            if self._on_error:
                self._on_error(f"Transcription failed: {e}")
            return ""
