#!/usr/bin/env python3
"""
Production-Grade Audio Recorder using MixMonitor
Industry standard for VoIP call recording - designed for production reliability
"""

import os
import time
import uuid
import logging
import threading
from dataclasses import dataclass
import subprocess

logger = logging.getLogger(__name__)

class ProductionCallRecorder:
    """Production-grade call recorder using MixMonitor (industry standard)"""

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client

    # --- End-of-speech tuning knobs ---
    _EOS_IDLE_MS = 800       # no growth for this long => end-of-speech
    _EOS_POLL_MS = 120       # polling interval
    _MIN_SPEECH_BYTES = 4096 # ignore tiny blips/breaths but catch short replies

    def _prepare_asr_input(self, src_wav: str) -> str:
        """Convert RX WAV to 16kHz mono PCM WAV for Whisper if needed.
        Returns path to converted file (may be source if conversion fails)."""
        try:
            if not os.path.exists(src_wav):
                return src_wav
            dst = f"/tmp/asr_{uuid.uuid4().hex[:8]}.wav"
            cmd = [
                'sox', src_wav,
                '-r', '16000',
                '-c', '1',
                '-b', '16',
                '-e', 'signed-integer',
                dst
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if os.path.exists(dst) and os.path.getsize(dst) > 1000:
                return dst
        except Exception:
            pass
        return src_wav

    @staticmethod
    def _file_size(path: str) -> int:
        try:
            return os.path.getsize(path)
        except Exception:
            return 0

    def _wait_for_end_of_speech(self, recording_path: str,
                                min_bytes: int = None,
                                idle_ms: int = None,
                                poll_ms: int = None,
                                deadline_ts: float = None) -> bool:
        """Blocks until the recording file stops growing for idle_ms and
        has at least min_bytes (avoids stopping on breaths).
        Returns True if EOS observed before deadline; False if deadline exceeded.
        """
        if min_bytes is None:
            min_bytes = self._MIN_SPEECH_BYTES
        if idle_ms is None:
            idle_ms = self._EOS_IDLE_MS
        if poll_ms is None:
            poll_ms = self._EOS_POLL_MS

        last = self._file_size(recording_path)
        start_t = time.time()
        saw_voice = False

        # Ensure we at least see some voice
        while self._file_size(recording_path) < min_bytes and self.agi.connected:
            if deadline_ts is not None and time.time() >= deadline_ts:
                return False
            time.sleep(poll_ms / 1000.0)
            if time.time() - start_t > 30:
                break
        # Check if we reached the required minimum bytes (voice seen)
        if self._file_size(recording_path) >= min_bytes:
            saw_voice = True

        # If we never saw voice, do not declare EOS; wait for timeout at caller
        if not saw_voice:
            return False

        # Now wait for growth to stall
        stable_for_ms = 0
        while self.agi.connected:
            if deadline_ts is not None and time.time() >= deadline_ts:
                return False
            time.sleep(poll_ms / 1000.0)
            cur = self._file_size(recording_path)
            if cur > last:
                last = cur
                stable_for_ms = 0
            else:
                stable_for_ms += poll_ms
                if stable_for_ms >= idle_ms:
                    return True

    def get_user_input_with_mixmonitor(self, timeout=10):
        """
        Production-grade user input recording using MixMonitor
        Records actual call audio stream (RTP) - not hardware devices
        """
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/mix_{unique_id}"
        wav_file = f"{record_file}.wav"              # mixed (both directions)
        rx_wav_file = f"{record_file}_rx.wav"        # inbound (caller -> bot)

        logger.info(f"Starting MixMonitor recording: {record_file}")

        try:
            # Start MixMonitor: also record receive-only stream to a separate file
            # Using r(file) per Asterisk docs so we can monitor caller-only audio
            mm_var = f"MMID_{unique_id}"
            mixmonitor_cmd = f'EXEC MixMonitor {record_file}.wav,r({record_file}_rx.wav),i({mm_var})'
            result = self.agi.command(mixmonitor_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start MixMonitor: {result}")
                return None

            logger.info(f"MixMonitor started, waiting up to {timeout}s for end-of-speech...")

            # Wait for EOS or timeout
            deadline = time.time() + float(timeout)
            # Wait on RX-only file to avoid bot TTS growth
            self._wait_for_end_of_speech(rx_wav_file, deadline_ts=deadline)

            # Stop MixMonitor
            stop_result = self.agi.command(f'EXEC StopMixMonitor ${{{mm_var}}}')
            logger.info(f"MixMonitor stopped: {stop_result}")

            # Small delay to ensure file is written
            time.sleep(0.2)

            # Check final recording (prefer RX-only)
            target_final = rx_wav_file if os.path.exists(rx_wav_file) else wav_file
            if os.path.exists(target_final):
                file_size = os.path.getsize(target_final)
                logger.info(f"Final recording: {file_size} bytes")

                if file_size >= self._MIN_SPEECH_BYTES:
                    # Transcribe with ASR
                    asr_input = self._prepare_asr_input(target_final)
                    transcript = self.asr.transcribe_file(asr_input)
                    try:
                        if asr_input != target_final and os.path.exists(asr_input):
                            os.unlink(asr_input)
                    except Exception:
                        pass

                    # Cleanup
                    try:
                        os.unlink(wav_file)
                        if os.path.exists(rx_wav_file):
                            os.unlink(rx_wav_file)
                    except Exception as e:
                        logger.debug(f"Cleanup failed: {e}")

                    return transcript.strip() if transcript else None
                else:
                    logger.info(f"Recording too small: {file_size} bytes")
                    # Cleanup small/empty file
                    try:
                        os.unlink(wav_file)
                        if os.path.exists(rx_wav_file):
                            os.unlink(rx_wav_file)
                    except:
                        pass
                    return None
            else:
                logger.warning("No recording file created")
                return None

        except Exception as e:
            logger.error(f"MixMonitor recording error: {e}")
            # Ensure cleanup
            try:
                self.agi.command(f'EXEC StopMixMonitor ${{{mm_var}}}')
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
                if os.path.exists(rx_wav_file):
                    os.unlink(rx_wav_file)
            except:
                pass
            return None

    def record_with_voice_interrupt(self, filename, timeout=3):
        """
        Record with voice interruption capability using MixMonitor
        Used for detecting user speech during TTS playback
        """
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/interrupt_{unique_id}"
        wav_file = f"{record_file}.wav"           # mixed
        rx_wav_file = f"{record_file}_rx.wav"     # inbound-only

        logger.info(f"Starting interrupt detection: {record_file}")

        try:
            # Start MixMonitor for interrupt detection; also capture RX-only stream
            mm_var = f"MMID_{unique_id}"
            mixmonitor_cmd = f'EXEC MixMonitor {record_file}.wav,r({record_file}_rx.wav),i({mm_var})'
            result = self.agi.command(mixmonitor_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start interrupt MixMonitor: {result}")
                return False, None

            # Wait for timeout or voice detection
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.agi.connected:
                    break

                # Check for voice activity on RX-only file
                if os.path.exists(rx_wav_file):
                    file_size = os.path.getsize(rx_wav_file)
                    if file_size > 200:  # Voice detected - lower threshold
                        logger.info(f"Voice interrupt detected: {file_size} bytes")

                        # Stop recording (specific instance)
                        self.agi.command(f'EXEC StopMixMonitor ${{{mm_var}}}')
                        time.sleep(0.1)

                        # Transcribe interruption from RX-only file
                        if os.path.exists(rx_wav_file):
                            asr_input = self._prepare_asr_input(rx_wav_file)
                            transcript = self.asr.transcribe_file(asr_input)
                            try:
                                if asr_input != rx_wav_file and os.path.exists(asr_input):
                                    os.unlink(asr_input)
                            except Exception:
                                pass

                            # Cleanup
                            try:
                                if os.path.exists(wav_file):
                                    os.unlink(wav_file)
                                if os.path.exists(rx_wav_file):
                                    os.unlink(rx_wav_file)
                            except:
                                pass

                            if transcript and len(transcript.strip()) > 1:
                                return True, transcript.strip()
                            else:
                                return True, "VOICE_DETECTED"

                time.sleep(0.1)  # Check every 100ms for fast response

            # No interruption detected
            self.agi.command(f'EXEC StopMixMonitor ${{{mm_var}}}')

            # Cleanup
            try:
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
                if os.path.exists(rx_wav_file):
                    os.unlink(rx_wav_file)
            except:
                pass

            return False, None
        except Exception as e:
            logger.error(f"Interrupt recording error: {e}")
            # Cleanup
            try:
                self.agi.command(f'EXEC StopMixMonitor ${{{mm_var}}}')
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
                if os.path.exists(rx_wav_file):
                    os.unlink(rx_wav_file)
            except Exception:
                pass
            return False, None

    # --- Background interrupt monitor for barge-in during TTS ---
    @dataclass
    class InterruptResult:
        activated: bool = False
        transcript: str = ""

    def start_interrupt_monitor(self, window_sec=5, min_bytes=4096, arm_delay_ms=0):
        """Start a short MixMonitor in background to detect caller voice during TTS.
        Returns (thread, stop_event, result_holder)."""
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/barge_{unique_id}"
        wav_file = f"{record_file}.wav"           # mixed
        rx_wav_file = f"{record_file}_rx.wav"     # inbound-only
        mm_id_var = f"MMID_{unique_id}"

        stop_event = threading.Event()
        result = ProductionCallRecorder.InterruptResult()

        def _runner():
            try:
                # Start MixMonitor capturing mixed and RX-only, store ID in chan var
                self.agi.command(f'EXEC MixMonitor {record_file}.wav,r({record_file}_rx.wav),i({mm_id_var})')
                t0 = time.time()
                voice_seen = False
                while not stop_event.is_set() and (time.time() - t0) < window_sec and self.agi.connected:
                    # Arm delay window to ignore initial bot audio
                    if arm_delay_ms and ((time.time() - t0) * 1000.0) < arm_delay_ms:
                        time.sleep(0.05)
                        continue
                    sz = self._file_size(rx_wav_file)
                    if sz >= min_bytes:
                        voice_seen = True
                        break
                    time.sleep(0.08)

                if voice_seen:
                    # user started speaking: wait a bit shorter for EOS to capture phrase
                    self._wait_for_end_of_speech(rx_wav_file, min_bytes=max(1, min_bytes // 2), idle_ms=600)
                    try:
                        txt = self.asr.transcribe_file(rx_wav_file) or ""
                    except Exception:
                        txt = ""
                    # Only mark as activated if we actually captured caller speech
                    txt_clean = txt.strip()
                    if txt_clean:
                        result.transcript = txt_clean
                        result.activated = True
                    else:
                        result.transcript = ""
                        result.activated = False
            finally:
                try:
                    # Stop only this instance using stored ID
                    self.agi.command(f'EXEC StopMixMonitor ${{{mm_id_var}}}')
                except Exception:
                    pass
                # cleanup temp barge recording to avoid disk bloat
                try:
                    if os.path.exists(wav_file):
                        os.unlink(wav_file)
                    if os.path.exists(rx_wav_file):
                        os.unlink(rx_wav_file)
                except Exception:
                    pass

        th = threading.Thread(target=_runner, daemon=True)
        th.start()
        return th, stop_event, result
