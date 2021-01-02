import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

VERSION = "0.1.0"
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
DATABASES = os.getenv("DATABASES").split(",")
LOCAL_DESTINATION = os.getenv("LOCAL_DESTINATION")
ROLLING = int(os.getenv("ROLLING"))
SSH_BACKUP = os.getenv("SSH_BACKUP") == "True"
SSH_USER = os.getenv("SSH_USER")
SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT"))
SSH_KEY = os.path.expanduser(os.getenv("SSH_KEY"))
SSH_DESTINATION = os.getenv("SSH_DESTINATION")
