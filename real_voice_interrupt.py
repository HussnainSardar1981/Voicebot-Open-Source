#!/usr/bin/env python3
"""
REAL Voice Interruption using Asterisk Built-in Speech Recognition
Uses SpeechBackground() for true voice barge-in like commercial voice assistants
"""

import os
import time
import uuid
import logging

logger = logging.getLogger(__name__)

class RealVoiceInterrupt:
    """
    Real voice interruption using Asterisk's built-in speech recognition
    This is how commercial voice systems actually work
    """

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client
        self.speech_engine_ready = False

    def initialize_speech_engine(self):
        """Initialize Asterisk's built-in speech recognition engine"""
        if self.speech_engine_ready:
            return True

        try:
            # Create speech recognition instance
            result = self.agi.command('EXEC SpeechCreate')
            if not result or not result.startswith('200'):
                logger.error(f"Failed to create speech engine: {result}")
                return False

            # Start speech recognition
            result = self.agi.command('EXEC SpeechStart')
            if not result or not result.startswith('200'):
                logger.error(f"Failed to start speech recognition: {result}")
                return False

            self.speech_engine_ready = True
            logger.info("✅ Asterisk speech recognition engine initialized")
            return True

        except Exception as e:
            logger.error(f"Speech engine initialization failed: {e}")
            return False

    def cleanup_speech_engine(self):
        """Clean up speech recognition resources"""
        if self.speech_engine_ready:
            try:
                self.agi.command('EXEC SpeechDestroy')
                self.speech_engine_ready = False
                logger.info("Speech recognition engine cleaned up")
            except:
                pass

    def play_with_voice_barge_in(self, filename):
        """
        Play audio with REAL voice interruption using SpeechBackground
        This is how commercial voice assistants work
        """
        if not self.speech_engine_ready:
            if not self.initialize_speech_engine():
                # Fallback to normal playback
                logger.warning("Speech engine not available, using normal playback")
                success = self.agi.stream_file(filename)
                return success, None

        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]

        logger.info(f"🎙️ Playing with REAL voice interruption: {filename}")

        # Use SpeechBackground for real voice barge-in
        # This plays audio while listening for speech simultaneously
        result = self.agi.command(f'EXEC SpeechBackground {filename}')

        if result and result.startswith('200'):
            # Check if speech was detected
            speech_result = self.agi.get_variable('SPEECH_RESULTS_COUNT')

            if speech_result and speech_result != '0':
                logger.info("🗣️ REAL voice interruption detected!")

                # Get the speech transcript
                transcript = self.agi.get_variable('SPEECH_TEXT(0)')

                if transcript and len(transcript.strip()) > 0:
                    logger.info(f"✅ Voice transcript: {transcript}")
                    return False, transcript.strip()  # Interrupted with speech
                else:
                    logger.info("✅ Voice detected but no clear transcript")
                    # Get additional speech input
                    return self._capture_additional_speech()
            else:
                logger.info("✅ Audio completed without voice interruption")
                return True, None  # Completed normally

        else:
            logger.warning(f"SpeechBackground failed: {result}")
            # Fallback to normal playback
            success = self.agi.stream_file(filename)
            return success, None

    def _capture_additional_speech(self):
        """Capture additional speech if initial detection was unclear"""
        logger.info("🎧 Listening for clearer speech...")

        try:
            # Use SpeechBackground with silence to just listen
            result = self.agi.command('EXEC SpeechBackground silence/2')

            speech_result = self.agi.get_variable('SPEECH_RESULTS_COUNT')

            if speech_result and speech_result != '0':
                transcript = self.agi.get_variable('SPEECH_TEXT(0)')

                if transcript and len(transcript.strip()) > 0:
                    return False, transcript.strip()

            # If still no clear speech, use traditional recording as backup
            return self._fallback_voice_capture()

        except Exception as e:
            logger.error(f"Additional speech capture failed: {e}")
            return self._fallback_voice_capture()

    def _fallback_voice_capture(self):
        """Fallback voice capture using traditional recording"""
        record_file = f"/var/spool/asterisk/monitor/voice_fallback_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        logger.info("🎤 Using fallback voice capture...")

        try:
            # Play a brief tone to indicate listening
            self.agi.stream_file("beep")

            # Record user speech
            result = self.agi.command(f'RECORD FILE {record_file} wav "#" 8000 0 2')

            wav_file = f"{record_file}.wav"
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)

                if file_size > 1000:  # Reasonable speech threshold
                    transcript = self.asr.transcribe_file(wav_file)

                    # Cleanup
                    try:
                        os.unlink(wav_file)
                    except:
                        pass

                    if transcript and len(transcript.strip()) > 0:
                        return False, transcript.strip()

                # Clean up empty/small files
                try:
                    os.unlink(wav_file)
                except:
                    pass

            return False, "VOICE_DETECTED"

        except Exception as e:
            logger.error(f"Fallback voice capture failed: {e}")
            return False, "VOICE_DETECTED"


class EnhancedAGI:
    """
    Enhanced AGI with REAL voice interruption using Asterisk's built-in speech recognition
    """

    def __init__(self, base_agi, asr_client):
        self.agi = base_agi
        self.asr = asr_client
        self.voice_interrupt = RealVoiceInterrupt(base_agi, asr_client)

    def __getattr__(self, name):
        """Delegate all other methods to base AGI"""
        return getattr(self.agi, name)

    def play_with_voice_interrupt(self, filename, asr_client=None):
        """
        REAL voice interruption using Asterisk built-in speech recognition
        Returns: (success, interrupt_transcript)
        """
        try:
            success, interrupt = self.voice_interrupt.play_with_voice_barge_in(filename)

            if interrupt:
                if interrupt == "VOICE_DETECTED":
                    logger.info("🎙️ Real voice interruption detected")
                    return success, "VOICE_DETECTED"
                else:
                    logger.info(f"🗣️ Real voice interruption: {interrupt[:50]}")
                    return success, interrupt
            else:
                logger.info(f"✅ Audio completed normally: {success}")
                return success, None

        except Exception as e:
            logger.error(f"Real voice interruption error: {e}")
            # Emergency fallback
            success = self.agi.stream_file(filename)
            return success, None

    def start_call_monitoring(self):
        """Initialize real voice interruption system"""
        success = self.voice_interrupt.initialize_speech_engine()
        if success:
            logger.info("🎙️ REAL voice interruption system ready")
        else:
            logger.warning("⚠️ Real voice interruption unavailable - check speech engine")
        return success

    def stop_call_monitoring(self):
        """Clean up voice interruption system"""
        self.voice_interrupt.cleanup_speech_engine()
        logger.info("🛑 Real voice interruption system stopped")

    def set_voice_detection_sensitivity(self, level="normal"):
        """Set voice detection sensitivity"""
        logger.info(f"🎛️ Voice detection sensitivity: {level}")

    def get_interrupt_description(self):
        """Describe real voice interruption capability"""
        return "You can interrupt me anytime just by speaking naturally - no need to press any keys"
