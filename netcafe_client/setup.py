import os
import sys
import subprocess

def setup_client():
    print("Setting up NetCafe Client...")
    
    # Install requirements
    print("Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    print("\nSetup complete! You can now run the client using:")
    print("python client.py")
    print("or")
    print("run_client.bat")

if __name__ == '__main__':
    setup_client() 