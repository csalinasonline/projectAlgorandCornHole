// INCLUDES ===
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <SoftwareSerial.h>
#include <Wire.h>
#include <Adafruit_NeoPixel.h>
#ifdef __AVR__
 #include <avr/power.h> // Required for 16 MHz Adafruit Trinket
#endif

// DEFINES ===
// Which pin on the Arduino is connected to the NeoPixels?
// On a Trinket or Gemma we suggest changing this to 1:
#define LED_PIN    11
#define ECHO_PIN   2 // attach pin D2 Arduino to pin Echo of HC-SR04
#define TRIG_PIN   3 // attach pin D3 Arduino to pin Trig of HC-SR04

//
#define ARDUINO_RX 9  //should connect to TX of the Serial MP3 Player module
#define ARDUINO_TX 10  //connect to RX of the module

#define ARDUINO_RX2 5  //should connect to TX of the BLE module
#define ARDUINO_TX2 6  //connect to RX of the module

//
#define CMD_NEXT_SONG     0X01  // Play next song.
#define CMD_PREV_SONG     0X02  // Play previous song.
#define CMD_PLAY_W_INDEX  0X03
#define CMD_VOLUME_UP     0X04
#define CMD_VOLUME_DOWN   0X05
#define CMD_SET_VOLUME    0X06

#define CMD_SNG_CYCL_PLAY 0X08  // Single Cycle Play.
#define CMD_SEL_DEV       0X09
#define CMD_SLEEP_MODE    0X0A
#define CMD_WAKE_UP       0X0B
#define CMD_RESET         0X0C
#define CMD_PLAY          0X0D
#define CMD_PAUSE         0X0E
#define CMD_PLAY_FOLDER_FILE 0X0F

#define CMD_STOP_PLAY     0X16
#define CMD_FOLDER_CYCLE  0X17
#define CMD_SHUFFLE_PLAY  0x18 //
#define CMD_SET_SNGL_CYCL 0X19 // Set single cycle.

#define CMD_SET_DAC 0X1A
#define DAC_ON  0X00
#define DAC_OFF 0X01

#define CMD_PLAY_W_VOL    0X22
#define CMD_PLAYING_N     0x4C
#define CMD_QUERY_STATUS      0x42
#define CMD_QUERY_VOLUME      0x43
#define CMD_QUERY_FLDR_TRACKS 0x4e
#define CMD_QUERY_TOT_TRACKS  0x48
#define CMD_QUERY_FLDR_COUNT  0x4f

#define DEV_TF            0X02

// How many NeoPixels are attached to the Arduino?
#define LED_COUNT 150

//
#define NODE_NAME 'O'
#define NODE_TYPE "BRD"

// GLOBALS ===

// Declare our NeoPixel strip object:
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// imu obj
Adafruit_MPU6050 mpu;

// threshold variables accelerometer
int i = 0;
float delta = 0;
float v1 = 0;
float v2 = 0;
int lock = 0;

// more threshold variables for ultrasone
long duration; // variable for the duration of sound wave travel
int distance;  // variable for the distance measurement

// serial coms to mp3 player
SoftwareSerial mp3(ARDUINO_RX, ARDUINO_TX);
// serial coms to bluetooth paired serial module
SoftwareSerial com(ARDUINO_RX2, ARDUINO_TX2); // RX, TX

// mp3 player globals
static int8_t Send_buf[8] = {0}; // Buffer for Send commands.  // BETTER LOCALLY
static uint8_t ansbuf[10] = {0}; // Buffer for the answers.    // BETTER LOCALLY
String mp3Answer;           // Answer from the MP3.

// save random numebr
long randNumber;

// SETUP ===

void setup() {
  // These lines are specifically to support the Adafruit Trinket 5V 16 MHz.
  // Any other board, you can remove this part (but no harm leaving it):
  // (ADAFRUIT)
#if defined(__AVR_ATtiny85__) && (F_CPU == 16000000)
  clock_prescale_set(clock_div_1);
#endif
  // END of Trinket-specific code.

  // setup IO for ultrasonic
  pinMode(TRIG_PIN, OUTPUT); // sets the trigPin as an OUTPUT
  pinMode(ECHO_PIN, INPUT);  // sets the echoPin as an INPUT  

  // setup mp3 player
  mp3.begin(9600);
  delay(500);
  sendCommand(CMD_SEL_DEV, DEV_TF);
  delay(500);
  randomSeed(analogRead(0));  

  // setup bluetooth paried serial
  com.begin(9600);
  delay(500);

  // Init the IMU
  if (!mpu.begin()) {
    while (1) {
      delay(10);
    }
  }

  // setup IMU
  mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
  mpu.setGyroRange(MPU6050_RANGE_250_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_5_HZ);

  // gimme some delay
  delay(100);  

  // setup RGB LED Addressable light strip
  strip.begin();           // INITIALIZE NeoPixel strip object (REQUIRED)
  strip.show();            // Turn OFF all pixels ASAP
  strip.setBrightness(255); // Set BRIGHTNESS to about 1/5 (max = 255)
}


