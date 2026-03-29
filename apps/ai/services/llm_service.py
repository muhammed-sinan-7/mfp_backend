import json
import logging

from django.conf import settings
from groq import Groq

logger = logging.getLogger(__name__)


class AIService:

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY, timeout=10)
        self.model = "llama-3.1-8b-instant"

    def chat(self, messages):

        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, temperature=0.5, max_tokens=500
                )

                text = response.choices[0].message.content.strip()
                return {"response": text}

            except Exception:
                logger.warning("Retrying...", exc_info=True)

        return {"response": ""}

    def chat_json(self, messages):

        raw = self.chat(messages)

        try:
            text = raw.get("response", "")

            text = text.replace("```json", "").replace("```", "")

            start = text.find("{")
            end = text.rfind("}")

            if start == -1 or end == -1:
                return {}

            json_str = text[start : end + 1]

            return json.loads(json_str)

        except Exception:
            return {}
