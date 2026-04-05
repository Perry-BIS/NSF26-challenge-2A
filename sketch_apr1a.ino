#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;

const int SENSOR_COUNT = 4;
const int MOVING_WINDOW = 8;
const float BASELINE_ALPHA = 0.02f;
const float ADAPTIVE_ALPHA = 0.05f;
const float KALMAN_Q = 0.01f;
const float KALMAN_R = 0.12f;

float history[SENSOR_COUNT][MOVING_WINDOW];
float baseline[SENSOR_COUNT] = {0, 0, 0, 0};
float adaptiveMean[SENSOR_COUNT] = {0, 0, 0, 0};
float adaptiveVar[SENSOR_COUNT] = {0, 0, 0, 0};
float kalmanEstimate[SENSOR_COUNT] = {0, 0, 0, 0};
float kalmanError[SENSOR_COUNT] = {1, 1, 1, 1};
float previousRaw[SENSOR_COUNT] = {0, 0, 0, 0};
bool initialized[SENSOR_COUNT] = {false, false, false, false};

int historyIndex = 0;
unsigned long sampleCount = 0;
int displayMode = 1;

float computeMovingAverage(int sensorIndex) {
  float sum = 0.0f;
  int validCount = min((unsigned long)MOVING_WINDOW, sampleCount + 1);
  for (int i = 0; i < validCount; i++) {
    sum += history[sensorIndex][i];
  }
  return sum / max(validCount, 1);
}

float updateKalman(int sensorIndex, float measurement) {
  kalmanError[sensorIndex] += KALMAN_Q;
  float gain = kalmanError[sensorIndex] / (kalmanError[sensorIndex] + KALMAN_R);
  kalmanEstimate[sensorIndex] += gain * (measurement - kalmanEstimate[sensorIndex]);
  kalmanError[sensorIndex] = (1.0f - gain) * kalmanError[sensorIndex];
  return kalmanEstimate[sensorIndex];
}

float updateAdaptiveActivation(int sensorIndex, float measurement) {
  adaptiveMean[sensorIndex] = (1.0f - ADAPTIVE_ALPHA) * adaptiveMean[sensorIndex] + ADAPTIVE_ALPHA * measurement;
  float delta = measurement - adaptiveMean[sensorIndex];
  adaptiveVar[sensorIndex] = (1.0f - ADAPTIVE_ALPHA) * adaptiveVar[sensorIndex] + ADAPTIVE_ALPHA * delta * delta;
  float sigma = sqrt(max(adaptiveVar[sensorIndex], 0.000001f));
  float adaptiveThreshold = adaptiveMean[sensorIndex] + 1.8f * sigma;
  return max(0.0f, measurement - adaptiveThreshold);
}

const char* classifyFingerprint(float normalizedSignals[SENSOR_COUNT], float derivatives[SENSOR_COUNT]) {
  float alcoholScore =
    1.25f * normalizedSignals[0] +
    0.55f * normalizedSignals[1] +
    0.20f * max(derivatives[0], 0.0f);

  float smokeScore =
    1.05f * normalizedSignals[2] +
    1.00f * normalizedSignals[3] +
    0.35f * normalizedSignals[1] +
    0.15f * max(derivatives[2], 0.0f);

  float airQualityScore =
    1.20f * normalizedSignals[1] +
    0.35f * normalizedSignals[2] +
    0.20f * normalizedSignals[3];

  if (alcoholScore < 1.8f && smokeScore < 1.8f && airQualityScore < 1.8f) {
    return "STABLE";
  }
  if (alcoholScore >= smokeScore && alcoholScore >= airQualityScore) {
    return "ALCOHOL";
  }
  if (smokeScore >= alcoholScore && smokeScore >= airQualityScore) {
    return "SMOKE";
  }
  return "AIR";
}

void setup(void) {
  Serial.begin(115200);
  ads.begin(0x48);
  ads.setGain(GAIN_TWOTHIRDS);
  Serial.println("Ready. Commands 1-6 switch algorithm label, output stays raw for Python.");
}

