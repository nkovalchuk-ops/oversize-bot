import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")

print("TOKEN:", BOT_TOKEN)  # тимчасово для перевірки