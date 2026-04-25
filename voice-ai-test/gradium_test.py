import asyncio
import os
import gradium
from dotenv import load_dotenv

load_dotenv()

async def main():
    client = gradium.client.GradiumClient(
        api_key=os.getenv("GRADIUM_API_KEY")
    )

    text = "Hmm... okay. I understand. So you had a billing issue, right?"

    result = await client.tts(
        setup={
            "model_name": "default",
            "voice_id": "7c5UOKm7AiBgJADg",
            "output_format": "wav"
        },
        text=text
    )

    with open("output.wav", "wb") as f:
        f.write(result.raw_data)

    print("Saved output.wav")
    print(f"Sample rate: {result.sample_rate}")
    print(f"Request ID: {result.request_id}")

asyncio.run(main())