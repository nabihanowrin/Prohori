#include <Servo.h>

const int flamePin = 7;
const int servoPin = 6;
const int linkPin = 8;     // from Uno D8

const int FLAME_DETECTED = LOW;
const int closedAngle = 90;
const int openAngle = 180;

Servo door;
bool alarmOn = false;
bool doorOpen = false;
unsigned long lastFlame = 0;

void setup() {
  Serial.begin(9600);
  pinMode(flamePin, INPUT);
  pinMode(linkPin, INPUT);
  door.attach(servoPin);
  door.write(closedAngle);
  Serial.println("EV|B|Zone B ready");
}

void loop() {
  bool flame = (digitalRead(flamePin) == FLAME_DETECTED);
  if (flame) lastFlame = millis();

  bool fireAlarm = flame || (lastFlame > 0 && millis() - lastFlame < 2000);
  bool unoSaysOpen = (digitalRead(linkPin) == HIGH);

  if (fireAlarm && !alarmOn) Serial.println("EV|B|FIRE ALERT - door open");
  if (!fireAlarm && alarmOn) Serial.println("EV|B|Fire clear");
  alarmOn = fireAlarm;

  bool openNow = fireAlarm || unoSaysOpen;
  if (openNow != doorOpen) {
    doorOpen = openNow;
    door.write(doorOpen ? openAngle : closedAngle);
  }

  Serial.print("B|flame=");  Serial.print(flame ? 1 : 0);
  Serial.print("|alarm=");   Serial.print(alarmOn ? 1 : 0);
  Serial.print("|door=");    Serial.print(doorOpen ? 1 : 0);
  Serial.println("|lights=0");
  delay(200);
}