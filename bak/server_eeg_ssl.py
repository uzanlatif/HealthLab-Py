import asyncio
import websockets
import json
import time
import signal
import sys
import ssl
import os
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowError

# Global board instance
board = None
board_initialized = False

# Signal handler
def signal_handler(sig, frame):
    print("\n🛑 Signal received, cleaning up...")
    cleanup()
    sys.exit(0)

def cleanup():
    global board, board_initialized
    if board and board_initialized:
        try:
            board.stop_stream()
        except BrainFlowError as e:
            print("⚠️ stop_stream error:", e)
        try:
            board.release_session()
        except BrainFlowError as e:
            print("⚠️ release_session error:", e)
    board_initialized = False
    print("✅ Cleaned up")

# Register signal handler
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# EEG handler
async def eeg_handler(websocket, path):
    print("🔌 Client connected")
    try:
        sampling_rate = board.get_sampling_rate(board_id)
        interval = 1.0 / sampling_rate

        while True:
            raw_data = board.get_current_board_data(50)
            sensor_data = {}
            timestamp_now = time.time()

            for ch in eeg_channels:
                label = channel_names.get(ch, f"CH{ch}")
                samples = raw_data[ch]
                sensor_data[label] = [
                    {
                        "y": float(val),
                        "__timestamp__": timestamp_now - (len(samples) - i - 1) * interval
                    }
                    for i, val in enumerate(samples)
                ]

            await websocket.send(json.dumps(sensor_data))
            await asyncio.sleep(0.3)
    except websockets.ConnectionClosed:
        print("❌ Client disconnected")
    except Exception as e:
        print("🚨 Handler error:", e)

# BrainFlow config
params = BrainFlowInputParams()
params.serial_port = '/dev/ttyUSB0'
board_id = BoardIds.CYTON_DAISY_BOARD.value
eeg_channels = BoardShim.get_eeg_channels(board_id)

channel_names = {
    1: "EEG_1", 2: "EEG_2", 3: "EEG_3", 4: "EEG_4", 5: "EEG_5", 6: "EEG_6",
    7: "EEG_7", 8: "EEG_8", 9: "EEG_9", 10: "EEG_10",
    11: "EEG_11", 12: "EEG_12", 13: "EEG_13", 14: "EEG_14",
    15: "EEG_15", 16: "EEG_16"
}

async def main():
    global board, board_initialized
    board = BoardShim(board_id, params)

    try:
        print("🔄 Preparing BrainFlow session...")
        board.prepare_session()
        board.start_stream()
        board_initialized = True
        print("✅ MBS streaming started")

        ip = '0.0.0.0'
        port = 7777

        # Use SSL from same folder
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cert_path = os.path.join(current_dir, "cert.pem")
        key_path = os.path.join(current_dir, "key.pem")

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)

        async with websockets.serve(
            eeg_handler, ip, port, ssl=ssl_context
        ):
            print(f"🔒 Secure WebSocket (WSS) running at wss://<raspi-ip>:{port}")
            await asyncio.Future()
    except BrainFlowError as e:
        print("🚨 BrainFlow error:", e)
    except Exception as e:
        print("🚨 Unexpected error:", e)
    finally:
        cleanup()

if __name__ == '__main__':
    asyncio.run(main())
