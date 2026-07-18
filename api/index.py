import sys
import os

# Add the project root and backend to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from backend.api import app as fastapi_app

# Vercel needs 'app' to be the FastAPI instance
app = fastapi_app
