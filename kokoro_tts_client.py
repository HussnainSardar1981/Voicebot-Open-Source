#!/usr/bin/env python3
"""
KokoroTTSClient - Text-to-Speech using Kokoro (Open Source)
Drop-in replacement for DirectTTSClient (RIVA)
"""

import os
import time
import uuid
import html
import logging
import soundfile as sf
from kokoro_onnx import Kokoro
from config import TTS_CONFIG, USE_TTS

logger = logging.getLogger(__name__)

class KokoroTTSClient:
    """Kokoro TTS Client - Drop-in replacement for RIVA TTS"""

    def __init__(self, voice_name=None):
        try:
            # Use config values
            tts_config = TTS_CONFIG.get(USE_TTS, TTS_CONFIG["kokoro"])
            self.voice_name = voice_name or tts_config["voice"]

            self.kokoro = Kokoro()  # Initialize with default models

            # Available Kokoro voices (female focus for consistency)
            self.available_voices = {
                "af_sarah": "af_sarah",      # Default - clear female voice
                "af_bella": "af_bella",      # Warm female voice
                "af_jessica": "af_jessica",  # Professional female voice
                "af_nova": "af_nova",        # Energetic female voice
                "af_sky": "af_sky"           # Soft female voice
            }

            # 🎵 AUDIO QUALITY SETTINGS - Use config values
            self.audio_quality = {
                "sample_rate": tts_config["sample_rate"],               # Kokoro native sample rate from config
                "target_sample_rate": tts_config["target_sample_rate"], # Asterisk compatibility from config
                "speech_speed": 1.0,                                    # Normal speed (adjustable per voice_type)
                "language": "en-us"                                     # English US
            }

            logger.info(f"Kokoro TTS Client initialized with voice: {self.voice_name} (from config: USE_TTS={USE_TTS})")

        except Exception as e:
            logger.error(f"Failed to initialize Kokoro TTS: {e}")
            raise

    def _get_voice_speed(self, voice_type):
        """Get speech speed based on voice type (matching RIVA's voice type system)"""
        speed_map = {
            "empathetic": 0.88,    # Slower = more empathetic
            "technical": 0.94,     # Slightly slower for clarity
            "greeting": 0.90,      # Warm greeting pace
            "default": 0.92        # Slightly slower than normal for naturalness
        }
        return speed_map.get(voice_type, 0.92)

    def _enhance_text_for_speech(self, text, voice_type="default"):
        """Enhance text for more natural speech (similar to RIVA's SSML enhancement)"""
        # Escape any problematic characters
        safe_text = html.escape(text, quote=False)

        # Basic text normalization for better TTS
        safe_text = safe_text.replace("&", "and")
        safe_text = safe_text.replace("%", " percent")
        safe_text = safe_text.replace("@", " at ")
        safe_text = safe_text.replace("#", " number ")

        # Add natural pauses for empathetic responses
        if voice_type == "empathetic":
            # Add slight pauses after empathetic words
            empathetic_words = ["sorry", "understand", "apologize", "help"]
            for word in empathetic_words:
                safe_text = safe_text.replace(word, f"{word},")

        return safe_text

    def synthesize(self, text, voice_type="default", voice_override=None):
        """
        SAME INTERFACE as your existing RIVA TTS client
        Returns path to generated WAV file compatible with Asterisk
        """
        try:
            # Use voice override or default voice
            voice = voice_override or self.voice_name

            # Ensure voice is available
            if voice not in self.available_voices:
                logger.warning(f"Voice '{voice}' not available, using default: {self.voice_name}")
                voice = self.voice_name

            # Get speed based on voice type (matching RIVA's voice type system)
            speed = self._get_voice_speed(voice_type)

            # Enhance text for natural speech
            enhanced_text = self._enhance_text_for_speech(text, voice_type)

            # Generate unique output filename
            unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            temp_output = f"/tmp/kokoro_temp_{unique_id}.wav"
            final_output = f"/tmp/kokoro_tts_{unique_id}.wav"

            logger.info(f"🎵 Kokoro TTS: voice={voice}, speed={speed}, type={voice_type}")
            logger.info(f"Synthesizing: '{text[:50]}{'...' if len(text) > 50 else ''}'")

            # Generate audio using Kokoro
            samples, sample_rate = self.kokoro.create(
                text=enhanced_text,
                voice=voice,
                speed=speed,
                lang=self.audio_quality["language"]
            )

            # Save at native sample rate first
            sf.write(temp_output, samples, sample_rate, subtype='PCM_16')

            # Convert to Asterisk-compatible format (8kHz mono)
            # Using sox for format conversion (same as your existing audio pipeline)
            import subprocess
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
        return list(self.available_voices.keys())