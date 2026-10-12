"""Single shared place for model configuration.

Every agent in backend/agents.py imports MODEL from here. This is the only
file that should ever construct a model or know a model name - if you want
to confirm no other model slipped in anywhere, grep the rest of backend/
for "gpt-" or "OpenAIResponsesModel" and this file should be the only hit.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

# backend/model.py -> backend/ -> this project's root .env (keeps the repo
# self-contained for anyone cloning it standalone - see .env.example/README.md).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL_NAME = "gpt-6-luna"


def _build_model() -> OpenAIResponsesModel:
    client = AsyncOpenAI(
        api_key=os.environ["PORTKEY_API_KEY"],
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
        max_retries=0,
    )
    # OpenAIResponsesModel uses the Responses API (client.responses.create),
    # the same call pattern Portkey + Luna is validated against for this project.
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


MODEL = _build_model()
