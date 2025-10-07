#!/usr/bin/env python3
"""
KokoroTTSClient - Professional Text-to-Speech using Kokoro
GPU-accelerated natural voice synthesis for professional voicebot applications
"""

import os
import time
import uuid
import html
import logging
import soundfile as sf
import subprocess
from kokoro import KPipeline
from config import KOKORO_CONFIG

logger = logging.getLogger(__name__)

class KokoroTTSClient:
    """Professional Kokoro TTS Client - Natural Voice Synthesis"""

    def __init__(self):
        try:
            # Use pure Kokoro configuration
            self.voice_name = KOKORO_CONFIG["voice"]
            self.sample_rate = KOKORO_CONFIG["sample_rate"]
            self.target_sample_rate = KOKORO_CONFIG["target_sample_rate"]
            self.language = KOKORO_CONFIG["language"]
            self.speed = KOKORO_CONFIG["speed"]

            logger.info("Initializing professional Kokoro TTS pipeline...")

            # Check for GPU availability
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"GPU detected for TTS: {gpu_name}")
                # Initialize with GPU support
                self.pipeline = KPipeline(lang_code='a', device=self.device)
            else:
                logger.info("Using CPU for TTS")
                self.pipeline = KPipeline(lang_code='a')  # 'a' for American English

            # Map config voice names to Kokoro voices
            self.voice_mapping = {
                "af_sarah": "af_sarah",
                "af_bella": "af_bella",    # More natural sounding
                "af_jessica": "af_jessica", # Professional tone
                "af_nova": "af_nova",      # Clear pronunciation
                "af_sky": "af_sky",        # Warm voice
                "af_heart": "af_heart",    # Most human-like
                "af_alloy": "af_alloy"
            }

            # Default to af_heart (most human-like) if voice not mapped
            self.kokoro_voice = self.voice_mapping.get(self.voice_name, "af_heart")

            # Audio quality settings for professional output
            self.audio_quality = {
                "native_sample_rate": self.sample_rate,          # Kokoro native (24kHz)
                "target_sample_rate": self.target_sample_rate,   # Asterisk compatibility (8kHz)
                "speech_speed": self.speed,                      # Natural speed
                "language": self.language                        # English
            }

            logger.info(f"✅ Kokoro TTS ready: voice={self.kokoro_voice}, GPU={torch.cuda.is_available()}")

        except Exception as e:
            logger.error(f"Failed to initialize Kokoro TTS: {e}")
            raise

    def _get_voice_speed(self, voice_type):
        """Get speech speed based on voice type for natural conversation flow"""
        speed_map = {
            "empathetic": 0.88,    # Slower = more empathetic
            "technical": 0.94,     # Slightly slower for clarity
            "greeting": 0.90,      # Warm greeting pace
            "default": 0.92        # Slightly slower than normal for naturalness
        }
        return speed_map.get(voice_type, 0.92)

    def _enhance_text_for_speech(self, text, voice_type="default"):
        """Enhance text for more natural speech with pronunciation fixes (safe & minimal)"""
        # Escape any problematic characters (keeps punctuation intact)
        safe_text = html.escape(text, quote=False)

        # --- Acronym spell-outs (unchanged) ---
        pronunciation_fixes = {
            "AGI": "A-G-I",
            "API": "A-P-I",
            "VoIP": "Voice over I-P",
            "SIP": "S-I-P",
        }
        for original, phonetic in pronunciation_fixes.items():
            safe_text = safe_text.replace(original, phonetic)

        # --- Company name: Netovo (natural, not letter-by-letter) ---
        # Works in sentences and before punctuation (.,!?)
        for v in ("NETOVO", "Netovo", "netovo"):
            safe_text = safe_text.replace(v, "Neh-TOH-voh")

        # Basic text normalization
        safe_text = safe_text.replace("&", " and ")
        safe_text = safe_text.replace("%", " percent ")
        safe_text = safe_text.replace("@", " at ")
        safe_text = safe_text.replace("#", " number ")

        # Common tech pronunciations
        safe_text = safe_text.replace("24/7", "twenty-four seven")
        safe_text = safe_text.replace("3CX", "three C X")

        # Light, optional pausing based on voice type (kept minimal to avoid regressions)
        if voice_type == "empathetic":
            for w in ("sorry", "understand", "apologize", "help"):
                # add a gentle comma after the word if present
                safe_text = safe_text.replace(f" {w} ", f" {w}, ")

        # NOTE: we do NOT force any special handling like "NETOVO." → "…"
        # to avoid re-introducing the letter-by-letter spelling.

        return safe_text


    def synthesize(self, text, voice_type="default", voice_override=None):
        """
        Professional text-to-speech synthesis with natural voice
        Returns path to generated WAV file compatible with Asterisk
        """
        try:
            # Use voice override or default voice
            voice = voice_override or self.kokoro_voice
            voice = self.voice_mapping.get(voice, "af_heart")

            # Enhance text for natural speech
            enhanced_text = self._enhance_text_for_speech(text, voice_type)

            # Generate unique output filename
            unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            temp_output = f"/tmp/kokoro_temp_{unique_id}.wav"
            final_output = f"/tmp/kokoro_tts_{unique_id}.wav"

            logger.info(f"🎵 Kokoro TTS: voice={voice}, type={voice_type}")
            logger.info(f"Synthesizing: '{text[:50]}{'...' if len(text) > 50 else ''}'")

            # Generate audio using Kokoro
            generator = self.pipeline(enhanced_text, voice=voice)

            # Kokoro yields chunks, we need to collect them
            audio_chunks = []
            for i, (gs, ps, audio_chunk) in enumerate(generator):
                audio_chunks.append(audio_chunk)
                if i == 0:  # First chunk
                    logger.debug(f"Kokoro TTS generating audio chunks...")

            # Combine all audio chunks
            if audio_chunks:
                import numpy as np
                full_audio = np.concatenate(audio_chunks)

                # Save at native sample rate first (24kHz)
                sf.write(temp_output, full_audio, self.audio_quality["native_sample_rate"], subtype='PCM_16')

                logger.info(f"Generated audio: {len(full_audio)} samples at {self.audio_quality['native_sample_rate']}Hz")
            else:
                logger.error("No audio generated from Kokoro TTS")
                return None

            # Convert to Asterisk-compatible format (8kHz mono) using sox
            sox_cmd = [
                'sox', temp_output,
                '-r', str(self.audio_quality["target_sample_rate"]),  # 8kHz for Asterisk
                '-c', '1',        # Mono
                '-b', '16',       # 16-bit
                '-e', 'signed-integer',  # PCM
                final_output
            ]

            convert_result = subprocess.run(sox_cmd, capture_output=True, text=True, timeout=10)

            # Cleanup temp file
            try:
                os.unlink(temp_output)
            except:
                pass

            if convert_result.returncode == 0 and os.path.exists(final_output):
                file_size = os.path.getsize(final_output)
                logger.info(f"Kokoro TTS success: {final_output} ({file_size} bytes)")
                return final_output
            else:
                logger.error(f"Audio conversion failed: {convert_result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Kokoro TTS error: {e}")
            # Cleanup on error
            try:
                if 'temp_output' in locals() and os.path.exists(temp_output):
                    os.unlink(temp_output)
                if 'final_output' in locals() and os.path.exists(final_output):
                    os.unlink(final_output)
            except:
                pass
            return None

    def list_voices(self):
        """List available voices"""
        return list(self.voice_mapping.keys())
    
