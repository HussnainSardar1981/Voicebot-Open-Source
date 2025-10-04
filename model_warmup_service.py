#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
Model Warm-up Service for Professional VoiceBot
Run this service to pre-load all models before customer calls come in
Ensures instant response times for professional customer service
"""

import sys
import os
import time
import signal
import logging

# Add project directory to path
sys.path.insert(0, "/home/aiadmin/netovo_voicebot/kokora")

from config import setup_logging, setup_project_path
from whisper_asr_client import WhisperASRClient
from kokoro_tts_client import KokoroTTSClient
from ollama_client import SimpleOllamaClient

# Set up configuration
setup_project_path()
setup_logging()
logger = logging.getLogger(__name__)

class ModelWarmupService:
    """Service to keep models warm and ready for instant response"""

    def __init__(self):
        self.running = True
        self.models_loaded = False
        self.tts_client = None
        self.asr_client = None
        self.ollama_client = None

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Received shutdown signal, stopping service...")
        self.running = False

    def load_models(self):
        """Load all models and keep them warm"""
        try:
            logger.info("🔥 Model Warm-up Service - Loading pure Whisper + Kokoro stack...")
            start_time = time.time()

            # Load Kokoro TTS
            logger.info("Loading professional Kokoro TTS...")
            self.tts_client = KokoroTTSClient()
            logger.info("✅ Kokoro TTS loaded")

            # Load Whisper ASR
            logger.info("Loading Whisper Large ASR on GPU...")
            self.asr_client = WhisperASRClient()
            logger.info("✅ Whisper ASR loaded")

            # Load Ollama
            logger.info("Loading Ollama client...")
            self.ollama_client = SimpleOllamaClient()
            logger.info("✅ Ollama loaded")

            # Test models with warm-up calls
            logger.info("Warming up models with test calls...")

            # Warm up TTS
            test_tts = self.tts_client.synthesize("Hello, this is a warm-up test.", voice_type="greeting")
            if test_tts:
                os.unlink(test_tts)
                logger.info("✅ TTS warm-up successful")

            # Warm up Ollama
            test_response = self.ollama_client.generate("Hello")
            if test_response:
                logger.info("✅ Ollama warm-up successful")

            total_time = time.time() - start_time
            self.models_loaded = True
            logger.info(f"🚀 All models loaded and warmed up in {total_time:.1f}s")
            logger.info("🎯 VoiceBot ready for INSTANT customer service!")

        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            self.models_loaded = False

    def keep_alive(self):
        """Keep the service alive and models warm"""
        logger.info("Model Warm-up Service running - keeping models ready...")

        # Periodic health checks
        health_check_interval = 300  # 5 minutes
        last_health_check = time.time()

        while self.running:
            try:
                current_time = time.time()

                # Periodic health check
                if current_time - last_health_check > health_check_interval:
                    if self.models_loaded:
                        logger.info("💚 Models healthy and ready for instant customer service")
                    else:
                        logger.warning("⚠️ Models not loaded - attempting reload")
                        self.load_models()
                    last_health_check = current_time

                # Sleep briefly to avoid busy waiting
                time.sleep(30)  # Check every 30 seconds

            except KeyboardInterrupt:
                logger.info("Service interrupted by user")
                break
            except Exception as e:
                logger.error(f"Service error: {e}")
                time.sleep(60)  # Wait before retrying

    def run(self):
        """Main service loop"""
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        logger.info("🚀 Starting Model Warm-up Service for Professional VoiceBot")

        # Load models initially
        self.load_models()

        if self.models_loaded:
            # Keep service alive
            self.keep_alive()
        else:
            logger.error("Failed to load models - service cannot start")
            return 1

        logger.info("Model Warm-up Service stopped")
        return 0

def main():
    """Main entry point"""
    service = ModelWarmupService()
    return service.run()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
