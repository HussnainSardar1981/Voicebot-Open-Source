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
        """
        DEPRECATED: Use ProductionCallRecorder.detect_barge_in_with_talk_detect() instead
        Maintained for backward compatibility - delegates to modern TALK_DETECT implementation
        """
        logger.warning("play_with_voice_interrupt is deprecated - use ProductionCallRecorder for professional barge-in")

        # Simple fallback - just play the file without interruption
        # Real barge-in should use ProductionCallRecorder.detect_barge_in_with_talk_detect()
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        logger.info(f"Simple playback (no interruption): {filename}")
        result = self.command(f'STREAM FILE {filename} ""')
        success = result and result.startswith('200')

        if success:
            logger.info("Playback completed")
            return True, None
        else:
            logger.warning(f"Playback failed: {result}")
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


# FastInterruptRecorder class removed - use ProductionCallRecorder instead
# This class has been deprecated in favor of the professional-grade
# ProductionCallRecorder with TALK_DETECT and MixMonitor capabilities
