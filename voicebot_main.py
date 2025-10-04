#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
EXACT RIVA Working Code Replication Test
Drop-in replacement for voicebot_main.py - same filename, different content
"""

import sys
import os
import time
import uuid
import logging

# Set up logging exactly like RIVA
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - FixedBot - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

class ExactRivaAGI:
    """EXACT copy of RIVA working AGI class"""

    def __init__(self):
        self.env = {}
        self.connected = True
        self.call_answered = False
        self._parse_env()

    def _parse_env(self):
        """Parse AGI environment"""
        env_count = 0
        while True:
            line = sys.stdin.readline()
            if not line or not line.strip():
                break
            if ':' in line:
                key, value = line.split(':', 1)
                self.env[key.strip()] = value.strip()
                env_count += 1
        logger.info(f"AGI env parsed: {env_count} vars")

    def command(self, cmd):
        """Send AGI command"""
        try:
            logger.debug(f"AGI: {cmd}")
            print(cmd)
            sys.stdout.flush()

            result = sys.stdin.readline().strip()
            logger.debug(f"Response: {result}")

            # Detect hangup scenarios
            if result.startswith('200 result=-1') or 'hangup' in result.lower():
                logger.info("Hangup detected via AGI response")
                self.connected = False

            return result
        except Exception as e:
            logger.error(f"AGI command failed: {e}")
            self.connected = False
            return "ERROR"

    def answer(self):
        """Answer call"""
        result = self.command("ANSWER")
        success = result and result.startswith('200')
        if success:
            self.call_answered = True
            logger.info("Call answered")
        return success

    def hangup(self):
        """Hangup call"""
        self.command("HANGUP")
        self.connected = False

    def verbose(self, msg):
        """Verbose message"""
        return self.command(f'VERBOSE "{msg}"')

    def stream_file(self, filename):
        """Play audio file - NO QUOTES on filename"""
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]
        result = self.command(f'STREAM FILE {filename} ""')
        success = result and result.startswith('200')
        logger.info(f"Stream file result: {result} (success: {success})")
        return success

class ExactRivaRecorder:
    """EXACT copy of RIVA working FastInterruptRecorder"""

    def __init__(self, agi):
        self.agi = agi

    def get_user_input_with_interrupt(self, timeout=10):
        """EXACT copy of RIVA working recording method"""
        record_file = f"/var/spool/asterisk/monitor/user_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        logger.info("Listening for user input...")
        # EXACT same command as RIVA working setup
        result = self.agi.command(f'RECORD FILE {record_file} wav "#" {timeout * 1000} 0 s=2')

        if not self.agi.connected:
            return None

        wav_file = f"{record_file}.wav"
        transcript = ""

        if os.path.exists(wav_file):
            file_size = os.path.getsize(wav_file)
            logger.info(f"Recording: {file_size} bytes")

            if file_size > 800:  # EXACT same threshold as RIVA
                logger.info(f"SUCCESS: Got {file_size} bytes - RIVA method WORKS!")
                self.agi.verbose(f"RIVA SUCCESS: {file_size} bytes recorded")
                # Instead of ASR, just return success indicator
                transcript = f"RIVA_RECORDING_SUCCESS_{file_size}_BYTES"
            else:
                logger.error(f"FAILED: Only {file_size} bytes - same issue persists")
                self.agi.verbose(f"RIVA FAILED: only {file_size} bytes")

            # Cleanup
            try:
                os.unlink(wav_file)
            except Exception as e:
                logger.debug(f"Cleanup failed: {e}")
        else:
            logger.error("No recording file created - same as current issue")
            self.agi.verbose("RIVA TEST: No file created")

        return transcript.strip() if transcript else None

def main():
    """Main AGI handler - EXACT RIVA replication test"""
    try:
        logger.info("=== EXACT RIVA REPLICATION TEST ===")

        # Initialize AGI exactly like RIVA
        agi = ExactRivaAGI()
        caller_id = agi.env.get('agi_callerid', 'Unknown')
        logger.info(f"Call from: {caller_id}")

        # Answer call exactly like RIVA
        if not agi.answer():
            logger.error("Failed to answer")
            return

        agi.verbose("RIVA Replication Test Starting...")

        # Play a simple greeting to verify TTS path
        agi.stream_file("demo-thanks")
        agi.verbose("Playing test greeting")

        # Initialize recorder exactly like RIVA
        recorder = ExactRivaRecorder(agi)

        # Test recording exactly like RIVA (multiple attempts)
        for attempt in range(3):
            logger.info(f"Testing EXACT RIVA recording method - Attempt {attempt + 1}")
            agi.verbose(f"RIVA Test Attempt {attempt + 1}")

            transcript = recorder.get_user_input_with_interrupt(timeout=12)

            if transcript and "SUCCESS" in transcript:
                logger.info(f"SUCCESS: RIVA method worked: {transcript}")
                agi.verbose(f"RIVA SUCCESS: {transcript}")
                agi.stream_file("demo-congrats")
                break
            else:
                logger.error(f"FAILED: Attempt {attempt + 1} - Even EXACT RIVA method fails!")
                agi.verbose(f"RIVA FAILED: Attempt {attempt + 1}")

                if attempt < 2:  # Not last attempt
                    agi.stream_file("beep")  # Give user audio feedback
                    time.sleep(1)

        # Final result
        if transcript and "SUCCESS" in transcript:
            logger.info("CONCLUSION: RIVA method WORKS - Issue is in new implementation")
            agi.verbose("CONCLUSION: RIVA method works")
        else:
            logger.error("CONCLUSION: System environment changed - RIVA method also fails")
            agi.verbose("CONCLUSION: System changed")

        # End call
        agi.verbose("RIVA Test Complete")
        time.sleep(1)
        agi.hangup()

        logger.info("=== RIVA Replication Test Complete ===")

    except Exception as e:
        logger.error(f"RIVA test error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        try:
            agi = ExactRivaAGI()
            agi.answer()
            agi.verbose("RIVA Test Error")
            agi.stream_file("demo-thanks")
            agi.hangup()
        except Exception as e:
            logger.error(f"Error cleanup failed: {e}")

if __name__ == "__main__":
    main()
