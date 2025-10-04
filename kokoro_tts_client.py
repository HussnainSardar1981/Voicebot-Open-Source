#!/usr/bin/env python3
"""
KokoroTTSClient - Text-to-Speech using Kokoro (Official Package)
Drop-in replacement for DirectTTSClient (RIVA)
"""

import os
import time
import uuid
import html
import logging
import soundfile as sf
import subprocess
from kokoro import KPipeline
from config import TTS_CONFIG, USE_TTS

logger = logging.getLogger(__name__)

class KokoroTTSClient:
    """Kokoro TTS Client - Drop-in replacement for RIVA TTS"""

    def __init__(self, voice_name=None):
        try:
            # Use config values
            tts_config = TTS_CONFIG.get(USE_TTS, TTS_CONFIG["kokoro"])
            self.voice_name = voice_name or tts_config["voice"]

            # Initialize Kokoro pipeline with American English
            logger.info("Initializing Kokoro TTS pipeline...")
            self.pipeline = KPipeline(lang_code='a')  # 'a' for American English

            # Map config voice names to Kokoro voices
            self.voice_mapping = {
                "af_sarah": "af_sarah",
                "af_bella": "af_bella",
                "af_jessica": "af_jessica",
                "af_nova": "af_nova",
                "af_sky": "af_sky",
                "af_heart": "af_heart",  # Popular Kokoro voice
                "af_alloy": "af_alloy"
            }

            # Default to af_heart if voice not mapped
            self.kokoro_voice = self.voice_mapping.get(self.voice_name, "af_heart")

            # Audio quality settings from config
            self.audio_quality = {
                "native_sample_rate": 24000,                               # Kokoro outputs 24kHz
                "target_sample_rate": tts_config["target_sample_rate"],     # Asterisk compatibility (8kHz)
                "speech_speed": 1.0,                                        # Normal speed
                "language": "en-us"
            }

            logger.info(f"Kokoro TTS Client initialized with voice: {self.kokoro_voice} (from config: USE_TTS={USE_TTS})")

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
        """Enhance text for more natural speech"""
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
                if word in safe_text.lower():
                    safe_text = safe_text.replace(word, f"{word},")

        return safe_text

    def synthesize(self, text, voice_type="default", voice_override=None):
        """
        SAME INTERFACE as your existing RIVA TTS client
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
    
