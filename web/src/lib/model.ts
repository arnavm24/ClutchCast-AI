// Champion model runtime: StandardScaler + MLP (85 -> 64 -> ReLU -> 32 -> ReLU -> 1 -> sigmoid).
// Weights are exported from the trained PyTorch checkpoint by src/export_web_data.py.

export interface ModelLayer {
  weights: number[][];
  bias: number[];
}

export interface ModelBundle {
  championKey: string;
  championName: string;
  featureColumns: string[];
  scalerMean: number[];
  scalerScale: number[];
  layers: ModelLayer[];
  teamStrength: Record<string, number>;
}

function linear(input: number[], layer: ModelLayer): number[] {
  const out = new Array(layer.bias.length);
  for (let o = 0; o < layer.bias.length; o++) {
    let sum = layer.bias[o];
    const row = layer.weights[o];
    for (let i = 0; i < row.length; i++) sum += row[i] * input[i];
    out[o] = sum;
  }
  return out;
}

function relu(values: number[]): number[] {
  return values.map((v) => (v > 0 ? v : 0));
}

export function predictHomeWinProbability(bundle: ModelBundle, rawFeatures: number[]): number {
  const scaled = rawFeatures.map((v, i) => (v - bundle.scalerMean[i]) / bundle.scalerScale[i]);
  let x = scaled;
  for (let l = 0; l < bundle.layers.length; l++) {
    x = linear(x, bundle.layers[l]);
    if (l < bundle.layers.length - 1) x = relu(x);
  }
  return 1 / (1 + Math.exp(-x[0]));
}

export function featureVector(bundle: ModelBundle, record: Record<string, number>): number[] {
  return bundle.featureColumns.map((name) => record[name] ?? 0);
}
