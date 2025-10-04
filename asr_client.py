#!/usr/bin/env python3
"""
DirectASRClient - Speech Recognition using RIVA Docker
Extracted from production_agi_voicebot.py
"""

import os
import time
import uuid
import subprocess
import logging
import re

logger = logging.getLogger(__name__)

class DirectASRClient:
    """Direct Docker ASR using your proven commands"""

    def __init__(self, container="riva-speech"):
        self.container = container

    def transcribe_file(self, audio_file):
        """Direct ASR transcription using Docker with format conversion"""
        try:
            unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            container_path = f"/tmp/riva_asr_{unique_id}.wav"
            converted_path = f"/tmp/converted_{unique_id}.wav"

            # Convert audio to RIVA-compatible format (16kHz, mono, 16-bit)
            sox_cmd = [
                'sox', audio_file,
                '-r', '16000',    # 16kHz (RIVA preferred)
                '-c', '1',        # Mono
                '-b', '16',       # 16-bit
                '-e', 'signed-integer',  # PCM
                converted_path
            ]

            logger.info(f"Converting audio for ASR: {' '.join(sox_cmd)}")
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

            # Copy converted file to container
            copy_cmd = ["docker", "cp", converted_path, f"{self.container}:{container_path}"]
            copy_result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=10)

            if copy_result.returncode != 0:
                logger.error(f"ASR copy failed: {copy_result.stderr}")
                return ""

            # Run ASR
            cmd = [
                "docker", "exec", self.container,
                "/opt/riva/clients/riva_streaming_asr_client",
                f"--riva_uri=localhost:50051",
                f"--audio_file={container_path}",
                "--simulate_realtime=false",
                "--language_code=en-US"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # DEBUG: Log everything RIVA returns
            logger.info(f"RIVA ASR returncode: {result.returncode}")
            logger.info(f"RIVA ASR stdout: {repr(result.stdout)}")
            logger.info(f"RIVA ASR stderr: {repr(result.stderr)}")

            # Cleanup
            try:
                subprocess.run(["docker", "exec", self.container, "rm", "-f", container_path],
                              capture_output=True, timeout=10)
            except Exception as e:
                logger.warning(f"Container cleanup failed: {e}")
            try:
                os.unlink(converted_path)
            except Exception as e:
                logger.debug(f"Temp file cleanup failed: {e}")

            if result.returncode == 0:
                # Parse transcript - ENHANCED
                full_output = result.stdout.strip()
                logger.info(f"Full RIVA output: {full_output}")

                if not full_output:
                    logger.warning("RIVA returned empty output")
                    return ""

                lines = full_output.split('\n')
                logger.info(f"RIVA output lines: {len(lines)}")

                # Look for RIVA's final transcript format: "0 : [transcript]"
                for i, line in enumerate(lines):
                    logger.info(f"Line {i}: {repr(line)}")

                    # RIVA format: "0 : Hello." or "0 : Can you please resolve my email verification issue? "
                    if line.strip().startswith("0 : "):
                        transcript = line.strip()[4:].strip()  # Remove "0 : " prefix
                        if transcript and len(transcript) > 1:
                            # Clean up transcript
                            transcript = transcript.strip('"').strip("'").strip()
                            if transcript:
                                logger.info(f"RIVA transcript found: {transcript}")
                                return transcript

                # Fallback: Look for any line with meaningful speech content
                for line in lines:
                    # Skip metadata lines
                    if any(x in line.lower() for x in ['loading', 'file:', 'done loading', 'audio processed', 'run time', 'total audio', 'throughput']):
                        continue

                    # Look for lines that look like speech
                    if line.strip() and not line.strip().startswith('-') and len(line.strip()) > 3:
                        # Remove timestamps and confidence scores
                        cleaned = re.sub(r'\d+\.\d+e[+-]\d+', '', line)  # Remove scientific notation
                        cleaned = re.sub(r'\d{4,}', '', cleaned)          # Remove timestamps
                        cleaned = cleaned.strip()

                        # Check if it looks like speech
                        if cleaned and len(cleaned) > 3 and any(c.isalpha() for c in cleaned):
                            logger.info(f"Fallback transcript: {cleaned}")
                            return cleaned

            else:
                logger.error(f"RIVA ASR failed with returncode: {result.returncode}")
                logger.error(f"RIVA stderr: {result.stderr}")

            logger.warning("No transcript found after all parsing attempts")
            return ""

        except Exception as e:
            logger.error(f"ASR error: {e}")
            return ""