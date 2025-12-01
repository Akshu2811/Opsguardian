# list_models.py
from dotenv import load_dotenv
import os
from google.genai import Client

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

print("\n=== RUNNING model list (using google.genai) ===")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not found in environment/.env")
    raise SystemExit(1)

client = Client(api_key=api_key)

try:
    pager = client.models.list()
    print("\n=== AVAILABLE GENAI MODELS ===")
    count = 0
    for m in pager:  # iterate the Pager
        count += 1
        # defensive field extraction
        name = getattr(m, "name", None) or getattr(m, "model", None) or str(m)
        methods = getattr(m, "supported_generation_methods", None)
        # some model objects show supported_methods or supported_generation_methods
        if methods is None:
            methods = getattr(m, "supported_methods", None)
        # print a short summary plus full repr for debugging
        print(f"\n[{count}] MODEL NAME: {name}")
        print("    supported_generation_methods:", methods)
        try:
            print("    repr:", repr(m)[:1000])  # avoid too long output
        except Exception:
            pass

    if count == 0:
        print("No models returned by the API call.")
except Exception as e:
    print("ERROR listing models:", repr(e))
    raise
