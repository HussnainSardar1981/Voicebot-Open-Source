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
        """Play audio with TRUE voice interruption - only monitors user audio, not bot"""
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        logger.info(f"Playing with voice interrupt (fixed): {filename}")

        # Start background playback
        self.command(f'EXEC Background {filename}')

        # Monitor using talk detection instead of recording mixed audio
        # This approach avoids recording bot's own voice
        start_time = time.time()
        max_playback_time = 30  # Maximum seconds to monitor
        check_interval = 0.2    # Check every 200ms for responsiveness

        while time.time() - start_time < max_playback_time:
            # Check if playback is still running
            playback_status = self.command('GET OPTION "" 100')  # 100ms timeout

            # Check for DTMF or hangup (user interaction)
            if playback_status and not playback_status.startswith('200 result=0'):
                # User pressed key or call ended
                if 'hangup' in playback_status.lower() or 'result=-1' in playback_status:
                    logger.info("Call hung up during playback")
                    self.connected = False
                    return False, None
                else:
                    logger.info("DTMF detected - stopping playback")
                    self.command('EXEC StopPlayback')
                    return False, "DTMF_DETECTED"

            # Use a short recording window to detect voice activity
            # Record ONLY inbound audio (not mixed) using proper channel monitoring
            monitor_file = f"/var/spool/asterisk/monitor/inbound_{int(time.time())}_{uuid.uuid4().hex[:4]}"

            # Record from inbound channel only (not mixed audio)
            # This avoids capturing bot's voice
            record_result = self.command(f'RECORD FILE {monitor_file} wav "#" 500 0 2')

            wav_file = f"{monitor_file}.wav"
            voice_detected = False

            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)

                # Lower threshold since we're only capturing user audio
                if file_size > 150:  # User voice detected
                    logger.info(f"User voice detected: {file_size} bytes")
                    voice_detected = True

                # Always cleanup the monitoring file
                try:
                    os.unlink(wav_file)
                except:
                    pass

            if voice_detected:
                logger.info("User spoke - stopping playback for clean recording")
                self.command('EXEC StopPlayback')

                # Now do a clean recording session (no background audio)
                time.sleep(0.2)  # Brief pause to let playback stop

                # Clean recording session for transcription
                clean_record_file = f"/var/spool/asterisk/monitor/clean_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                clean_result = self.command(f'RECORD FILE {clean_record_file} wav "#" 8000 0 2')

                clean_wav_file = f"{clean_record_file}.wav"
                transcript = ""

                if os.path.exists(clean_wav_file):
                    clean_size = os.path.getsize(clean_wav_file)
                    logger.info(f"Clean recording: {clean_size} bytes")

                    if clean_size > 200:
                        transcript = asr_client.transcribe_file(clean_wav_file)

                    # Cleanup
                    try:
                        os.unlink(clean_wav_file)
                    except:
                        pass

                if transcript and len(transcript.strip()) > 2:
                    logger.info(f"Voice interrupt transcript: {transcript[:50]}...")
                    return False, transcript
                else:
                    logger.info("Voice detected but no clear transcript")
                    return False, "VOICE_DETECTED"

            # Brief sleep before next check
            time.sleep(check_interval)

        # If we get here, playback completed without interruption
        logger.info("Playback completed without user interruption")
        return True, None

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
