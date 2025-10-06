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
import re

logger = logging.getLogger(__name__)

class SimpleAGI:
    """Minimal AGI with correct command syntax"""

    def __init__(self):
        self.env = {}
        self.connected = True
        self.call_answered = False
        self._parse_env()

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

    # --- Helper to stream an arbitrary WAV that already lives in Asterisk sounds ---
    def stream_external_wav(self, abs_wav_path: str):
        """Play an arbitrary WAV file by converting/copying to sounds and streaming."""
        try:
            if not abs_wav_path:
                return False
            if not os.path.exists(abs_wav_path):
                logger.error(f"External WAV missing: {abs_wav_path}")
                return False
            # If caller passed a bare filename created by converter, just stream it
            if abs_wav_path.startswith("/usr/share/asterisk/sounds/"):
                base = abs_wav_path[len("/usr/share/asterisk/sounds/"):]
                if base.endswith('.wav'):
                    base = base[:-4]
                return self.stream_file(base)

            # Otherwise, copy to sounds tmp with unique name
            unique = f"ext_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            dst = f"/usr/share/asterisk/sounds/{unique}.wav"
            try:
                import shutil
                shutil.copyfile(abs_wav_path, dst)
            except Exception as e:
                logger.error(f"Copy external wav failed: {e}")
                return False
            ok = self.stream_file(unique)
            # Cleanup temp copy to avoid disk bloat
            try:
                if os.path.exists(dst):
                    os.unlink(dst)
            except Exception as e:
                logger.debug(f"Temp WAV cleanup skipped: {e}")
            return ok
        except Exception as e:
            logger.error(f"stream_external_wav error: {e}")
            return False

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


# --- Chunked TTS playback with interrupt checks between chunks ---
SENTENCE_SPLIT = re.compile(r'([.!?]+)\s+')

def _chunk_text_for_tts(text: str, max_chars: int = 140):
    parts, cur = [], ""
    # Simple whitespace-based splitting with soft sentence handling
    tokens = text.split()
    for word in tokens:
        if len(cur) + (1 if cur else 0) + len(word) > max_chars:
            if cur:
                parts.append(cur)
            cur = word
        else:
            cur = (cur + (" " if cur else "") + word)
    if cur:
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]

def play_chunks_with_interrupt(agi: SimpleAGI, tts_client, text: str, voice_type: str = "default",
                               check_stop=lambda: False, on_chunk_played=None):
    """Synthesize small chunks and play them one-by-one.
    Between chunks, check stop flag; if set, abort immediately.
    tts_client.synthesize should return a WAV path compatible with stream_external_wav.
    """
    chunks = _chunk_text_for_tts(text)
    for ch in chunks:
        if check_stop():
            return "INTERRUPTED"
        wav_file = tts_client.synthesize(ch, voice_type=voice_type)
        if not wav_file:
            continue
        agi.stream_external_wav(wav_file)
        if on_chunk_played is not None:
            try:
                on_chunk_played(ch)
            except Exception:
                pass
        time.sleep(0.02)
    return "OK"
