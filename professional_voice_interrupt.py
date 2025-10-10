#!/usr/bin/env python3
"""
Professional Voice Interruption using WebRTC VAD
Production-grade voice activity detection used by commercial voice agents
"""

import os
import sys
import time
import uuid
import logging
import threading
import subprocess
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

# Check for required libraries
try:
    import webrtcvad
    import pyaudio
except ImportError as e:
    logger.error(f"Missing required library: {e}")
    logger.error("Install with: pip install webrtcvad pyaudio")
    sys.exit(1)

class WebRTCVoiceDetector:
    """
    Professional Voice Activity Detection using Google's WebRTC VAD
    This is the same technology used by Google Meet, Zoom, and commercial voice systems
    """

    def __init__(self, aggressiveness=2, sample_rate=16000, frame_duration=30):
        """
        Initialize WebRTC VAD
        aggressiveness: 0-3 (0=least aggressive, 3=most aggressive)
        sample_rate: 8000, 16000, 32000, or 48000 Hz
        frame_duration: 10, 20, or 30 ms
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration
        self.frame_size = int(sample_rate * frame_duration / 1000)
        self.bytes_per_frame = self.frame_size * 2  # 16-bit audio

        # Voice activity detection parameters
        self.voice_frames = deque(maxlen=10)  # Track last 10 frames
        self.speech_threshold = 0.6  # 60% of frames must contain speech

        logger.info(f"WebRTC VAD initialized: aggressiveness={aggressiveness}, "
                   f"sample_rate={sample_rate}, frame_duration={frame_duration}ms")

    def is_speech(self, audio_frame):
        """
        Detect if audio frame contains speech
        Returns: True if speech detected, False otherwise
        """
        if len(audio_frame) != self.bytes_per_frame:
            return False

        try:
            # WebRTC VAD expects 16-bit PCM audio
            is_voice = self.vad.is_speech(audio_frame, self.sample_rate)

            # Add to rolling window
            self.voice_frames.append(is_voice)

            # Calculate speech ratio in recent frames
            if len(self.voice_frames) >= 5:  # Need at least 5 frames
                speech_ratio = sum(self.voice_frames) / len(self.voice_frames)
                return speech_ratio >= self.speech_threshold

            return is_voice

        except Exception as e:
            logger.debug(f"VAD error: {e}")
            return False

    def reset(self):
        """Reset voice detection state"""
        self.voice_frames.clear()


class RealTimeAudioProcessor:
    """
    Real-time audio processing for voice interruption detection
    Uses PyAudio for low-latency audio capture
    """

    def __init__(self, vad_detector, sample_rate=16000, chunk_size=480):
        self.vad = vad_detector
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size  # 30ms at 16kHz
        self.audio = None
        self.stream = None
        self.processing = False
        self.speech_detected = False
        self.speech_callback = None

    def start_monitoring(self, speech_callback=None):
        """Start real-time audio monitoring"""
        try:
            self.audio = pyaudio.PyAudio()
            self.speech_callback = speech_callback

            # Find default input device
            input_device = self.audio.get_default_input_device_info()
            logger.info(f"Using audio input: {input_device['name']}")

            # Open audio stream
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )

            self.processing = True
            self.stream.start_stream()
            logger.info("Real-time audio monitoring started")
            return True

        except Exception as e:
            logger.error(f"Failed to start audio monitoring: {e}")
            return False

    def stop_monitoring(self):
        """Stop real-time audio monitoring"""
        self.processing = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.audio:
            self.audio.terminate()

        logger.info("Real-time audio monitoring stopped")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for real-time audio processing"""
        if self.processing and len(in_data) == self.vad.bytes_per_frame:
            is_speech = self.vad.is_speech(in_data)

            if is_speech and not self.speech_detected:
                self.speech_detected = True
                logger.info("Voice activity detected!")

                # Notify callback
                if self.speech_callback:
                    threading.Thread(
                        target=self.speech_callback,
                        daemon=True
                    ).start()

        return (in_data, pyaudio.paContinue)

    def reset_detection(self):
        """Reset speech detection state"""
        self.speech_detected = False
        self.vad.reset()


