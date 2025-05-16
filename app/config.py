import os
from dotenv import load_dotenv
import logging

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Load secrets
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("REGION_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
