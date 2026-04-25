import WebSocket from "ws";
import fs from "fs";
import { exec } from "child_process";

export function generateSpeech(text) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket("wss://eu.api.gradium.ai/api/speech/tts", {
      headers: {
        "x-api-key": "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
      }
    });

    let audioChunks = [];

    ws.on("open", () => {
      console.log("Connected to Gradium");

      ws.send(JSON.stringify({
        type: "speak",
        text: text,
        voice_id: "7c5U0Km7AiBgJADg",
        output_format: "wav",
        sample_rate: 48000,
        json_config: {
          speed: 1.0,
          temp: 0.6
        }
      }));
    });

    ws.on("message", (data) => {
      console.log("Received message from Gradium");
      console.log("Raw message:", data.toString());

      const message = JSON.parse(data.toString());

      if (message.audio) {
        audioChunks.push(Buffer.from(message.audio, "base64"));
      }

      if (message.isFinal || message.done) {
        const finalAudio = Buffer.concat(audioChunks);

        fs.writeFileSync("output.wav", finalAudio);

        console.log("Audio saved as output.wav");

        exec("afplay output.wav");

        resolve("output.wav");
      }
    });

    ws.on("error", (error) => {
      console.error("Gradium WebSocket error:", error.message);
      reject(error);
    });

    ws.on("close", () => {
      console.log("Gradium connection closed");
    });
  });
}