// Verifies the TypeScript model runtime reproduces the PyTorch champion.
// Run: node scripts/parity.ts  (from web/, after src/export_web_data.py)

import { readFileSync } from "fs";
import path from "path";
import { predictHomeWinProbability } from "../src/lib/model.ts";
import type { ModelBundle } from "../src/lib/model.ts";

const dataDir = path.join(process.cwd(), "public", "data");
const bundle = JSON.parse(readFileSync(path.join(dataDir, "model.json"), "utf-8")) as ModelBundle;
const vectors = JSON.parse(readFileSync(path.join(dataDir, "test_vectors.json"), "utf-8")) as {
  gameId: string;
  vectors: { features: number[]; expected: number }[];
};

let worst = 0;
for (const [index, vector] of vectors.vectors.entries()) {
  const predicted = predictHomeWinProbability(bundle, vector.features);
  const diff = Math.abs(predicted - vector.expected);
  worst = Math.max(worst, diff);
  console.log(
    `vector ${index}: ts=${predicted.toFixed(6)} torch=${vector.expected.toFixed(6)} diff=${diff.toExponential(2)}`,
  );
}

if (worst > 1e-4) {
  console.error(`PARITY FAILED — worst diff ${worst}`);
  process.exit(1);
}
console.log(`PARITY OK — ${vectors.vectors.length} vectors from game ${vectors.gameId}, worst diff ${worst.toExponential(2)}`);
