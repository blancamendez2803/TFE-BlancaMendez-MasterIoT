#include <lmic.h>
#include <hal/hal.h>
#include <SPI.h>

// TTN keys
static const u1_t PROGMEM APPEUI[8] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
void os_getArtEui (u1_t* buf) { memcpy_P(buf, APPEUI, 8);}

static const u1_t PROGMEM DEVEUI[8] = { 0xDE, 0xC0, 0x06, 0xD0, 0x7E, 0xD5, 0xB3, 0x70 };
void os_getDevEui (u1_t* buf) { memcpy_P(buf, DEVEUI, 8);}

static const u1_t PROGMEM APPKEY[16] = { 0xFF, 0xFB, 0x07, 0x18, 0x84, 0x02, 0x29, 0x8B,
                                        0x39, 0x4D, 0x6B, 0x22, 0x86, 0xD5, 0x9E, 0xAF };
void os_getDevKey (u1_t* buf) { memcpy_P(buf, APPKEY, 16);}

// Fixed sensor values
const float FIXED_VALUES[] = {
    25,  // AHT10_1 temperature
    65,  // AHT10_1 humidity
    25,  // AHT10_2 temperature
    65,  // AHT10_2 humidity
    22,  // DS18B20_1 temperature
    22,  // DS18B20_2 temperature
    60,  // Light level 1
    60,  // Light level 2
    15,  // Soil moisture 1
    15   // Soil moisture 2
};
// LoRa settings
static osjob_t sendjob;
const unsigned TX_INTERVAL = 10;  // Transmission interval in seconds

// LoRa pins for TTGO board
const lmic_pinmap lmic_pins = {
    .nss = 18,
    .rxtx = LMIC_UNUSED_PIN,
    .rst = 23,
    .dio = {26, 33, 32}
};

// Counter for transmitted messages
unsigned long messageCount = 0;

void do_send(osjob_t* j) {
    // Check if there is not a current TX/RX job running
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
    } else {
        // Convert fixed float values to integers (multiply by 100 to preserve decimals)
        int values[10];
        for (int i = 0; i < 10; i++) {
            values[i] = (int)(FIXED_VALUES[i] * 100);
        }
        
        // Prepare payload
        byte payload[20];
        for (int i = 0; i < 10; i++) {
            payload[i*2] = (byte)(values[i] >> 8);    // High byte
            payload[i*2+1] = (byte)(values[i] & 0xFF); // Low byte
        }
        
        // Send payload
        LMIC_setTxData2(1, payload, sizeof(payload), 0);
        
        messageCount++;
    }
}

void onEvent (ev_t ev) {
    Serial.print(os_getTime());
    Serial.print(": ");
    switch(ev) {
        case EV_JOINED:
            Serial.println(F("EV_JOINED"));
            // Disable link check validation
            LMIC_setLinkCheckMode(0);
            // Set data rate and transmit power 
            LMIC_setDrTxpow(DR_SF7, 14);
            break;
        case EV_TXCOMPLETE:
            Serial.println(F("EV_TXCOMPLETE"));
            // Schedule next transmission
            os_setTimedCallback(&sendjob, os_getTime() + sec2osticks(TX_INTERVAL), do_send);
            break;
        case EV_JOIN_FAILED:
            Serial.println(F("EV_JOIN_FAILED"));
            break;
        case EV_TXSTART:
            Serial.println(F("EV_TXSTART"));
            break;
        default:
            Serial.printf("Unknown event: %d\n", (unsigned) ev);
            break;
    }
}

void setup() {
    Serial.begin(115200);
    Serial.println(F("Starting"));
    
    // LMIC init
    os_init();
    
    // Reset the MAC state. Session and pending data transfers will be discarded
    LMIC_reset();
    
    // Allow for clock variance
    LMIC_setClockError(MAX_CLOCK_ERROR * 5 / 100);
    
    // Start job (sending automatically starts OTAA too)
    do_send(&sendjob);
}

void loop() {
    os_runloop_once();
}