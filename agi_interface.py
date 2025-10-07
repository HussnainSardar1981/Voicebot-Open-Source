#!/usr/bin/env python3
"""
AGI Interface Components - Asterisk communication and recording
Extracted from production_agi_voicebot.py
"""

import sys
import os
import time
import uuid
import logging

logger = logging.getLogger(__name__)

class SimpleAGI:
    """Minimal AGI with correct command syntax"""

    def __init__(self):
        self.env = {}
        self.connected = True
        self.call_answered = False
        self._parse_env()

    def _start_mixmonitor(self, rec_basename):
        # rec_basename without extension; Asterisk will add .wav
        return self.command(f'EXEC MixMonitor {rec_basename}.wav')

    def _stop_mixmonitor(self):
        return self.command('EXEC StopMixMonitor')

    def _parse_env(self):
        """Parse AGI environment"""
        env_count = 0
        while True:
            line = sys.stdin.readline()
            if not line or not line.strip():
                break
            if ':' in line:
                key, value = line.split(':', 1)
                self.env[key.strip()] = value.strip()
                env_count += 1
        logger.info(f"AGI env parsed: {env_count} vars")

    def command(self, cmd):
        """Send AGI command"""
        try:
            logger.debug(f"AGI: {cmd}")
            print(cmd)
            sys.stdout.flush()

            result = sys.stdin.readline().strip()
            logger.debug(f"Response: {result}")

            # Detect hangup scenarios
            if result.startswith('200 result=-1') or 'hangup' in result.lower():
                logger.info("Hangup detected via AGI response")
                self.connected = False

            return result
        except Exception as e:
            logger.error(f"AGI command failed: {e}")
            self.connected = False
            return "ERROR"

    def answer(self):
        """Answer call"""
        # Check if call is already answered
        status_result = self.command("CHANNEL STATUS")
        if "result=6" in status_result:  # Already answered
            logger.info("Call already answered")
            self.call_answered = True
            return True

        result = self.command("ANSWER")
        success = result and result.startswith('200')
        if success:
            self.call_answered = True
            logger.info("Call answered successfully")
        else:
            logger.error(f"Failed to answer call: {result}")
        return success

    def hangup(self):
        """Hangup call"""
        self.command("HANGUP")
        self.connected = False

    def verbose(self, msg):
        """Verbose message"""
        return self.command(f'VERBOSE "{msg}"')

    def stream_file(self, filename):
        """Play audio file - NO QUOTES on filename"""
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        # Check for both WAV and SLIN16 files in root sounds directory
        wav_path = f"/usr/share/asterisk/sounds/{filename}.wav"
        sln16_path = f"/usr/share/asterisk/sounds/{filename}.sln16"

        if os.path.exists(wav_path):
            file_size = os.path.getsize(wav_path)
            logger.info(f"Playing WAV: {filename} (file exists: {file_size} bytes)")
        elif os.path.exists(sln16_path):
            file_size = os.path.getsize(sln16_path)
            logger.info(f"Playing SLIN16: {filename} (file exists: {file_size} bytes)")
        else:
            logger.error(f"Audio file not found: {wav_path} or {sln16_path}")

        result = self.command(f'STREAM FILE {filename} ""')
        success = result and result.startswith('200')
        logger.info(f"Stream file result: {result} (success: {success})")
        return success

    def play_with_voice_interrupt(self, filename, asr_client):
        """Play audio with simple barge-in detection - no hangup issues"""
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        logger.info(f"Playing with voice interrupt (simplified): {filename}")

        # Simple approach: Just play the file normally first
        # This eliminates complex monitoring that was causing hangups
        result = self.command(f'STREAM FILE {filename} ""')
        success = result and result.startswith('200')

        if success:
            logger.info("Greeting completed successfully")
            return True, None
        else:
            logger.warning(f"Playback had issues: {result}")
            return False, None
        
    def play_response_with_barge_in(self, chunk_filenames, vad_window_ms=250):
        """
        Plays short audio chunks (filenames may include .wav/.sln16 or bare name).
        Between chunks, quickly checks MixMonitor file growth (~vad_window_ms).
        If caller speech is detected, stops further playback and returns.
        Returns (played_all, detected_speech).
        """
        rec_id = f"mm_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        rec_base = f"/var/spool/asterisk/monitor/{rec_id}"
        rec_path = f"{rec_base}.wav"
        self._start_mixmonitor(rec_base)

        detected_speech = False
        try:
            for fname in chunk_filenames:
                if not self.connected:
                    break

                # Normalize filename for STREAM FILE (no extension)
                base = fname
                if '.' in base:
                    base = base.rsplit('.', 1)[0]

                # Play one short chunk (no DTMF keys allowed)
                res = self.command(f'STREAM FILE {base} ""')
                ok = res and res.startswith('200')
                if not ok:
                    logger.warning(f"Chunk playback issue: {res}")

                # Quick VAD window: ~250 ms checking MixMonitor size growth
                end_by = time.time() + (vad_window_ms / 1000.0)
                last_size = os.path.getsize(rec_path) if os.path.exists(rec_path) else 0
                while time.time() < end_by:
                    time.sleep(0.05)
                    size = os.path.getsize(rec_path) if os.path.exists(rec_path) else 0
                    if size > last_size + 1024:  # ~1KB growth ≈ recent caller voice
                        detected_speech = True
                        break

                if detected_speech:
                    break

            played_all = not detected_speech
            return played_all, detected_speech
        finally:
            self._stop_mixmonitor()


    def record_file(self, filename):
        """Record audio - SIMPLE syntax without beep"""
        result = self.command(f'RECORD FILE {filename} wav "#" 15000 0 2')
        # Check for hangup during recording
        if result and 'result=-1' in result:
            logger.info("Hangup detected during recording")
            self.connected = False
            return False
        return result and result.startswith('200')

    def sleep(self, seconds):
        """Sleep"""
        time.sleep(seconds)


class FastInterruptRecorder:
    """Simple, fast interrupt-capable recorder"""

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client

    def get_user_input_with_interrupt(self, timeout=10):
        """Get user input with fast interrupt capability"""
        record_file = f"/var/spool/asterisk/monitor/user_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        logger.info("Listening for user input...")
        # Shorter timeout for faster responsiveness
        result = self.agi.command(f'RECORD FILE {record_file} wav "#" {timeout * 1000} 0 2')

        if not self.agi.connected:
            return None

        wav_file = f"{record_file}.wav"
        transcript = ""

        if os.path.exists(wav_file):
            file_size = os.path.getsize(wav_file)
            logger.info(f"Recording: {file_size} bytes")

            if file_size > 300:  # Lower threshold for better detection
                transcript = self.asr.transcribe_file(wav_file)

            # Cleanup
            try:
                os.unlink(wav_file)
            except Exception as e:
                logger.debug(f"Cleanup failed: {e}")

        return transcript.strip() if transcript else None
