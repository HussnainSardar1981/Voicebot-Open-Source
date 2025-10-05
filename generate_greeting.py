#!/usr/bin/env python3
"""
Pre-generate greeting audio for instant playback
Eliminates TTS delay on call answer - greeting plays immediately
"""

import os
import sys
import requests
import subprocess
import logging

# Add project directory to path
sys.path.insert(0, "/home/aiadmin/netovo_voicebot/kokora")
from config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Greeting text from voicebot_main.py
GREETING_TEXT = "Hello, thank you for calling NET-OH-VOH. I'm Alexis. How can I help you?"
GREETING_VOICE = "af_heart"

# Asterisk sounds directory
ASTERISK_SOUNDS_DIR = "/usr/share/asterisk/sounds"
GREETING_FILENAME = "netovo_greeting"

# Model worker service URL
WORKER_URL = "http://127.0.0.1:8777"

def check_worker_health():
    """Check if model worker service is running"""
    try:
        response = requests.get(f"{WORKER_URL}/health", timeout=10)
        if response.status_code == 200:
            health = response.json()
            if health.get("models_loaded"):
                logger.info("✅ Model worker service is healthy and ready")
                return True
            else:
                logger.error("❌ Model worker service models not loaded")
                return False
        else:
            logger.error(f"❌ Model worker health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Cannot connect to model worker: {e}")
        return False

def generate_greeting_audio():
    """Generate greeting audio via model worker service"""
    try:
        logger.info(f"Generating greeting: '{GREETING_TEXT}'")

        # Call TTS service
        response = requests.post(
            f"{WORKER_URL}/synthesize",
            json={
                "text": GREETING_TEXT,
                "voice": GREETING_VOICE
            },
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"TTS request failed: {response.status_code} - {response.text}")
            return None

        result = response.json()
        temp_file = result["path"]
        duration = result["duration"]

        logger.info(f"✅ Greeting generated in {duration:.2f}s: {temp_file}")
        return temp_file

    except Exception as e:
        logger.error(f"Greeting generation failed: {e}")
        return None

def install_greeting_file(temp_file):
    """Install greeting file to Asterisk sounds directory"""
    try:
        # Target file path (without extension - Asterisk adds it)
        target_path = os.path.join(ASTERISK_SOUNDS_DIR, f"{GREETING_FILENAME}.wav")

        logger.info(f"Installing greeting: {temp_file} -> {target_path}")

        # Copy file to Asterisk sounds directory
        subprocess.run(["sudo", "cp", temp_file, target_path], check=True)

        # Set proper ownership and permissions
        subprocess.run(["sudo", "chown", "asterisk:asterisk", target_path], check=True)
        subprocess.run(["sudo", "chmod", "644", target_path], check=True)

        # Cleanup temp file
        os.unlink(temp_file)

        logger.info(f"✅ Greeting installed successfully: {target_path}")

        # Verify file
        if os.path.exists(target_path):
            file_size = os.path.getsize(target_path)
            logger.info(f"Greeting file verified: {file_size} bytes")
            return True
        else:
            logger.error("Greeting file not found after installation")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Installation command failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Installation failed: {e}")
        return False

def test_greeting_playback():
    """Test that greeting can be played by Asterisk"""
    target_path = os.path.join(ASTERISK_SOUNDS_DIR, f"{GREETING_FILENAME}.wav")

    if not os.path.exists(target_path):
        logger.error("Greeting file not found for testing")
        return False

    try:
        # Test with aplay (basic audio test)
        logger.info("Testing greeting playback...")
        result = subprocess.run(
            ["aplay", "-t", "wav", target_path],
            capture_output=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info("✅ Greeting playback test successful")
            return True
        else:
            logger.error(f"Playback test failed: {result.stderr.decode()}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Playback test timed out")
        return False
    except Exception as e:
        logger.error(f"Playback test failed: {e}")
        return False

def main():
    """Main entry point"""
    logger.info("🎤 NETOVO Greeting Generator - Pre-generating greeting audio")

    # Check if model worker is ready
    if not check_worker_health():
        logger.error("Model worker service not ready. Start it first with:")
        logger.error("sudo systemctl start netovo-model-worker")
        return 1

    # Generate greeting audio
    temp_file = generate_greeting_audio()
    if not temp_file:
        logger.error("Failed to generate greeting audio")
        return 1

    # Install to Asterisk sounds directory
    if not install_greeting_file(temp_file):
        logger.error("Failed to install greeting file")
        return 1

    # Test playback
    if not test_greeting_playback():
        logger.warning("Greeting installed but playback test failed")
        logger.warning("This may be normal if no audio device is available")

    logger.info("🚀 Greeting generation complete!")
    logger.info(f"Greeting available as: STREAM FILE {GREETING_FILENAME}")
    logger.info("VoiceBot will now play greeting instantly on call answer")

    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)