void loop(void) {
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c >= '1' && c <= '6') {
      displayMode = c - '0';
    }
  }

  float raw[SENSOR_COUNT];
  float processed[SENSOR_COUNT];
  float movingAvg[SENSOR_COUNT];
  float kalman[SENSOR_COUNT];
  float baselineCorrected[SENSOR_COUNT];
  float adaptiveActivation[SENSOR_COUNT];
  float derivative[SENSOR_COUNT];
  float normalized[SENSOR_COUNT];

  for (int i = 0; i < SENSOR_COUNT; i++) {
    raw[i] = ads.computeVolts(ads.readADC_SingleEnded(i));

    if (!initialized[i]) {
      baseline[i] = raw[i];
      adaptiveMean[i] = raw[i];
      adaptiveVar[i] = 0.01f;
      kalmanEstimate[i] = raw[i];
      previousRaw[i] = raw[i];
      for (int j = 0; j < MOVING_WINDOW; j++) {
        history[i][j] = raw[i];
      }
      initialized[i] = true;
    }

    history[i][historyIndex] = raw[i];
    movingAvg[i] = computeMovingAverage(i);
    kalman[i] = updateKalman(i, raw[i]);

    baseline[i] = (1.0f - BASELINE_ALPHA) * baseline[i] + BASELINE_ALPHA * raw[i];
    baselineCorrected[i] = raw[i] - baseline[i];

    adaptiveActivation[i] = updateAdaptiveActivation(i, raw[i]);
    derivative[i] = raw[i] - previousRaw[i];

    float sigma = sqrt(max(adaptiveVar[i], 0.000001f));
    normalized[i] = max(0.0f, (raw[i] - adaptiveMean[i]) / sigma);

    switch (displayMode) {
      case 1:
        processed[i] = baselineCorrected[i];
        break;
      case 2:
        processed[i] = movingAvg[i];
        break;
      case 3:
        processed[i] = kalman[i];
        break;
      case 4:
        processed[i] = adaptiveActivation[i];
        break;
      case 5:
        processed[i] = derivative[i];
        break;
      case 6:
        processed[i] = normalized[i];
        break;
      default:
        processed[i] = raw[i];
        break;
    }

    previousRaw[i] = raw[i];
  }

  float fusedSignals[SENSOR_COUNT];
  fusedSignals[0] = 0.55f * normalized[0] + 0.25f * normalized[1];
  fusedSignals[1] = 0.20f * normalized[0] + 0.50f * normalized[1] + 0.15f * normalized[2];
  fusedSignals[2] = 0.10f * normalized[0] + 0.20f * normalized[1] + 0.45f * normalized[2] + 0.25f * normalized[3];
  fusedSignals[3] = 0.10f * normalized[0] + 0.15f * normalized[1] + 0.30f * normalized[2] + 0.45f * normalized[3];

  const char* fingerprint = classifyFingerprint(normalized, derivative);

  Serial.print("MQ3:");
  Serial.print(raw[0], 4);
  Serial.print(",MQ135:");
  Serial.print(raw[1], 4);
  Serial.print(",MQ2:");
  Serial.print(raw[2], 4);
  Serial.print(",MQ9:");
  Serial.print(raw[3], 4);
  Serial.print(",MODE:");
  Serial.print(displayMode);
  Serial.print(",ACTIVE_MQ3:");
  Serial.print(processed[0], 4);
  Serial.print(",ACTIVE_MQ135:");
  Serial.print(processed[1], 4);
  Serial.print(",ACTIVE_MQ2:");
  Serial.print(processed[2], 4);
  Serial.print(",ACTIVE_MQ9:");
  Serial.print(processed[3], 4);
  Serial.print(",FPRINT:");
  Serial.print(fingerprint);
  Serial.print(",FUSED_MQ3:");
  Serial.print(fusedSignals[0], 3);
  Serial.print(",FUSED_MQ135:");
  Serial.print(fusedSignals[1], 3);
  Serial.print(",FUSED_MQ2:");
  Serial.print(fusedSignals[2], 3);
  Serial.print(",FUSED_MQ9:");
  Serial.println(fusedSignals[3], 3);

  historyIndex = (historyIndex + 1) % MOVING_WINDOW;
  sampleCount++;
  delay(100);
}
