import { generateSpeech } from "./gradium.js";
import { generateResponse } from "./agent.js";

async function run() {
  const userInput = "I had a billing issue";

  const response = generateResponse(userInput);

  console.log("AI says:", response);

  const audioFile = await generateSpeech(response);

  console.log("Saved:", audioFile);
}

run();