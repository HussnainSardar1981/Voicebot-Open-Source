#!/usr/bin/env python3
"""
Audio Utilities - Audio conversion and processing
Extracted from production_agi_voicebot.py
"""

import os
import time
import uuid
import subprocess
import logging

logger = logging.getLogger(__name__)

def convert_audio_for_asterisk(input_wav):
    """Convert to exact Asterisk-compatible format"""
    try:
        # Create unique timestamp to prevent file collisions
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # Try multiple format approaches
        formats_to_try = [
            {
                'ext': 'wav',
                'path': f"/usr/share/asterisk/sounds/tts_{unique_id}.wav",
                'sox_args': [
                    'sox', input_wav,
                    '-r', '8000',      # 8kHz sample rate
                    '-c', '1',         # Mono
                    '-b', '16',        # 16-bit
                    '-e', 'signed-integer',  # PCM
                    '-t', 'wav'        # Explicitly specify WAV format
                ]
            },
            {
                'ext': 'sln16',
                'path': f"/usr/share/asterisk/sounds/tts_{unique_id}.sln16",
                'sox_args': [
                    'sox', input_wav,
                    '-r', '8000',      # 8kHz
                    '-c', '1',         # Mono
                    '-b', '16',        # 16-bit
                    '-e', 'signed-integer',  # PCM
                    '-t', 'raw'        # Raw format (what .sln16 is)
                ]
            },
            {
                'ext': 'gsm',
                'path': f"/usr/share/asterisk/sounds/tts_{unique_id}.gsm",
                'sox_args': [
                    'sox', input_wav,
                    '-r', '8000',      # 8kHz
                    '-c', '1',         # Mono
                    '-t', 'gsm'        # GSM format (very compatible)
                ]
            }
        ]

        for fmt in formats_to_try:
            try:
                logger.info(f"Trying {fmt['ext']} format...")

                # Add output path to sox command
                sox_cmd = fmt['sox_args'] + [fmt['path']]
                logger.info(f"Sox command: {' '.join(sox_cmd)}")

                result = subprocess.run(sox_cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0 and os.path.exists(fmt['path']):
                    file_size = os.path.getsize(fmt['path'])
                    if file_size > 100:  # Valid file
                        os.chmod(fmt['path'], 0o644)
                        filename = f"tts_{unique_id}"
                        logger.info(f"SUCCESS: {fmt['ext']} format created: {filename} ({file_size} bytes)")
                        return filename
                    else:
                        logger.warning(f"{fmt['ext']} file too small: {file_size} bytes")
                        os.unlink(fmt['path'])
                else:
                    logger.warning(f"{fmt['ext']} conversion failed: {result.stderr}")

            except Exception as e:
                logger.warning(f"{fmt['ext']} format failed: {e}")

        # If all formats fail, try copying a working built-in file and replacing content
        try:
            logger.info("Trying built-in file replacement method...")

            # Find a working built-in file to use as template
            template_files = [
                "/var/lib/asterisk/sounds/demo-thanks.wav",
                "/var/lib/asterisk/sounds/demo-congrats.wav",
                "/var/lib/asterisk/sounds/hello.wav"
            ]

            template_file = None
            for tf in template_files:
                if os.path.exists(tf):
                    template_file = tf
                    break

            if template_file:
                output_path = f"/usr/share/asterisk/sounds/tts_{unique_id}.wav"

                # Use sox to match the exact format of the working template
                sox_cmd = [
                    'sox', input_wav,
                    output_path,
                    'rate', '8000',    # Alternative syntax
                    'channels', '1',   # Alternative syntax
                    'bits', '16'       # Alternative syntax
                ]

                result = subprocess.run(sox_cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0 and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    if file_size > 100:
                        os.chmod(output_path, 0o644)
                        logger.info(f"Template-based conversion success: {file_size} bytes")
                        return f"tts_{unique_id}"

        except Exception as e:
            logger.error(f"Template method failed: {e}")

        logger.error("All audio conversion methods failed")
        return None

    except Exception as e:
        logger.error(f"Audio conversion fatal error: {e}")
        return None