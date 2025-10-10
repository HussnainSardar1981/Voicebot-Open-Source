#!/usr/bin/env python3
"""
Asterisk-Compatible Voice Interruption System
Real-time voice interruption using Asterisk audio streams (not system microphone)
"""

import os
import time
import uuid
import logging
import threading
import subprocess
from collections import deque

logger = logging.getLogger(__name__)

class AsteriskVoiceDetector:
    """
    Real-time voice activity detection using Asterisk MixMonitor streams
    This works with telephony audio (SIP/RTP) instead of system microphones
    """

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client
        self.monitoring = False
        self.current_recording = None
        self.interrupt_detected = False
        self.playback_active = False
        self.monitor_thread = None

    def start_call_monitoring(self):
        """Start monitoring call audio for voice interruption"""
        if self.monitoring:
            return True

        # Create unique recording session for the entire call
        unique_id = f"voice_monitor_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        self.current_recording = f"/var/spool/asterisk/monitor/{unique_id}.wav"

        # Start MixMonitor for continuous call recording
        mixmonitor_cmd = f'EXEC MixMonitor {unique_id}.wav'
        result = self.agi.command(mixmonitor_cmd)

        if not result or not result.startswith('200'):
            logger.error(f"Failed to start call monitoring: {result}")
            return False

        self.monitoring = True
        logger.info(f"Asterisk voice monitoring started: {unique_id}")
        return True

    def stop_call_monitoring(self):
        """Stop call monitoring"""
        if self.monitoring:
            self.agi.command('EXEC StopMixMonitor')
            self.monitoring = False

            # Cleanup recording file
            try:
                if self.current_recording and os.path.exists(self.current_recording):
                    os.unlink(self.current_recording)
            except:
                pass

            logger.info("Asterisk voice monitoring stopped")

    def play_with_voice_interrupt(self, filename, detection_interval=0.2):
        """
        Play audio with real-time voice interruption detection
        Uses file size monitoring of MixMonitor recording for voice detection
        """
        if not self.monitoring:
            if not self.start_call_monitoring():
                # Fallback to normal playback
                success = self.agi.stream_file(filename)
                return success, None

        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        logger.info(f"Playing with Asterisk voice interruption: {filename}")

        # Reset state
        self.interrupt_detected = False
        self.playback_active = True

        # Record baseline file size before playback
        baseline_size = 0
        if os.path.exists(self.current_recording):
            baseline_size = os.path.getsize(self.current_recording)

        # Start playback in background thread
        playback_result = {'completed': False, 'success': False, 'interrupted': False}

        def play_audio():
            try:
                # Allow DTMF to stop playback
                result = self.agi.command(f'STREAM FILE {filename} "*#"')
                playback_result['success'] = result and result.startswith('200')

                # Check if interrupted by DTMF
                if result and 'digit=' in result:
                    playback_result['interrupted'] = True
                    logger.info("Playback interrupted by DTMF")

                playback_result['completed'] = True
            except Exception as e:
                logger.error(f"Playback error: {e}")
                playback_result['completed'] = True

        playback_thread = threading.Thread(target=play_audio, daemon=True)
        playback_thread.start()

        # Monitor for voice activity during playback
        last_size = baseline_size
        voice_detection_threshold = 2048  # 2KB file growth indicates voice activity
        silence_frames = 0
        voice_detected_frames = 0

        while self.playback_active and not playback_result['completed']:
            time.sleep(detection_interval)

            # Check current file size
            if os.path.exists(self.current_recording):
                current_size = os.path.getsize(self.current_recording)
                size_growth = current_size - last_size

                if size_growth > voice_detection_threshold:
                    voice_detected_frames += 1
                    silence_frames = 0

                    # If we detect voice activity for 2 consecutive checks
                    if voice_detected_frames >= 2:
                        logger.info("Voice interruption detected via file growth!")
                        self.interrupt_detected = True
                        self.playback_active = False

                        # Stop playback
                        self.agi.command('EXEC SendDTMF *')
                        break
                else:
                    silence_frames += 1
                    if silence_frames > 2:  # Reset voice detection after silence
                        voice_detected_frames = 0

                last_size = current_size

            # Check if playback completed naturally
            if playback_result['completed']:
                break

            # Check for call disconnection
            if not self.agi.connected:
                logger.info("Call disconnected during playback")
                self.playback_active = False
                break

        # Wait for playback thread to finish
        playback_thread.join(timeout=2)
        self.playback_active = False

        # Handle interruption
        if self.interrupt_detected:
            logger.info("Processing voice interruption...")
            time.sleep(0.5)  # Brief pause for user to finish speaking

            # Capture the interruption
            transcript = self._capture_interruption_speech()
            return False, transcript  # Interrupted
        elif playback_result['interrupted']:
            # DTMF interruption fallback
            transcript = self._capture_dtmf_interruption()
            return playback_result['success'], transcript
        else:
            # Completed normally
            logger.info("Playback completed without interruption")
            return playback_result['success'], None

    def _capture_interruption_speech(self):
        """Capture speech after voice interruption detected"""
        record_file = f"/var/spool/asterisk/monitor/interrupt_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        logger.info("Capturing speech after voice interruption...")

        try:
            # Record user speech (shorter timeout for responsiveness)
            result = self.agi.command(f'RECORD FILE {record_file} wav "#" 8000 0 2')

            wav_file = f"{record_file}.wav"
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)
                logger.info(f"Interruption capture: {file_size} bytes")

                if file_size > 800:  # Reasonable speech threshold
                    transcript = self.asr.transcribe_file(wav_file)

                    # Cleanup
                    try:
                        os.unlink(wav_file)
                    except:
                        pass

                    return transcript.strip() if transcript else "VOICE_DETECTED"
                else:
                    # File too small
                    try:
                        os.unlink(wav_file)
                    except:
                        pass

            return "VOICE_DETECTED"

        except Exception as e:
            logger.error(f"Speech capture error: {e}")
            return "VOICE_DETECTED"

    def _capture_dtmf_interruption(self):
        """Handle DTMF-based interruption as fallback"""
        record_file = f"/var/spool/asterisk/monitor/dtmf_interrupt_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        logger.info("DTMF interruption - listening for speech...")

        try:
            result = self.agi.command(f'RECORD FILE {record_file} wav "#" 10000 0 2')

            wav_file = f"{record_file}.wav"
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)
                if file_size > 800:
                    transcript = self.asr.transcribe_file(wav_file)
                    try:
                        os.unlink(wav_file)
                    except:
                        pass
                    return transcript.strip() if transcript else "VOICE_DETECTED"
                else:
                    try:
                        os.unlink(wav_file)
                    except:
                        pass

            return "DTMF_INTERRUPT"

        except Exception as e:
            logger.error(f"DTMF capture error: {e}")
            return "DTMF_INTERRUPT"


