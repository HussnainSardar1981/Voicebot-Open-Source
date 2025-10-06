#!/usr/bin/python3
"""
Model Warm-up Service for Professional VoiceBot
Loads models ONCE and serves AGI requests via Unix socket
Ensures instant response times with persistent models
"""

import sys
import os
import time
import signal
import logging
import socket
import json
import threading
from pathlib import Path

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

# Socket configuration
SOCKET_PATH = "/tmp/netovo_models.sock"

class ModelWarmupService:
    """Service to keep models warm and serve requests via Unix socket"""

    def __init__(self):
        self.running = True
        self.models_loaded = False
        self.tts_client = None
        self.asr_client = None
        self.ollama_client = None
        self.socket_server = None

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Received shutdown signal, stopping service...")
        self.running = False
        self._cleanup_socket()

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

    def _cleanup_socket(self):
        """Clean up socket file"""
        try:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
                logger.info("Socket file cleaned up")
        except Exception as e:
            logger.error(f"Socket cleanup failed: {e}")

    def _setup_socket(self):
        """Set up Unix domain socket server"""
        try:
            # Remove existing socket file
            self._cleanup_socket()

            # Create socket
            self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket_server.bind(SOCKET_PATH)
            self.socket_server.listen(5)

            # Set permissions for asterisk user access
            os.chmod(SOCKET_PATH, 0o660)
            try:
                import pwd, grp
                # Set owner to aiadmin, group to asterisk
                aiadmin_uid = pwd.getpwnam('aiadmin').pw_uid
                asterisk_gid = grp.getgrnam('asterisk').gr_gid
                os.chown(SOCKET_PATH, aiadmin_uid, asterisk_gid)
            except:
                logger.warning("Could not set socket ownership - permissions may need manual adjustment")

            logger.info(f"✅ Socket server listening on {SOCKET_PATH}")
            return True

        except Exception as e:
            logger.error(f"Socket setup failed: {e}")
            return False

    def _handle_client_request(self, client_socket):
        """Handle individual client request"""
        try:
            # Receive request
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return

            request = json.loads(data)
            action = request.get('action')

            response = {'status': 'error', 'message': 'Unknown action'}

            if not self.models_loaded:
                response = {'status': 'error', 'message': 'Models not loaded'}

            elif action == 'synthesize':
                text = request.get('text', '')
                voice_type = request.get('voice_type', 'default')

                if text:
                    tts_file = self.tts_client.synthesize(text, voice_type=voice_type)
                    if tts_file:
                        response = {'status': 'success', 'file_path': tts_file}
                    else:
                        response = {'status': 'error', 'message': 'TTS synthesis failed'}
                else:
                    response = {'status': 'error', 'message': 'No text provided'}

            elif action == 'transcribe':
                audio_file = request.get('audio_file', '')

                if audio_file and os.path.exists(audio_file):
                    transcript = self.asr_client.transcribe_file(audio_file)
                    response = {'status': 'success', 'transcript': transcript or ''}
                else:
                    response = {'status': 'error', 'message': 'Audio file not found'}

            elif action == 'generate':
                prompt = request.get('prompt', '')

                if prompt:
                    ai_response = self.ollama_client.generate(prompt)
                    response = {'status': 'success', 'response': ai_response or ''}
                else:
                    response = {'status': 'error', 'message': 'No prompt provided'}

            elif action == 'health':
                response = {'status': 'success', 'models_loaded': self.models_loaded}

            # Send response
            response_json = json.dumps(response)
            client_socket.send(response_json.encode('utf-8'))

        except Exception as e:
            logger.error(f"Client request handling failed: {e}")
            try:
                error_response = json.dumps({'status': 'error', 'message': str(e)})
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()

    def _run_socket_server(self):
        """Run socket server in separate thread"""
        logger.info("🔌 Starting socket server thread...")

        while self.running:
            try:
                if self.socket_server:
                    client_socket, addr = self.socket_server.accept()
                    # Handle each request in a separate thread for concurrent access
                    client_thread = threading.Thread(
                        target=self._handle_client_request,
                        args=(client_socket,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                else:
                    time.sleep(1)

            except Exception as e:
                if self.running:  # Only log errors if we're supposed to be running
                    logger.error(f"Socket server error: {e}")
                break

    def run(self):
        """Main service loop"""
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        logger.info("🚀 Starting Model Warm-up Service with Socket Server")

        # Load models initially
        self.load_models()

        if not self.models_loaded:
            logger.error("Failed to load models - service cannot start")
            return 1

        # Set up socket server
        if not self._setup_socket():
            logger.error("Failed to setup socket server - service cannot start")
            return 1

        # Start socket server in background thread
        socket_thread = threading.Thread(target=self._run_socket_server)
        socket_thread.daemon = True
        socket_thread.start()

        logger.info("🎯 Service ready - models loaded, socket server running")

        # Keep service alive with periodic health checks
        self.keep_alive()

        # Cleanup on exit
        self._cleanup_socket()
        logger.info("Model Warm-up Service stopped")
        return 0

def main():
    """Main entry point"""
    service = ModelWarmupService()
    return service.run()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)