#!/usr/bin/env python3
"""
WhisperASRClient - Professional Speech Recognition using OpenAI Whisper
GPU-accelerated speech-to-text for professional voicebot applications
"""

import os
import time
import uuid
import subprocess
import logging
import whisper
import torch
from config import WHISPER_CONFIG

logger = logging.getLogger(__name__)

class WhisperASRClient:
    """Whisper ASR Client - Production-ready speech recognition"""

    def __init__(self):
        try:
            # Use pure Whisper configuration
            self.model_size = WHISPER_CONFIG["model"]
            self.sample_rate = WHISPER_CONFIG["sample_rate"]
            self.language = WHISPER_CONFIG["language"]

            logger.info(f"Loading Whisper {self.model_size} model for professional ASR...")

            # Load Whisper model (auto-downloads if needed)
            self.model = whisper.load_model(self.model_size)

            # Check if CUDA is available for faster processing
            self.device = WHISPER_CONFIG.get("device", "cuda" if torch.cuda.is_available() else "cpu")

            # Get GPU info if available
            if torch.cuda.is_available() and self.device == "cuda":
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"GPU detected: {gpu_name} ({gpu_memory:.1f}GB)")

                # Move model to GPU for faster inference
                if hasattr(self.model, 'to'):
                    self.model = self.model.to(self.device)
            else:
                logger.warning("CUDA not available - using CPU (slower)")

            logger.info(f"✅ Whisper ASR ready: model={self.model_size}, device={self.device}")

        except Exception as e:
            logger.error(f"Failed to initialize Whisper ASR: {e}")
            raise

    def _validate_audio_file(self, audio_file):
        """Validate audio file exists and has content"""
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return False

        file_size = os.path.getsize(audio_file)
        logger.info(f"Audio file: {audio_file} ({file_size} bytes)")

        if file_size < 100:  # Very small files are likely empty/corrupted
            logger.error(f"Audio file too small: {file_size} bytes")
            return False

        return True

    def _convert_audio_for_whisper(self, audio_file):
        """Convert audio to Whisper-compatible format if needed"""
        try:
            # Create unique temp file
            unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            converted_path = f"/tmp/whisper_{unique_id}.wav"

            # Get original file info
            try:
                file_cmd = subprocess.run(['file', audio_file], capture_output=True, text=True, timeout=5)
                logger.info(f"Original file type: {file_cmd.stdout.strip()}")
            except Exception as e:
                logger.debug(f"Could not get file info: {e}")

            # Convert to Whisper-preferred format (16kHz mono)
            sox_cmd = [
                'sox', audio_file,
                '-r', str(self.sample_rate),  # 16kHz sample rate
                '-c', '1',                    # Mono
                '-b', '16',                   # 16-bit
                '-e', 'signed-integer',       # PCM
                converted_path
            ]

            logger.info(f"Converting audio: {' '.join(sox_cmd)}")
            convert_result = subprocess.run(sox_cmd, capture_output=True, text=True, timeout=15)

            if convert_result.returncode != 0:
                logger.error(f"Audio conversion failed: {convert_result.stderr}")
                logger.error(f"Sox stdout: {convert_result.stdout}")
                return None

            # Validate converted file
            if not self._validate_audio_file(converted_path):
                try:
                    os.unlink(converted_path)
                except:
                    pass
                return None

            logger.info(f"Audio converted successfully: {converted_path}")
            return converted_path

        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return None

    def transcribe_file(self, audio_file):
        """
        Professional speech-to-text transcription
        Returns transcribed text string with high accuracy
        """
        try:
            logger.info(f"Whisper ASR transcribing: {audio_file}")

            # Validate original file first
            if not self._validate_audio_file(audio_file):
                return ""

            # Convert audio for optimal Whisper processing
            converted_file = self._convert_audio_for_whisper(audio_file)
            if not converted_file:
                logger.error("Audio conversion failed")
                return ""

            # Use converted file for transcription
            audio_to_process = converted_file

            logger.info(f"Running Whisper transcription on: {audio_to_process}")

            # Transcribe with Whisper - optimized for GPU
            # GPU optimization options:
            # - fp16=True for H100 GPU (faster inference)
            # - language="en" for English-only processing (faster)
            # - task="transcribe" for transcription (not translation)
            # - beam_size=5 for better accuracy on GPU
            use_fp16 = torch.cuda.is_available() and self.device == "cuda"

            result = self.model.transcribe(
                audio_to_process,
                fp16=use_fp16,        # Use FP16 on GPU for speed
                language="en",        # English only (faster)
                task="transcribe",    # Transcription mode
                verbose=False,        # Less verbose output
                beam_size=5,          # Better accuracy (GPU can handle it)
                best_of=5,           # Multiple candidates for better results
                temperature=0.0       # Deterministic output
            )

            # Cleanup temp file immediately
            try:
                if converted_file and os.path.exists(converted_file):
                    os.unlink(converted_file)
            except Exception as e:
                logger.debug(f"Temp file cleanup failed: {e}")

            # Extract and clean transcript
            transcript = result.get("text", "").strip()

            if transcript:
                # Clean the transcript
                cleaned_transcript = self._clean_transcript(transcript)
                if cleaned_transcript:
                    logger.info(f"Whisper ASR result: '{cleaned_transcript}'")
                    return cleaned_transcript
                else:
                    logger.warning("Transcript cleaning resulted in empty text")
                    return ""
            else:
                logger.warning("Whisper returned no transcription")
                return ""

        except Exception as e:
            logger.error(f"Whisper ASR error: {e}")
            # Ensure cleanup on error
            try:
                if 'converted_file' in locals() and converted_file and os.path.exists(converted_file):
                    os.unlink(converted_file)
            except:
                pass
            return ""

    def _clean_transcript(self, text):
        """Clean and normalize transcription output"""
        if not text:
            return ""

        # Remove extra whitespace
        cleaned = text.strip()
        cleaned = " ".join(cleaned.split())  # Normalize whitespace

        # Remove common Whisper artifacts
        artifacts = [
            "Thank you for watching!",
            "Thanks for watching!",
            "Subscribe to my channel!",
            "Please like and subscribe",
            "♪",  # Music notes
            "♫",
            "[Music]",
            "[music]",
            "[MUSIC]"
        ]

        for artifact in artifacts:
            cleaned = cleaned.replace(artifact, "").strip()

        # Remove quotes if they wrap the entire text
        if len(cleaned) > 2:
            if (cleaned.startswith('"') and cleaned.endswith('"')) or \
               (cleaned.startswith("'") and cleaned.endswith("'")):
                cleaned = cleaned[1:-1].strip()

        # Capitalize first letter if needed
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]

        # Remove trailing periods if sentence seems incomplete
        if cleaned.endswith('.') and len(cleaned.split()) < 3:
            cleaned = cleaned[:-1]

        return cleaned

    def get_model_info(self):
        """Get information about the loaded model"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "sample_rate": self.sample_rate
        }