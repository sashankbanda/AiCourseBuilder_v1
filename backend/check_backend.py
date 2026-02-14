import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import app.main...")
    from app.main import app
    print("Successfully imported app.main!")
    
    print("Attempting to import agents...")
    from app.agents.orchestrator import Orchestrator
    print("Successfully imported Orchestrator!")
    
except Exception as e:
    print(f"Import Error: {e}")
    sys.exit(1)
