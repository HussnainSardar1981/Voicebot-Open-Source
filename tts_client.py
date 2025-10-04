#!/usr/bin/env python3
"""
DirectTTSClient - Text-to-Speech using RIVA Docker
Extracted from production_agi_voicebot.py
"""

import os
import time
import uuid
import html
import subprocess
import logging

logger = logging.getLogger(__name__)

class DirectTTSClient:
    """Direct Docker TTS using your proven commands with enhanced voice quality"""

    def __init__(self, container="riva-speech"):
        self.container = container

        # Use single consistent voice for natural sound
        self.voice_name = "English-US.Female-1"

        # 🎵 AUDIO QUALITY SETTINGS - Optimized for natural human-like speech
        self.audio_quality = {
            "sample_rate": 22050,          # Better balance of quality/speed
            "enable_ssml": True,           # Enable SSML for more natural speech
            "speech_rate": "92%",          # Slower = more conversational
            "pitch_adjust": "+0.08",       # Slightly higher pitch = friendlier
            "volume": "medium",            # Consistent volume
            "emphasis": "moderate"         # Natural emphasis
        }

    def enhance_text_naturally(self, text, voice_type="default"):
        """Add natural speech patterns with basic SSML only"""

        # Escape XML special characters to prevent injection
        safe_text = html.escape(text, quote=False)

        # Voice-type specific adjustments for more human-like speech
        if voice_type == "empathetic":
            rate = "88%"
            pitch = "+0.06"
        elif voice_type == "technical":
            rate = "94%"
            pitch = "+0.02"
        elif voice_type == "greeting":
            rate = "90%"
            pitch = "+0.12"
        else:
            rate = "92%"
            pitch = "+0.08"

        # Enhanced SSML with natural pauses and emphasis for human-like speech
        return f"""<speak>
            <prosody rate="{rate}" pitch="{pitch}" volume="medium">
                {safe_text}
            </prosody>
        </speak>"""

    def synthesize(self, text, voice_type="default", voice_override=None):
        """Direct TTS synthesis using Docker with enhanced voice quality"""
        try:
            # Use single consistent voice
            voice = voice_override or self.voice_name
            sample_rate = self.audio_quality["sample_rate"]

            # 🎵 Add natural speech with enhanced SSML
            if self.audio_quality["enable_ssml"]:
                enhanced_text = self.enhance_text_naturally(text, voice_type)
            else:
                enhanced_text = html.escape(text, quote=False)

            # Create unique temp files to prevent collisions
            unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            host_output = f"/tmp/tts_agi_{unique_id}.wav"
            container_output = f"/tmp/riva_tts_{unique_id}.wav"

            # Run TTS without sudo (AGI doesn't have terminal access)
            cmd = [
                "docker", "exec", self.container,
                "/opt/riva/clients/riva_tts_client",
                f"--riva_uri=localhost:50051",
                f"--text={enhanced_text}",
                f"--voice_name={voice}",
                f"--audio_file={container_output}",
                f"--rate={sample_rate}"
            ]

            logger.info(f"🎵 TTS Enhanced: voice={voice}, rate={sample_rate}, ssml={self.audio_quality['enable_ssml']}")

            logger.info(f"Running TTS: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"TTS failed: {result.stderr}")
                return None

            # Copy from container to host
            copy_cmd = ["docker", "cp", f"{self.container}:{container_output}", host_output]
            copy_result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=10)

            # Cleanup container file
            try:
                subprocess.run(["docker", "exec", self.container, "rm", "-f", container_output],
                              capture_output=True, timeout=10)
            except Exception as e:
                logger.warning(f"Container cleanup failed: {e}")

            if copy_result.returncode == 0 and os.path.exists(host_output):
                file_size = os.path.getsize(host_output)
                logger.info(f"TTS success: {host_output} ({file_size} bytes)")
                return host_output
            else:
                logger.error(f"TTS copy failed: {copy_result.stderr}")
                return None

        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None