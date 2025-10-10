#!/usr/bin/env python3
"""
Robust Voice Interruption System for VoiceBot
Production-grade barge-in without breaking AGI calls
"""

import os
import time
import uuid
import threading
import logging
from queue import Queue, Empty

logger = logging.getLogger(__name__)

class RobustVoiceInterrupt:
    """
    Production-grade voice interruption that won't break your voicebot
    Uses single MixMonitor session with background monitoring
    """

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client
        self.monitoring = False
        self.monitor_thread = None
        self.interrupt_queue = Queue()
        self.current_recording = None
        self.last_file_size = 0
        self.speech_detected = False

    def start_monitoring(self):
        """Start background voice monitoring (once per call)"""
        if self.monitoring:
            return True

        # Create unique recording session
        unique_id = f"call_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        self.current_recording = f"/var/spool/asterisk/monitor/{unique_id}.wav"

        # Start MixMonitor ONCE for the entire call
        mixmonitor_cmd = f'EXEC MixMonitor {unique_id}.wav'
        result = self.agi.command(mixmonitor_cmd)

        if not result or not result.startswith('200'):
            logger.error(f"Failed to start MixMonitor: {result}")
            return False

        self.monitoring = True
        self.last_file_size = 0

        # Start background monitoring thread
        self.monitor_thread = threading.Thread(target=self._background_monitor, daemon=True)
        self.monitor_thread.start()

        logger.info(f"Voice monitoring started: {self.current_recording}")
        return True

    def stop_monitoring(self):
        """Stop voice monitoring (once per call)"""
        if not self.monitoring:
            return

        self.monitoring = False

        # Stop MixMonitor
        self.agi.command('EXEC StopMixMonitor')

        # Wait for thread to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        # Cleanup recording file
        try:
            if self.current_recording and os.path.exists(self.current_recording):
                os.unlink(self.current_recording)
        except Exception as e:
            logger.debug(f"Cleanup failed: {e}")

        logger.info("Voice monitoring stopped")

    def _background_monitor(self):
        """Background thread to monitor voice activity"""
        while self.monitoring and self.agi.connected:
            try:
                if os.path.exists(self.current_recording):
                    current_size = os.path.getsize(self.current_recording)

                    # Detect voice activity (file growth)
                    if current_size > self.last_file_size + 1024:  # 1KB growth
                        if not self.speech_detected:
                            self.speech_detected = True
                            self.interrupt_queue.put({
                                'type': 'speech_detected',
                                'timestamp': time.time(),
                                'file_size': current_size
                            })

                        self.last_file_size = current_size

                time.sleep(0.1)  # Check every 100ms

            except Exception as e:
                logger.debug(f"Monitor error: {e}")
                break

    def play_with_interrupt_detection(self, filename, max_play_time=10):
        """
        Play audio file with voice interruption detection
        Returns: (completed_playback, was_interrupted, interrupt_transcript)
        """
        if not self.monitoring:
            if not self.start_monitoring():
                # Fallback to normal playback
                success = self.agi.stream_file(filename)
                return success, False, None

        # Clear any previous interrupts
        while not self.interrupt_queue.empty():
            try:
                self.interrupt_queue.get_nowait()
            except Empty:
                break

        self.speech_detected = False
        logger.info(f"Playing with interrupt detection: {filename}")

        # Start playback in separate thread to enable interruption
        playback_thread = threading.Thread(
            target=self._threaded_playback,
            args=(filename,),
            daemon=True
        )
        playback_thread.start()

        # Monitor for interruptions during playback
        start_time = time.time()
        while time.time() - start_time < max_play_time:
            # Check for voice interruption
            try:
                interrupt_event = self.interrupt_queue.get(timeout=0.1)
                logger.info("Voice interruption detected during playback!")

                # Stop playback by sending DTMF (Asterisk standard)
                self.agi.command('EXEC SendDTMF *')  # Stop current audio

                # Wait a moment for user to finish speaking
                time.sleep(1.5)

                # Get transcript of the interruption
                transcript = self._get_interruption_transcript()

                # Wait for playback thread to finish
                playback_thread.join(timeout=1)

                return False, True, transcript

            except Empty:
                continue

            # Check if playback completed
            if not playback_thread.is_alive():
                logger.info("Playback completed without interruption")
                return True, False, None

            if not self.agi.connected:
                logger.info("Call disconnected during playback")
                return False, False, None

        # Timeout reached
        logger.info("Playback timeout reached")
        playback_thread.join(timeout=1)
        return True, False, None

    def _threaded_playback(self, filename):
        """Play audio file in separate thread"""
        try:
            # Remove extension if present
            if '.' in filename:
                filename = filename.rsplit('.', 1)[0]

            # Play file (this blocks until complete or interrupted)
            result = self.agi.command(f'STREAM FILE {filename} "*"')  # Allow * to stop
            logger.debug(f"Playback result: {result}")

        except Exception as e:
            logger.error(f"Playback error: {e}")

    def _get_interruption_transcript(self):
        """Get transcript of voice interruption"""
        if not self.current_recording or not os.path.exists(self.current_recording):
            return None

        try:
            # Wait for file to stabilize
            time.sleep(0.5)

            # Create a copy for transcription (avoid file conflicts)
            temp_file = f"{self.current_recording}.temp"
            os.system(f"cp {self.current_recording} {temp_file}")

            # Transcribe the interruption
            transcript = self.asr.transcribe_file(temp_file)

            # Cleanup temp file
            try:
                os.unlink(temp_file)
            except:
                pass

            return transcript.strip() if transcript else None

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None


# Enhanced AGI Interface with Robust Interruption
class EnhancedAGI:
    """AGI with robust voice interruption capabilities"""

    def __init__(self, base_agi, asr_client):
        self.agi = base_agi
        self.voice_interrupt = RobustVoiceInterrupt(base_agi, asr_client)

    def __getattr__(self, name):
        """Delegate all other methods to base AGI"""
        return getattr(self.agi, name)

    def play_with_voice_interrupt(self, filename, asr_client=None):
        """
        Enhanced play with voice interrupt - production grade
        Returns: (success, interrupt_transcript)
        """
        try:
            success, interrupted, transcript = self.voice_interrupt.play_with_interrupt_detection(filename)

            if interrupted and transcript:
                logger.info(f"Playback interrupted with speech: {transcript[:30]}...")
                return success, transcript
            elif interrupted:
                logger.info("Playback interrupted (voice detected)")
                return success, "VOICE_DETECTED"
            else:
                logger.info(f"Playback completed: {success}")
                return success, None

        except Exception as e:
            logger.error(f"Enhanced playback error: {e}")
            # Fallback to normal playback
            success = self.agi.stream_file(filename)
            return success, None

    def start_call_monitoring(self):
        """Start voice monitoring for the entire call"""
        return self.voice_interrupt.start_monitoring()

    def stop_call_monitoring(self):
        """Stop voice monitoring for the call"""
        self.voice_interrupt.stop_monitoring()