class EnhancedAGI:
    """
    Enhanced AGI with Asterisk-compatible voice interruption
    Works with telephony audio streams (not system microphone)
    """

    def __init__(self, base_agi, asr_client):
        self.agi = base_agi
        self.asr = asr_client
        self.voice_detector = AsteriskVoiceDetector(base_agi, asr_client)

    def __getattr__(self, name):
        """Delegate all other methods to base AGI"""
        return getattr(self.agi, name)

    def play_with_voice_interrupt(self, filename, asr_client=None):
        """
        Asterisk-compatible voice interruption
        Returns: (success, interrupt_transcript)
        """
        try:
            success, interrupt = self.voice_detector.play_with_voice_interrupt(filename)

            if interrupt and interrupt not in ["VOICE_DETECTED", "DTMF_INTERRUPT"]:
                logger.info(f"Voice interruption with transcript: {interrupt[:50]}")
                return success, interrupt
            elif interrupt == "VOICE_DETECTED":
                logger.info("Voice interruption detected")
                return success, "VOICE_DETECTED"
            elif interrupt == "DTMF_INTERRUPT":
                logger.info("DTMF interruption detected")
                return success, "VOICE_DETECTED"  # Treat as voice for consistency
            else:
                logger.info(f"Playback completed normally: {success}")
                return success, None

        except Exception as e:
            logger.error(f"Asterisk voice interruption error: {e}")
            # Emergency fallback
            success = self.agi.stream_file(filename)
            return success, None

    def start_call_monitoring(self):
        """Start voice monitoring for the call"""
        return self.voice_detector.start_call_monitoring()

    def stop_call_monitoring(self):
        """Stop voice monitoring"""
        self.voice_detector.stop_call_monitoring()

    def set_voice_detection_sensitivity(self, threshold_bytes=2048):
        """Adjust voice detection sensitivity (bytes of file growth)"""
        # This could be implemented to adjust detection thresholds
        logger.info(f"Voice detection threshold: {threshold_bytes} bytes")

    def get_interrupt_capability_description(self):
        """Describe the voice interruption capability"""
        return "You can interrupt me by speaking at any time, or press star (*) on your keypad"