// LOOP ===

void loop() {

  // accel thresholding
  float ax,ay, az;
  float threshold = 0.08;
  float threshold_hole = 20;

  // Clears the trigPin condition
  digitalWrite(TRIG_PIN, LOW);

  // Get new sensor events with the readings 
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  // get latest accel
  ax = a.acceleration.x;
  ay = a.acceleration.y;
  az = a.acceleration.z;

  // get magnitude of all componets
  float mag = sqrt( ax*ax + ay*ay + az*az ); 

  // threshold accel
  if( i == 0 ) {
    v1 = mag;
    i++;
  } else if( i == 1 ) {
    v2 = mag;
    i++;
  } else {
    delta = abs(v2-v1);
    i = 0;
  }

  // start ultrasonic measurement
  // Sets the trigPin HIGH (ACTIVE) for 10 microseconds
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  // Reads the TRIG_PIN, returns the sound wave travel time in microseconds
  duration = pulseIn(ECHO_PIN, HIGH);
  // Calculating the distance
  distance = duration * 0.034 / 2; // Speed of sound wave divided by 2 (go and back)

  // gimme some delay
  delay(10);
  
  // 1st priority hole trigger
  if( distance < threshold_hole ) {
    if( lock == 1 ) {
      // CornHole!
      sendMP3Command('w');
      colorWipe(strip.Color(  255,   0, 0), 1); // Red
      colorWipe(strip.Color(  0,   255, 0), 1); // Green
      colorWipe(strip.Color(  255,   0, 0), 1); // Red
      colorWipe(strip.Color(  0,   255, 0), 1); // Green
      colorWipe(strip.Color(  255,   0, 0), 1); // Red
      colorWipe(strip.Color(  0,   255, 0), 1); // Green
      lock = 0;

      // send serial msg to bluetooth serial
      com.print(NODE_TYPE);
      com.print(",");       
      com.print(NODE_NAME);
      com.print(",");      
      com.print(millis());
      com.print(",");
      com.println(3);  
    }    
  } else if( delta > threshold ) {  // 2nd priority detect hit trigger
    if( lock == 1 ) {
      // Woody!
      sendMP3Command('l');
      theaterChaseRainbow(30); 
      lock = 0;

      // ...
      com.print(NODE_TYPE);
      com.print(",");        
      com.print(NODE_NAME);
      com.print(",");
      com.print(millis());
      com.print(",");
      com.println(1);      
    }
  } else {  // idle 
    if( lock == 0 ) {
      // boring
      colorWipe(strip.Color(  0,   0, 255), 1); // Blue
      lock = 1;
    }
  }
}

// FUNCTIONS ===

// led color wipe 
// (ADAFRUIT)
void colorWipe(uint32_t color, int wait) {
  for(int i=0; i<strip.numPixels(); i++) { // For each pixel in strip...
    strip.setPixelColor(i, color);         //  Set pixel's color (in RAM)
    strip.show();                          //  Update strip to match
    delay(wait);                           //  Pause for a moment
  }
}

// Theater-marquee-style chasing lights. Pass in a color (32-bit value,
// a la strip.Color(r,g,b) as mentioned above), and a delay time (in ms)
// between frames.
// (ADAFRUIT)
void theaterChase(uint32_t color, int wait) {
  for(int a=0; a<10; a++) {  // Repeat 10 times...
    for(int b=0; b<3; b++) { //  'b' counts from 0 to 2...
      strip.clear();         //   Set all pixels in RAM to 0 (off)
      // 'c' counts up from 'b' to end of strip in steps of 3...
      for(int c=b; c<strip.numPixels(); c += 3) {
        strip.setPixelColor(c, color); // Set pixel 'c' to value 'color'
      }
      strip.show(); // Update strip with new contents
      delay(wait);  // Pause for a moment
    }
  }
}

// Rainbow cycle along whole strip. Pass delay time (in ms) between frames.
// (ADAFRUIT)
void rainbow(int wait) {
  // Hue of first pixel runs 5 complete loops through the color wheel.
  // Color wheel has a range of 65536 but it's OK if we roll over, so
  // just count from 0 to 5*65536. Adding 256 to firstPixelHue each time
  // means we'll make 5*65536/256 = 1280 passes through this outer loop:
  for(long firstPixelHue = 0; firstPixelHue < 5*65536; firstPixelHue += 256) {
    for(int i=0; i<strip.numPixels(); i++) { // For each pixel in strip...
      // Offset pixel hue by an amount to make one full revolution of the
      // color wheel (range of 65536) along the length of the strip
      // (strip.numPixels() steps):
      int pixelHue = firstPixelHue + (i * 65536L / strip.numPixels());
      // strip.ColorHSV() can take 1 or 3 arguments: a hue (0 to 65535) or
      // optionally add saturation and value (brightness) (each 0 to 255).
      // Here we're using just the single-argument hue variant. The result
      // is passed through strip.gamma32() to provide 'truer' colors
      // before assigning to each pixel:
      strip.setPixelColor(i, strip.gamma32(strip.ColorHSV(pixelHue)));
    }
    strip.show(); // Update strip with new contents
    delay(wait);  // Pause for a moment
  }
}

