#!/usr/bin/env python3
"""
Production-Grade Audio Recorder using MixMonitor
Industry standard for VoIP call recording - designed for production reliability
"""

import os
import time
import uuid
import logging

logger = logging.getLogger(__name__)

class ProductionCallRecorder:
    """Production-grade call recorder using MixMonitor (industry standard)"""

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client

    def get_user_input_with_mixmonitor(self, timeout=10):
        """
        Production-grade user input recording using MixMonitor with smart silence detection
        Real-time monitoring with proper voice activity detection
        """
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/mix_{unique_id}"
        wav_file = f"{record_file}.wav"  # Single file with inbound-only recording

        logger.info(f"Starting MixMonitor recording: {record_file}")

        try:
            # Start MixMonitor with inbound-only direction control (Option A)
            # 'r(in)' parameter = record inbound only (user voice), prevents bot voice hallucinations
            mixmonitor_cmd = f'EXEC MixMonitor {record_file}.wav,b,r(in)'
            result = self.agi.command(mixmonitor_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start MixMonitor: {result}")
                return None

            logger.info(f"MixMonitor started, waiting {timeout}s for user input...")

            # Wait for user to speak with proper silence detection
            start_time = time.time()
            speech_detected = False
            speech_start_time = None
            last_file_size = 0
            silence_start = None
            silence_threshold = 1.0  # 1 second of silence to end recording
            min_speech_duration = 1.5  # Must speak for 1.5s before silence detection starts
            min_speech_size = 400    # Minimum audio to consider speech started (lowered)
            growth_threshold = 15    # Minimum growth to consider ongoing speech (much more sensitive)

            while time.time() - start_time < timeout:
                if not self.agi.connected:
                    logger.info("Call disconnected during recording")
                    break

                # Check if file exists and has content
                if os.path.exists(wav_file):
                    file_size = os.path.getsize(wav_file)

                    # Phase 1: Detect start of speech
                    if not speech_detected and file_size > min_speech_size:
                        speech_detected = True
                        speech_start_time = time.time()
                        last_file_size = file_size
                        logger.info(f"Speech started: {file_size} bytes")

                    # Phase 2: Monitor ongoing speech and detect silence
                    elif speech_detected:
                        size_growth = file_size - last_file_size
                        speech_duration = time.time() - speech_start_time

                        if size_growth > growth_threshold:
                            # File still growing - user still speaking
                            silence_start = None  # Reset silence timer
                            last_file_size = file_size
                            logger.debug(f"Speech continues: {file_size} bytes (+{size_growth})")
                        else:
                            # File not growing much - potential silence
                            # Only start silence detection after minimum speech duration
                            if speech_duration >= min_speech_duration:
                                if silence_start is None:
                                    silence_start = time.time()
                                    logger.debug("Silence period started (after minimum speech duration)")
                                elif time.time() - silence_start > silence_threshold:
                                    logger.info(f"Silence detected after {file_size} bytes - ending recording")
                                    break
                            else:
                                # Still in minimum speech period, don't trigger silence detection
                                last_file_size = file_size
                                logger.debug(f"In minimum speech period: {speech_duration:.1f}s of {min_speech_duration}s")

                time.sleep(0.1)  # Check every 100ms for better responsiveness

            # Stop MixMonitor
            stop_result = self.agi.command('EXEC StopMixMonitor')
            logger.info(f"MixMonitor stopped: {stop_result}")

            # Small delay to ensure file is written
            time.sleep(0.2)

            # Check final recording
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)
                logger.info(f"Final recording: {file_size} bytes")

                if file_size > 300:  # Lower threshold for better detection
                    # Transcribe with ASR
                    transcript = self.asr.transcribe_file(wav_file)

                    # Cleanup recording file
                    try:
                        os.unlink(wav_file)
                    except Exception as e:
                        logger.debug(f"Cleanup failed: {e}")

                    return transcript.strip() if transcript else None
                else:
                    logger.info(f"Recording too small: {file_size} bytes")
                    # Cleanup small/empty file
                    try:
                        os.unlink(wav_file)
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
                self.agi.command('EXEC StopMixMonitor')
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
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
        wav_file = f"{record_file}.wav"  # Single file with inbound-only recording

        logger.info(f"Starting interrupt detection: {record_file}")

        try:
            # Start MixMonitor for interrupt detection (inbound-only)
            mixmonitor_cmd = f'EXEC MixMonitor {record_file}.wav,b,r(in)'
            result = self.agi.command(mixmonitor_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start interrupt MixMonitor: {result}")
                return False, None

            # Wait for timeout or voice detection
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.agi.connected:
                    break

                # Check for voice activity
                if os.path.exists(wav_file):
                    file_size = os.path.getsize(wav_file)
                    if file_size > 200:  # Voice detected - lower threshold
                        logger.info(f"Voice interrupt detected: {file_size} bytes")

                        # Stop recording
                        self.agi.command('EXEC StopMixMonitor')
                        time.sleep(0.1)

                        # Transcribe interruption
                        if os.path.exists(wav_file):
                            transcript = self.asr.transcribe_file(wav_file)

                            # Cleanup
                            try:
                                os.unlink(wav_file)
                            except:
                                pass

                            if transcript and len(transcript.strip()) > 1:
                                return True, transcript.strip()
                            else:
                                return True, "VOICE_DETECTED"

                time.sleep(0.1)  # Check every 100ms for fast response

            # No interruption detected
            self.agi.command('EXEC StopMixMonitor')

            # Cleanup
            try:
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
            except:
                pass

            return False, None

        except Exception as e:
            logger.error(f"Interrupt recording error: {e}")
            # Cleanup
            try:
                self.agi.command('EXEC StopMixMonitor')
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
            except:
                pass
            return False, None
