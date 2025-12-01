from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

print("Loaded key?", bool(key))

genai.configure(api_key=key)

model = genai.GenerativeModel("gemini-1.5-flash")

resp = model.generate_content("Hello!")
print(resp.text)
