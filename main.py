import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

client = OpenAI(
    api_key=os.environ["PORTKEY_API_KEY"],
    base_url="https://api.portkey.ai/v1",
    default_headers={"x-portkey-provider": "openai"},
)
response = client.responses.create(
    model="gpt-6-luna",
    input="Your prompt here",
)
print(response.output_text)
