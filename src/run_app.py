from pyngrok import ngrok
import os
from dotenv import load_dotenv
import subprocess
import time
import psutil
import requests

# Load environment variables
load_dotenv()

def check_port_available(port):
    """Check if the port is available"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result != 0

def get_active_connections(url):
    """Get number of active connections to the app"""
    try:
        response = requests.get(f"{url}/healthz", timeout=1)
        return response.headers.get('X-Concurrent-Users', '0')
    except:
        return "Unknown"

def main():
    # Check if port 8501 is available
    if not check_port_available(8501):
        print("\n❌ Error: Port 8501 is already in use!")
        print("Please stop any running Streamlit applications and try again.")
        return

    # Get the ngrok auth token from environment variable
    ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
    if not ngrok_token or ngrok_token == "your_ngrok_auth_token_here":
        print("\n❌ Error: NGROK_AUTH_TOKEN not set!")
        print("Please follow these steps:")
        print("1. Sign up at https://ngrok.com/")
        print("2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken")
        print("3. Add your token to the .env file:")
        print("   NGROK_AUTH_TOKEN=your_actual_token_here")
        return

    try:
        print("\n🔄 Starting ngrok tunnel...")
        # Start ngrok tunnel to port 8501 (default Streamlit port)
        tunnel = ngrok.connect(8501)
        public_url = tunnel.public_url
        print(f"✨ ngrok tunnel established!")
        print(f"👉 Public URL: {public_url}")
        
        print("\n🔄 Starting Streamlit app...")
        # Start Streamlit in a separate process with optimized settings
        env = {
            **os.environ,
            "STREAMLIT_SERVER_ADDRESS": "0.0.0.0",
            "STREAMLIT_SERVER_HEADLESS": "true",
            "STREAMLIT_SERVER_ENABLE_CORS": "false",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"
        }
        streamlit_process = subprocess.Popen(
            ["streamlit", "run", "app.py"],
            env=env
        )
        
        print("\n🚀 Application is now running!")
        print(f"💻 Local URL: http://localhost:8501")
        print(f"🌍 Public URL: {public_url}")
        print("\nImportant Notes:")
        print("1. Share the Public URL with your students")
        print("2. The free ngrok plan supports up to 40 connections/minute")
        print("3. The tunnel will expire after 2 hours")
        print("4. Each student should register with a unique email")
        print("\nMonitoring:")
        
        # Monitor the application
        while True:
            time.sleep(5)  # Check every 5 seconds
            # Get CPU and memory usage
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            # Clear previous line and print new status
            print(f"\r💻 CPU: {cpu_percent}% | 🎯 RAM: {memory_percent}% | ⏱️ Tunnel valid for 2 hours", end="")
            
    except KeyboardInterrupt:
        print("\n\n🔄 Shutting down...")
        # Clean up ngrok tunnels
        ngrok.kill()
        # Stop Streamlit process
        streamlit_process.terminate()
        print("✨ Server stopped successfully!")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nCommon issues:")
        print("1. Make sure you have a valid ngrok auth token")
        print("2. Check if port 8501 is available")
        print("3. Ensure you're running the script from the src directory")
        ngrok.kill()
        
if __name__ == "__main__":
    main() 