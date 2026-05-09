# Project notes for coding agents

## Gemini SDK: Vertex AI mode only

This project uses the `google-genai` SDK in **Vertex AI mode** (not the Gemini Developer API). Vertex mode gives us Zero Data Retention (ZDR); do not replace it with `api_key=...`.

- Always obtain the client through `get_genai_client()` in [app/routes/main.py](app/routes/main.py) — it handles the `genai.Client(vertexai=True, project=..., location=...)` construction and missing-config logging.
- Vertex config (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`) lives in [config.py](config.py).
- The `gemini-api-dev` skill in [.claude/skills/gemini-api-dev/SKILL.md](.claude/skills/gemini-api-dev/SKILL.md) documents current models and SDK best practices. Its examples default to the Developer API constructor — translate them to the Vertex constructor above. The rest of the API surface (`generate_content`, streaming, tool use, prompt caching, structured output) is identical between the two modes.
