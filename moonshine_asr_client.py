#!/usr/bin/env python3
"""
MoonshineASRClient - Speech Recognition using Moonshine (Open Source)
Drop-in replacement for DirectASRClient (RIVA)
"""

import os
import time
import uuid
import subprocess
import logging
import moonshine_onnx
from config import ASR_CONFIG, USE_ASR

logger = logging.getLogger(__name__)

class MoonshineASRClient:
    """Moonshine ASR Client - Drop-in replacement for RIVA ASR"""

    def __init__(self, model=None):
        # Use config values
        asr_config = ASR_CONFIG.get(USE_ASR, ASR_CONFIG["moonshine"])
        self.model = model or asr_config["model"]
        self.sample_rate = asr_config["sample_rate"]

        logger.info(f"Moonshine ASR Client initialized with model: {self.model} (from config: USE_ASR={USE_ASR})")

    def transcribe_file(self, audio_file):
        """
        SAME INTERFACE as your existing RIVA ASR client
        Returns transcribed text string
        """
        try:
            logger.info(f"Moonshine ASR transcribing: {audio_file}")

            # Create unique temp file for format conversion
            unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            converted_path = f"/tmp/moonshine_{unique_id}.wav"

            # Check original file details first
            if os.path.exists(audio_file):
                orig_size = os.path.getsize(audio_file)
                logger.info(f"Original audio file: {orig_size} bytes")

                # Get file info
                try:
                    import subprocess
                    file_cmd = subprocess.run(['file', audio_file], capture_output=True, text=True)
                    logger.info(f"Original file type: {file_cmd.stdout.strip()}")
                except:
                    pass
            else:
                logger.error(f"Original audio file not found: {audio_file}")
                return ""

            # Convert audio to Moonshine-compatible format (16kHz, mono, 16-bit)
            sox_cmd = [
                'sox', audio_file,
                '-r', str(self.sample_rate),  # 16kHz (Moonshine requirement)
                '-c', '1',                    # Mono
                '-b', '16',                   # 16-bit
                '-e', 'signed-integer',       # PCM
                converted_path
            ]

            logger.info(f"Converting audio for Moonshine: {' '.join(sox_cmd)}")
            convert_result = subprocess.run(sox_cmd, capture_output=True, text=True, timeout=10)

            if convert_result.returncode != 0:
                logger.error(f"Audio conversion failed: {convert_result.stderr}")
                logger.error(f"Sox stdout: {convert_result.stdout}")
                return ""

            # Check converted file size and details
            if os.path.exists(converted_path):
                file_size = os.path.getsize(converted_path)
                logger.info(f"Converted audio file: {file_size} bytes")

                # Get converted file info
                try:
                    file_cmd = subprocess.run(['file', converted_path], capture_output=True, text=True)
                    logger.info(f"Converted file type: {file_cmd.stdout.strip()}")
                except:
                    pass

                if file_size < 1000:
                    logger.error("Converted file too small")
                    return ""
            else:
                logger.error("Converted file not created")
                return ""

            # Transcribe with Moonshine
            logger.info(f"Running Moonshine ASR with model: {self.model}")
            try:
                transcription = moonshine_onnx.transcribe(converted_path, self.model)
                logger.info(f"Moonshine raw output: {transcription}")
            except Exception as e:
                logger.error(f"Moonshine transcription failed: {e}")
                return ""

            # Cleanup temp file
            try:
                os.unlink(converted_path)
            except Exception as e:
                logger.debug(f"Temp file cleanup failed: {e}")

            # Process transcription result
            if transcription and len(transcription) > 0:
                # moonshine_onnx.transcribe returns a list of strings
                if isinstance(transcription, list):
                    if len(transcription) > 0 and transcription[0]:
                        cleaned_text = self._clean_transcript(transcription[0])
                    else:
                        logger.warning("Moonshine returned empty transcription list")
                        return ""
                else:
                    # In case it returns a single string
                    cleaned_text = self._clean_transcript(str(transcription))

                if cleaned_text:
                    logger.info(f"Moonshine ASR result: '{cleaned_text}'")
                    return cleaned_text
                else:
                    logger.warning("Transcript cleaning resulted in empty text")
                    return ""
            else:
                logger.warning("Moonshine returned no transcription")
                return ""

        except Exception as e:
            logger.error(f"Moonshine ASR error: {e}")
            # Cleanup on error
            try:
                if 'converted_path' in locals() and os.path.exists(converted_path):
                    os.unlink(converted_path)
            except:
                pass
            return ""

    def _clean_transcript(self, text):
        """Clean and normalize transcription output (same logic as RIVA client)"""
        if not text:
            return ""

        # Basic cleaning
        cleaned = text.strip()
        cleaned = cleaned.replace("  ", " ")  # Remove double spaces

        # Remove quotes if they wrap the entire text
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]

        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        return cleaned
