import express from "express";
import { WebSocketServer } from "ws";
import speech from "@google-cloud/speech";
import Database from "better-sqlite3";

const app = express();
const PORT = process.env.PORT || 3000;

const db = new Database("transcripts.db");
db.exec(`
  CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sid TEXT,
    text TEXT,
    is_final INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

const insertTranscript = db.prepare(`
  INSERT INTO transcripts (call_sid, text, is_final)
  VALUES (?, ?, ?)
`);

const speechClient = new speech.SpeechClient();

app.post("/twilio/voice", (req, res) => {
  res.type("text/xml");
  res.send(`
    <Response>
      <Say>Hi, this call may be recorded and transcribed.</Say>
      <Connect>
        <Stream url="wss://YOUR_PUBLIC_URL/stream" />
      </Connect>
    </Response>
  `);
});

const server = app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

const wss = new WebSocketServer({ server, path: "/stream" });

wss.on("connection", (ws) => {
  console.log("Twilio connected");

  let callSid = null;

  const recognizeStream = speechClient
    .streamingRecognize({
      config: {
        encoding: "MULAW",
        sampleRateHertz: 8000,
        languageCode: "en-US",
        model: "phone_call",
      },
      interimResults: true,
    })
    .on("error", (err) => {
      console.error("Google STT error:", err);
    })
    .on("data", (data) => {
      const result = data.results?.[0];
      const transcript = result?.alternatives?.[0]?.transcript;

      if (!transcript) return;

      const isFinal = result.isFinal ? 1 : 0;

      console.log(isFinal ? "FINAL:" : "INTERIM:", transcript);

      insertTranscript.run(callSid, transcript, isFinal);
    });

  ws.on("message", (message) => {
    const msg = JSON.parse(message.toString());

    if (msg.event === "start") {
      callSid = msg.start.callSid;
      console.log("Call started:", callSid);
    }

    if (msg.event === "media") {
      const audio = Buffer.from(msg.media.payload, "base64");
      recognizeStream.write(audio);
    }

    if (msg.event === "stop") {
      console.log("Call stopped");
      recognizeStream.end();
    }
  });

  ws.on("close", () => {
    console.log("Twilio disconnected");
    recognizeStream.end();
  });
});