// Rainbow-enhanced theater marquee. Pass delay time (in ms) between frames.
// (ADAFRUIT)
void theaterChaseRainbow(int wait) {
  int firstPixelHue = 0;     // First pixel starts at red (hue 0)
  for(int a=0; a<30; a++) {  // Repeat 30 times...
    for(int b=0; b<3; b++) { //  'b' counts from 0 to 2...
      strip.clear();         //   Set all pixels in RAM to 0 (off)
      // 'c' counts up from 'b' to end of strip in increments of 3...
      for(int c=b; c<strip.numPixels(); c += 3) {
        // hue of pixel 'c' is offset by an amount to make one full
        // revolution of the color wheel (range 65536) along the length
        // of the strip (strip.numPixels() steps):
        int      hue   = firstPixelHue + c * 65536L / strip.numPixels();
        uint32_t color = strip.gamma32(strip.ColorHSV(hue)); // hue -> RGB
        strip.setPixelColor(c, color); // Set pixel 'c' to value 'color'
      }
      strip.show();                // Update strip with new contents
      delay(wait);                 // Pause for a moment
      firstPixelHue += 65536 / 90; // One cycle of color wheel over 90 frames
    }
  }
}

// sends loser or winner sounds to mp3 player
void sendMP3Command(char c) {
  switch (c) {
    case 'r':
      Serial.println("Reset");
      sendCommand(CMD_RESET, 0x00);
      break;

   case 'l':
      randNumber = random(1, 15);    
      Serial.println("Loser Song");
      Serial.println(randNumber); 
      sendCommand(CMD_PLAY_W_INDEX, (int)randNumber);
      break;       

   case 'w':
      Serial.println("Win Song");
      sendCommand(CMD_PLAY_W_INDEX, 16);
      break;
  }
}

// decode the mp3 player circuit respose msgs
String decodeMP3Answer() {
  String decodedMP3Answer = "";

  decodedMP3Answer += sanswer();

  switch (ansbuf[3]) {
    case 0x3A:
      decodedMP3Answer += " -> Memory card inserted.";
      break;

    case 0x3D:
      decodedMP3Answer += " -> Completed play num " + String(ansbuf[6], DEC);
      break;

    case 0x40:
      decodedMP3Answer += " -> Error";
      break;

    case 0x41:
      decodedMP3Answer += " -> Data recived correctly. ";
      break;

    case 0x42:
      decodedMP3Answer += " -> Status playing: " + String(ansbuf[6], DEC);
      break;

    case 0x48:
      decodedMP3Answer += " -> File count: " + String(ansbuf[6], DEC);
      break;

    case 0x4C:
      decodedMP3Answer += " -> Playing: " + String(ansbuf[6], DEC);
      break;

    case 0x4E:
      decodedMP3Answer += " -> Folder file count: " + String(ansbuf[6], DEC);
      break;

    case 0x4F:
      decodedMP3Answer += " -> Folder count: " + String(ansbuf[6], DEC);
      break;
  }

  return decodedMP3Answer;
}

// send commands to mp3 player
void sendCommand(int8_t command, int16_t dat)
{
  delay(20);
  Send_buf[0] = 0x7e;   //
  Send_buf[1] = 0xff;   //
  Send_buf[2] = 0x06;   // Len
  Send_buf[3] = command;//
  Send_buf[4] = 0x01;   // 0x00 NO, 0x01 feedback
  Send_buf[5] = (int8_t)(dat >> 8);  //datah
  Send_buf[6] = (int8_t)(dat);       //datal
  Send_buf[7] = 0xef;   //
  for (uint8_t i = 0; i < 8; i++)
  {
    mp3.write(Send_buf[i]) ;
  }
}

// byte to string hex
String sbyte2hex(uint8_t b)
{
  String shex;

  shex = "0X";

  if (b < 16) shex += "0";
  shex += String(b, HEX);
  shex += " ";
  return shex;
}

// get response from mp3 player
String sanswer(void)
{
  uint8_t i = 0;
  String mp3answer = "";

  // Get only 10 Bytes
  while (mp3.available() && (i < 10))
  {
    uint8_t b = mp3.read();
    ansbuf[i] = b;
    i++;
    mp3answer += sbyte2hex(b);
  }

  // if the answer format is correct.
  if ((ansbuf[0] == 0x7E) && (ansbuf[9] == 0xEF))
  {
    return mp3answer;
  }
  return "???: " + mp3answer;
}
