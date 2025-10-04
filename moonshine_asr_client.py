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

logger = logging.getLogger(__name__)

class MoonshineASRClient:
    """Moonshine ASR Client - Drop-in replacement for RIVA ASR"""

    def __init__(self, model="moonshine/base"):
        self.model = model  # Use 'moonshine/base' for better accuracy than 'tiny'
        self.sample_rate = 16000  # Moonshine requirement

        logger.info(f"Moonshine ASR Client initialized with model: {model}")

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

            # Convert audio to Moonshine-compatible format (16kHz, mono, 16-bit)
            # Same conversion as RIVA for consistency
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
                return ""

            # Check converted file size
            if os.path.exists(converted_path):
                file_size = os.path.getsize(converted_path)
                logger.info(f"Converted audio file: {file_size} bytes")
                if file_size < 1000:
                    logger.error("Converted file too small")
                    return ""
            else:
                logger.error("Converted file not created")
                return ""

            # Transcribe with Moonshine
            logger.info(f"Running Moonshine ASR with model: {self.model}")
            transcription = moonshine_onnx.transcribe(converted_path, self.model)

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