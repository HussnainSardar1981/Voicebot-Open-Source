#!/usr/bin/env python3
"""
Production-Grade Audio Recorder using MixMonitor
Industry standard for VoIP call recording - designed for production reliability
"""

import os
import time
import uuid
import logging
import webrtcvad

logger = logging.getLogger(__name__)

class ProductionCallRecorder:
    """Production-grade call recorder using MixMonitor (industry standard)"""

    def __init__(self, agi, asr_client):
        self.agi = agi
        self.asr = asr_client
        self.vad = webrtcvad.Vad(3)  # Aggressive mode for best speech detection

    def get_user_input_with_mixmonitor(self, timeout=10):
        """
        Production-grade user input recording using MixMonitor
        Records actual call audio stream (RTP) - not hardware devices
        """
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:4]}"
        record_file = f"/var/spool/asterisk/monitor/mix_{unique_id}"
        wav_file = f"{record_file}.wav"

        logger.info(f"Starting MixMonitor recording: {record_file}")

        try:
            # Start MixMonitor - records call audio stream (both directions)
            mixmonitor_cmd = f'EXEC MixMonitor {record_file}.wav'
            result = self.agi.command(mixmonitor_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start MixMonitor: {result}")
                return None

            logger.info(f"MixMonitor started, waiting {timeout}s for user input...")

            max_utterance_sec = 30.0
            eos_silence_ms = 1800
            poll_ms = 30  # 30ms frames for VAD
            frame_bytes = 480  # 30ms at 16kHz, 16-bit mono

            record_start = time.time()
            last_speech_time = record_start
            file_pos = 0

            while True:
                if not self.agi.connected:
                    logger.info("Call disconnected during recording")
                    break

                now = time.time()
                if now - record_start > max_utterance_sec:
                    logger.info("Max utterance cap reached")
                    break

                if os.path.exists(wav_file):
                    with open(wav_file, 'rb') as f:
                        f.seek(file_pos)
                        chunk = f.read(frame_bytes)
                        while len(chunk) == frame_bytes:
                            if self.vad.is_speech(chunk, 16000):
                                last_speech_time = now
                            file_pos += frame_bytes
                            chunk = f.read(frame_bytes)

                # End if enough silence since last speech
                if (now - last_speech_time) * 1000.0 >= eos_silence_ms:
                    logger.info("EOS silence reached; stopping recording")
                    break

                time.sleep(poll_ms / 1000.0)

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
        wav_file = f"{record_file}.wav"

        logger.info(f"Starting interrupt detection: {record_file}")

        try:
            # Start MixMonitor for interrupt detection (both directions)
            mixmonitor_cmd = f'EXEC MixMonitor {record_file}.wav'
            result = self.agi.command(mixmonitor_cmd)

            if not result or not result.startswith('200'):
                logger.error(f"Failed to start interrupt MixMonitor: {result}")
                return False, None

            # Wait for timeout or voice detection
            start_time = time.time()
            frame_bytes = 480  # 30ms at 16kHz, 16-bit mono

            while time.time() - start_time < timeout:
                if not self.agi.connected:
                    break

                if os.path.exists(wav_file):
                    with open(wav_file, 'rb') as f:
                        f.seek(-frame_bytes, 2)
                        frame = f.read(frame_bytes)
                        if len(frame) == frame_bytes:
                            if self.vad.is_speech(frame, 16000):
                                logger.info("Voice interrupt detected")
                                self.agi.command('EXEC StopMixMonitor')
                                time.sleep(0.1)
                                transcript = self.asr.transcribe_file(wav_file)
                                os.unlink(wav_file)
                                return True, transcript.strip() if transcript else "VOICE_DETECTED"

                time.sleep(0.1)

            self.agi.command('EXEC StopMixMonitor')
            if os.path.exists(wav_file):
                os.unlink(wav_file)
            return False, None

        except Exception as e:
            logger.error(f"Interrupt recording error: {e}")
            self.agi.command('EXEC StopMixMonitor')
            if os.path.exists(wav_file):
                os.unlink(wav_file)
            return False, None
