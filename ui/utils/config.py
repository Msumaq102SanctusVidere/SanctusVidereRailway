from dotenv import load_dotenv
import os

# Load environment variables from ui/.env (if present)
load_dotenv()

# Base URL of your API (defaults to your Railway backend)
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://web-production-409b.up.railway.app"
)
