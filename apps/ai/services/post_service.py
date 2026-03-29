from apps.ai.services.llm_service import AIService

system_prompt = """
You are an expert social media strategist AI.

You help users create and refine posts conversationally.

---

CAPABILITIES:
- Generate full posts
- Improve captions
- Rewrite hooks
- Suggest hashtags

---

PLATFORM RULES:

LinkedIn:
- 80–150 words
- Professional tone
- Clear spacing

Instagram:
- 40–100 words
- Casual, engaging

YouTube:
- Informative, slightly longer

---

INTENT HANDLING:

- If user asks for full post → generate all fields
- If user asks for caption only → fill caption, leave others empty
- If user asks for hook → modify hook only
- If user asks for hashtags → return only hashtags

---

CONTENT QUALITY RULES:

- Avoid generic phrases like:
  "In today's world", "Unlock your potential"

- Hooks must be specific and engaging

- Caption must be structured and readable

- Hashtags must be relevant

---

STRICT OUTPUT FORMAT:

Return ONLY JSON:

{
  "hook": "string",
  "caption": "string",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "format": "post"
}

---

GUARDRAIL:

If user asks unrelated question:

{
  "hook": "",
  "caption": "I can only help with social media content creation.",
  "hashtags": [],
  "format": "post"
}
"""


class PostService:

    def __init__(self):
        self.ai = AIService()

    def generate_post(self, history, platform, tone, audience):

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        result = self.ai.chat_json(messages) or {}

        hook = (result.get("hook") or "").strip()
        caption = (result.get("caption") or "").strip()
        hashtags = result.get("hashtags")

        if not isinstance(hashtags, list):
            hashtags = []

        hashtags = [h.strip() for h in hashtags if isinstance(h, str)]

        # Ensure UI always gets usable text, even for hook-only/hashtags-only intents.
        if not caption and hook:
            caption = hook

        if not caption and hashtags:
            caption = "Suggested hashtags: " + " ".join(hashtags[:5])

        if not hook and caption:
            # Keep hook non-empty for components that display it prominently.
            hook = caption[:120].strip()

        if not caption:
            caption = (
                "I can help with hooks, captions, hashtags, and rewrites. "
                "Try: 'Write a YouTube caption about Python for beginners.'"
            )

        return {
            "hook": hook,
            "caption": caption,
            "hashtags": hashtags[:5],
            "format": "post",
        }
