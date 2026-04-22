import os
import json
from openai import OpenAI

# Paths
CONFIG_PATH = "ai_config.json"

# Defaults
API_KEY = os.environ.get("OVH_AI_ENDPOINTS_ACCESS_TOKEN", "")
AI_MODEL_NAME = "gpt-oss-120b"

# Load config
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r") as f:
            ai_cfg = json.load(f)
            API_KEY = ai_cfg.get("OVH_AI_ENDPOINTS_ACCESS_TOKEN", API_KEY)
            AI_MODEL_NAME = ai_cfg.get("AI_MODEL_NAME", AI_MODEL_NAME)
            print(f"Loaded config: Model={AI_MODEL_NAME}, Key={'SET' if API_KEY and API_KEY != 'YOUR_OVH_TOKEN_HERE' else 'NOT SET / DUMMY'}")
    except Exception as e:
        print(f"Error loading config: {e}")

if not API_KEY or API_KEY == "YOUR_OVH_TOKEN_HERE":
    print("WARNING: OVH Access Token is not set or is using the dummy placeholder 'YOUR_OVH_TOKEN_HERE'.")
    print("The API request will likely fail.")

try:
    print("Initializing OpenAI client for OVH endpoint...")
    client = OpenAI(
        base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        api_key=API_KEY
    )

    print(f"Testing completion with model '{AI_MODEL_NAME}'...")
    response = client.chat.completions.create(
        model=AI_MODEL_NAME,
        messages=[{"role": "user", "content": "Hello! Say exactly 'Working!' if you are ready."}],
        temperature=0.15
    )

    result_text = response.choices[0].message.content.strip()
    print("\n--- AI Response ---")
    print(result_text)
    print("-------------------\n")
    print("SUCCESS: Model is working!")

except Exception as e:
    print(f"\nERROR: Failed to test model. Exception details:")
    print(e)
