#include <lmic.h>
#include <hal/hal.h>
#include <Adafruit_AHTX0.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "esp_sleep.h"

// OLED display settings
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Pin definitions for sensors
#define LDR_PIN 36     // GPIO36 (ADC1_CH0) for LDR sensor
#define DS18B20_PIN 4  // GPIO4 for temperature sensor
#define SOIL_PIN 35    // GPIO34 for soil moisture sensor

// TTN keys - Replace with your own values
static const u1_t PROGMEM APPEUI[8] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
void os_getArtEui (u1_t* buf) { memcpy_P(buf, APPEUI, 8);}
static const u1_t PROGMEM DEVEUI[8] = { 0xDE, 0xC0, 0x06, 0xD0, 0x7E, 0xD5, 0xB3, 0x70 };
void os_getDevEui (u1_t* buf) { memcpy_P(buf, DEVEUI, 8);}
static const u1_t PROGMEM APPKEY[16] = { 0xFF, 0xFB, 0x07, 0x18, 0x84, 0x02, 0x29, 0x8B,
                                        0x39, 0x4D, 0x6B, 0x22, 0x86, 0xD5, 0x9E, 0xAF };
void os_getDevKey (u1_t* buf) { memcpy_P(buf, APPKEY, 16);}

// Sleep settings
const unsigned long SLEEP_TIME = 43200000; // 20 seconds (20000) or 12 hours (43200000) in milliseconds

// Soil moisture sensor calibration values
const int AirValue = 3200;   // Sensor value in dry soil
const int WaterValue = 0;    // Sensor value in water

// LoRa settings
static osjob_t sendjob;
bool txComplete = false;

// LoRa pins for TTGO board
const lmic_pinmap lmic_pins = {
    .nss = 18,
    .rxtx = LMIC_UNUSED_PIN,
    .rst = 23,
    .dio = {26, 33, 32}
};

// Create objects for sensors and display
Adafruit_AHTX0 aht;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
OneWire oneWire(DS18B20_PIN);
DallasTemperature DS18B20_sensor(&oneWire);
float tempC;

// Variables for sensor readings
sensors_event_t humidity, temp;
int lightLevel, soilMoisture;

// Function to update OLED display
void updateDisplay(String line1, String line2, String line3, String line4, String line5) {
  display.clearDisplay();
  display.setCursor(0,0);
  display.println(line1);
  display.println(line2);
  display.println(line3);
  display.println(line4);
  display.println(line5);
  display.display();
}

// Function to read LDR sensor
int readLDR() {
  int rawValue = analogRead(LDR_PIN);
  int percentage = map(rawValue, 0, 4095, 0, 100);
  return percentage;
}

// Function to read soil moisture sensor
int readSoilMoisture() {
  int soilMoistureValue = analogRead(SOIL_PIN);
  int humidity = map(soilMoistureValue, WaterValue, AirValue, 0, 100);
  humidity = constrain(humidity, 0, 100);
  humidity = 100 - humidity;
  return humidity;
}

// Function to read all sensors
void readSensors() {
  aht.getEvent(&humidity, &temp);
  DS18B20_sensor.requestTemperatures();
  tempC = DS18B20_sensor.getTempCByIndex(0);
  lightLevel = readLDR();
  soilMoisture = readSoilMoisture();
}

// Function to go to sleep
void goToSleep() {
  updateDisplay("Going to sleep", "for 20 seconds", "", "", "");
  delay(2000);  // Give time to see the message
  display.clearDisplay();
  display.display();
  
  // Enable timer wakeup
  esp_sleep_enable_timer_wakeup(SLEEP_TIME * 1000); // Convert to microseconds
  
  // Go to sleep
  esp_deep_sleep_start();
}

void do_send(osjob_t* j) {
  if (LMIC.opmode & OP_TXRXPEND) {
    updateDisplay("TTN Status", "Busy - waiting", "", "", "");
  } 
  else {
    readSensors();
    
    // Convert float values to int preserving 2 decimal places
    int temp_aht = (int)(temp.temperature * 100);
    int hum_aht = (int)(humidity.relative_humidity * 100);
    int temp_ds = (int)(tempC * 100);
    int light = (int)(lightLevel * 100);
    int soil = (int)(soilMoisture * 100);
    
    // Prepare payload
    byte payload[10];
    payload[0] = (byte)(temp_aht / 256);
    payload[1] = (byte)(temp_aht % 256);
    payload[2] = (byte)(hum_aht / 256);
    payload[3] = (byte)(hum_aht % 256);
    payload[4] = (byte)(temp_ds / 256);
    payload[5] = (byte)(temp_ds % 256);
    payload[6] = (byte)(light / 256);
    payload[7] = (byte)(light % 256);
    payload[8] = (byte)(soil / 256);
    payload[9] = (byte)(soil % 256);
    
    LMIC_setTxData2(1, payload, sizeof(payload), 0);
    
    String tempAhtStr = "AHT10 Temp: " + String(temp.temperature, 2) + " C";
    String tempDsStr = "DS18B20 Temp: " + String(tempC, 2) + " C";
    String humStr = "AHT10 Hum: " + String(humidity.relative_humidity, 2) + "%";
    String lightStr = "Light level: " + String(lightLevel, 2) + "%";
    String soilStr = "Soil moist: " + String(soilMoisture, 2) + "%";
    
    updateDisplay(tempAhtStr, tempDsStr, humStr, lightStr, soilStr);
  }
}

void onEvent (ev_t ev) {
  switch(ev) {
    case EV_JOINING:
      updateDisplay("TTN Status", "Joining...", "", "", "");
      break;
      
    case EV_JOINED:
      updateDisplay("TTN Status", "Joined!", "", "", "");
      LMIC_setLinkCheckMode(0);
      LMIC_setDrTxpow(DR_SF7, 14);
      break;
      
    case EV_JOIN_FAILED:
      updateDisplay("TTN Status", "Join failed", "", "", "");
      break;
      
    case EV_TXCOMPLETE:
      updateDisplay("TTN Status", "Tx complete", "", "", "");
      txComplete = true;  // Set flag to indicate transmission is complete
      break;
      
    case EV_TXSTART:
      updateDisplay("TTN Status", "Starting Tx", "", "", "");
      break;
      
    default:
      updateDisplay("TTN Status", "Unknown event", String((unsigned)ev), "", "");
      break;
  }
}

void setup() {
  Serial.begin(115200);
  
  analogReadResolution(12);
  DS18B20_sensor.begin();
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  
  if (!aht.begin()) {
    updateDisplay("Sensor error", "AHT10 not found!", "Check wiring!", "", "");
    Serial.println("Could not find AHT10 sensor!");
    while (1) delay(10);
  }
  
  os_init();
  LMIC_reset();
  LMIC_setClockError(MAX_CLOCK_ERROR * 5 / 100);
  
  // Start job (sending automatically starts OTAA too)
  do_send(&sendjob);
}

void loop() {
  os_runloop_once();
  
  // If transmission is complete, go to sleep
  if (txComplete) {
    goToSleep();
  }
}