class ProfessionalVoiceInterrupt:
    """
    Professional voice interruption system using WebRTC VAD + PyAudio
    Production-grade solution used by commercial voice agents
    """

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client

        # Initialize WebRTC VAD (aggressiveness=2 for balanced detection)
        self.vad_detector = WebRTCVoiceDetector(aggressiveness=2)
        self.audio_processor = RealTimeAudioProcessor(self.vad_detector)

        self.monitoring = False
        self.interrupt_detected = False
        self.playback_active = False

    def start_voice_monitoring(self):
        """Start professional voice activity monitoring"""
        if self.monitoring:
            return True

        success = self.audio_processor.start_monitoring(
            speech_callback=self._on_speech_detected
        )

        if success:
            self.monitoring = True
            logger.info("Professional voice monitoring started (WebRTC VAD)")
        else:
            logger.error("Failed to start voice monitoring")

        return success

    def stop_voice_monitoring(self):
        """Stop voice monitoring"""
        if self.monitoring:
            self.audio_processor.stop_monitoring()
            self.monitoring = False
            logger.info("Professional voice monitoring stopped")

    def _on_speech_detected(self):
        """Callback when speech is detected"""
        if self.playback_active:
            logger.info("Voice interruption detected during playback!")
            self.interrupt_detected = True
            # Stop current audio playback
            self._stop_current_playback()

    def _stop_current_playback(self):
        """Stop current audio playback"""
        try:
            # Send DTMF to stop Asterisk playback
            self.agi.command('EXEC SendDTMF *')
            logger.info("Playback stopped due to voice interruption")
        except Exception as e:
            logger.error(f"Failed to stop playback: {e}")

    def play_with_voice_interrupt(self, filename, max_play_time=15):
        """
        Play audio with professional voice interruption detection
        Returns: (success, was_interrupted, transcript)
        """
        if not self.monitoring:
            if not self.start_voice_monitoring():
                # Fallback to normal playback
                success = self.agi.stream_file(filename)
                return success, False, None

        # Reset detection state
        self.audio_processor.reset_detection()
        self.interrupt_detected = False
        self.playback_active = True

        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        logger.info(f"Playing with professional voice interruption: {filename}")

        # Start playback in separate thread
        playback_result = {'completed': False, 'success': False}

        def play_audio():
            try:
                result = self.agi.command(f'STREAM FILE {filename} "*"')
                playback_result['success'] = result and result.startswith('200')
                playback_result['completed'] = True
            except Exception as e:
                logger.error(f"Playback error: {e}")
                playback_result['completed'] = True

        playback_thread = threading.Thread(target=play_audio, daemon=True)
        playback_thread.start()

        # Monitor for interruption
        start_time = time.time()
        while time.time() - start_time < max_play_time:
            if self.interrupt_detected:
                # Voice interruption detected
                playback_thread.join(timeout=1)
                self.playback_active = False

                # Get transcript of interruption
                transcript = self._capture_interruption_transcript()

                logger.info(f"Voice interruption processed: {transcript[:50] if transcript else 'No transcript'}")
                return False, True, transcript

            if playback_result['completed']:
                # Playback finished normally
                self.playback_active = False
                logger.info("Playback completed without interruption")
                return playback_result['success'], False, None

            if not self.agi.connected:
                self.playback_active = False
                logger.info("Call disconnected during playback")
                return False, False, None

            time.sleep(0.1)  # Check every 100ms

        # Timeout reached
        self.playback_active = False
        playback_thread.join(timeout=1)
        return playback_result['success'], False, None

    def _capture_interruption_transcript(self):
        """Capture and transcribe voice interruption"""
        record_file = f"/var/spool/asterisk/monitor/voice_interrupt_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        logger.info("Capturing voice after interruption...")

        try:
            # Record user speech after interruption (shorter timeout for responsiveness)
            result = self.agi.command(f'RECORD FILE {record_file} wav "#" 8000 0 2')

            wav_file = f"{record_file}.wav"
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)
                logger.info(f"Voice capture: {file_size} bytes")

                if file_size > 1000:  # Reasonable speech threshold
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
            logger.error(f"Voice capture error: {e}")
            return "VOICE_DETECTED"


class EnhancedAGI:
    """
    Enhanced AGI with professional voice interruption using WebRTC VAD
    """

    def __init__(self, base_agi, asr_client):
        self.agi = base_agi
        self.asr = asr_client
        self.voice_interrupt = ProfessionalVoiceInterrupt(base_agi, asr_client)

    def __getattr__(self, name):
        """Delegate all other methods to base AGI"""
        return getattr(self.agi, name)

    def play_with_voice_interrupt(self, filename, asr_client=None):
        """
        Professional voice interruption using WebRTC VAD
        Returns: (success, interrupt_transcript)
        """
        try:
            success, interrupted, transcript = self.voice_interrupt.play_with_voice_interrupt(filename)

            if interrupted and transcript and transcript != "VOICE_DETECTED":
                logger.info(f"Professional voice interruption: {transcript[:50]}")
                return success, transcript
            elif interrupted:
                logger.info("Voice interruption detected (no clear transcript)")
                return success, "VOICE_DETECTED"
            else:
                logger.info(f"Playback completed normally: {success}")
                return success, None

        except Exception as e:
            logger.error(f"Professional voice interruption error: {e}")
            # Fallback to normal playback
            success = self.agi.stream_file(filename)
            return success, None

    def start_call_monitoring(self):
        """Start professional voice monitoring"""
        return self.voice_interrupt.start_voice_monitoring()

    def stop_call_monitoring(self):
        """Stop professional voice monitoring"""
        self.voice_interrupt.stop_voice_monitoring()

    def set_vad_aggressiveness(self, level=2):
        """
        Set VAD aggressiveness level
        0 = Least aggressive (more sensitive to speech)
        3 = Most aggressive (less sensitive, better for noisy environments)
        """
        self.voice_interrupt.vad_detector = WebRTCVoiceDetector(aggressiveness=level)
        logger.info(f"VAD aggressiveness set to: {level}")

    def get_interrupt_capability_description(self):
        """Describe the voice interruption capability to users"""
        return "You can interrupt me by speaking at any time - no need to press any keys"
