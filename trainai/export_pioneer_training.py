import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("PIONEER_API_KEY"),
    base_url="https://api.pioneer.ai/v1"
)

response = client.chat.completions.create(
    model="insurance-assistant-v1",
    messages=[
        {
            "role": "system",
            "content": "You are a professional insurance customer service assistant."
        },
        {
            "role": "user",
            "content": "My car was hit yesterday. How do I start a claim?"
        }
    ]
)

print(response.choices[0].message.content)