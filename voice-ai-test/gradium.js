import WebSocket from "ws";
import fs from "fs";

export function generateSpeech(text) {
  return new Promise((resolve) => {
    const ws = new WebSocket("wss://api.gradium.ai/api/speech/tts", {
      headers: {
        "x-api-key": "Bearer YOUR_API_KEY"
      }
    });

    let audioChunks = [];

    ws.on("open", () => {
      ws.send(JSON.stringify({
        text,
        voice_id: "7c5UOKm7AiBgJADg",
        json_config: {
          temp: 0.6
        }
      }));
    });

    ws.on("message", (data) => {
      const chunk = JSON.parse(data);

      if (chunk.audio) {
        audioChunks.push(Buffer.from(chunk.audio, "base64"));
      }

      if (chunk.isFinal) {
        const finalAudio = Buffer.concat(audioChunks);
        fs.writeFileSync("output.wav", finalAudio);
        resolve("output.wav");
      }
    });
  });
}