#!/usr/bin/env python3
"""
Socket Client Classes for NETOVO VoiceBot
Communicates with persistent model warmup service via Unix socket
Provides same interface as original clients but with zero model loading
"""

import os
import socket
import json
import logging

logger = logging.getLogger(__name__)

SOCKET_PATH = "/tmp/netovo_models.sock"

class SocketClient:
    """Base socket client for communication with model service"""

    def __init__(self):
        self.socket_path = SOCKET_PATH
        logger.info(f"Socket client initialized - connecting to {self.socket_path}")

    def _send_request(self, request_data):
        """Send request to socket server and get response (FIXED: no truncation)"""
        try:
            # Create socket connection
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.connect(self.socket_path)

            # Send request
            request_json = json.dumps(request_data)
            client_socket.send(request_json.encode('utf-8'))

            # Shutdown write side to signal end of request
            client_socket.shutdown(socket.SHUT_WR)

            # Receive response in chunks until EOF (FIXED: prevents truncation)
            response_chunks = []
            while True:
                chunk = client_socket.recv(8192)
                if not chunk:
                    break
                response_chunks.append(chunk)

            client_socket.close()

            # Decode full response
            if response_chunks:
                response_data = b''.join(response_chunks).decode('utf-8')
                response = json.loads(response_data)
                return response
            else:
                return {'status': 'error', 'message': 'Empty response from server'}

        except FileNotFoundError:
            logger.error(f"Socket not found: {self.socket_path}")
            logger.error("Make sure model warmup service is running!")
            return {'status': 'error', 'message': 'Service not available'}

        except Exception as e:
            logger.error(f"Socket communication failed: {e}")
            return {'status': 'error', 'message': str(e)}

class KokoroSocketClient(SocketClient):
    """Socket-based Kokoro TTS Client - Zero model loading overhead"""

    def synthesize(self, text, voice_type="default"):
        """
        Synthesize speech via socket communication

        Args:
            text (str): Text to synthesize
            voice_type (str): Voice type (greeting, empathetic, etc.)

        Returns:
            str: Path to generated audio file or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for synthesis")
            return None

        request = {
            'action': 'synthesize',
            'text': text.strip(),
            'voice_type': voice_type
        }

        response = self._send_request(request)

        if response.get('status') == 'success':
            file_path = response.get('file_path')
            if file_path and os.path.exists(file_path):
                logger.info(f"TTS success via socket: {file_path}")
                return file_path
            else:
                logger.error(f"TTS file not found: {file_path}")
                return None
        else:
            error_msg = response.get('message', 'Unknown error')
            logger.error(f"TTS synthesis failed: {error_msg}")
            return None

class WhisperSocketClient(SocketClient):
    """Socket-based Whisper ASR Client - Zero model loading overhead"""

    def transcribe_file(self, audio_file):
        """
        Transcribe audio file via socket communication

        Args:
            audio_file (str): Path to audio file

        Returns:
            str: Transcribed text or empty string if failed
        """
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return ""

        request = {
            'action': 'transcribe',
            'audio_file': audio_file
        }

        response = self._send_request(request)

        if response.get('status') == 'success':
            transcript = response.get('transcript', '')
            logger.info(f"ASR success via socket: '{transcript[:50]}...'")
            return transcript
        else:
            error_msg = response.get('message', 'Unknown error')
            logger.error(f"ASR transcription failed: {error_msg}")
            return ""

    def transcribe(self, audio_file):
        """Alias for transcribe_file for compatibility"""
        return self.transcribe_file(audio_file)

class OllamaSocketClient(SocketClient):
    """Socket-based Ollama Client - Uses persistent connection"""

    def generate(self, prompt):
        """
        Generate response via socket communication

        Args:
            prompt (str): Input prompt

        Returns:
            str: Generated response or empty string if failed
        """
        if not prompt or not prompt.strip():
            logger.warning("Empty prompt provided")
            return ""

        request = {
            'action': 'generate',
            'prompt': prompt.strip()
        }

        response = self._send_request(request)

        if response.get('status') == 'success':
            ai_response = response.get('response', '')
            logger.info(f"Ollama success via socket: '{ai_response[:50]}...'")
            return ai_response
        else:
            error_msg = response.get('message', 'Unknown error')
            logger.error(f"Ollama generation failed: {error_msg}")
            return ""

def test_socket_connection():
    """Test connection to socket server"""
    try:
        client = SocketClient()
        response = client._send_request({'action': 'health'})

        if response.get('status') == 'success':
            models_loaded = response.get('models_loaded', False)
            if models_loaded:
                logger.info("✅ Socket connection successful - models ready")
                return True
            else:
                logger.warning("⚠️ Socket connected but models not loaded")
                return False
        else:
            logger.error(f"❌ Socket health check failed: {response.get('message')}")
            return False

    except Exception as e:
        logger.error(f"❌ Socket connection test failed: {e}")
        return False

# Create aliases for compatibility with existing code
KokoroTTSClient = KokoroSocketClient
WhisperASRClient = WhisperSocketClient
SimpleOllamaClient = OllamaSocketClient
