"""Test which Gemini models work on free tier."""

import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import pip_system_certs  # noqa: F401
except ImportError:
    pass

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
key = os.getenv("GEMINI_API_KEY", "").strip()

from google import genai
from google.genai import types

client = genai.Client(api_key=key)

models = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]

print("=== FREE TIER MODEL TEST ===\n")
for model in models:
    try:
        r = client.models.generate_content(
            model=model,
            contents="Reply with exactly: OK",
            config=types.GenerateContentConfig(temperature=0.0),
        )
        print(f"{model:30} PASS  -> {(r.text or '').strip()[:40]}")
    except Exception as e:
        err = str(e)
        if "429" in err:
            print(f"{model:30} 429   -> quota exhausted (limit may be 0)")
        elif "404" in err or "NOT_FOUND" in err:
            print(f"{model:30} 404   -> model not found / deprecated")
        elif "401" in err or "403" in err:
            print(f"{model:30} AUTH  -> invalid credentials")
        else:
            print(f"{model:30} FAIL  -> {type(e).__name__}: {err[:80]}")
