#!/usr/bin/env python3
"""
Production-Grade Audio Recorder using Inbound-Only Recording
Prevents voice hallucinations by recording only user speech (not bot TTS)
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
        Production-grade user input recording using RECORD FILE (inbound only)
        Records only user speech - prevents bot voice hallucinations
        """
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/user_{unique_id}"
        wav_file = f"{record_file}.wav"

        logger.info(f"Starting inbound-only recording: {record_file}")

        try:
            # Use RECORD FILE for inbound-only recording (no bot voice pickup)
            # Syntax: RECORD FILE filename format escape_digits timeout offset_samples beep
            record_cmd = f'RECORD FILE {record_file} wav "#" {timeout * 1000} 0 0'

            # Start recording with intelligent monitoring
            self.agi.command(record_cmd)
            logger.info(f"Inbound recording started, intelligent monitoring for {timeout}s...")

            # RECORD FILE is blocking - it handles the timeout automatically
            # Recording completes when user stops speaking or timeout is reached

            # Small delay to ensure file is fully written
            time.sleep(0.1)

            # Check final recording
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)
                logger.info(f"Final recording: {file_size} bytes")

                if file_size > 300:  # Lower threshold for better detection
                    # Transcribe with ASR
                    transcript = self.asr.transcribe_file(wav_file)

                    # Cleanup
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
            logger.error(f"Inbound recording error: {e}")
            # Ensure cleanup
            try:
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
            except:
                pass
            return None

    def record_with_voice_interrupt(self, filename, timeout=3):
        """
        Record with voice interruption capability using inbound-only recording
        Used for detecting user speech during TTS playback
        """
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/interrupt_{unique_id}"
        wav_file = f"{record_file}.wav"

        logger.info(f"Starting interrupt detection: {record_file}")

        try:
            # Use RECORD FILE for inbound-only interrupt detection
            record_cmd = f'RECORD FILE {record_file} wav "#" {timeout * 1000} 0 0'

            # This is a short recording just to detect interruptions
            result = self.agi.command(record_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start interrupt recording: {result}")
                return False, None

            # RECORD FILE is blocking and completes automatically
            # Check if voice was detected
            if os.path.exists(wav_file):
                file_size = os.path.getsize(wav_file)
                if file_size > 200:  # Voice detected - lower threshold
                    logger.info(f"Voice interrupt detected: {file_size} bytes")

                    # Transcribe interruption
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
                else:
                    # File too small - no significant voice detected
                    try:
                        os.unlink(wav_file)
                    except:
                        pass
                    return False, None
            else:
                # No file created
                return False, None

        except Exception as e:
            logger.error(f"Interrupt recording error: {e}")
            # Cleanup
            try:
                if os.path.exists(wav_file):
                    os.unlink(wav_file)
            except:
                pass
            return False, None
