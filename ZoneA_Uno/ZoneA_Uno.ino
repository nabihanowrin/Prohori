#include <SPI.h>
#include <MFRC522.h>

const int mq2Pin = A0;
const int pumpPin = 3;     // MOSFET gate (through 220 ohm)
const int buzzerPin = 5;
const int linkPin = 8;     // to Nano D8: HIGH = open door
const int arrowLeds[] = {2, A1, A3};   // red, yellow, green
const int arrowCount = 3;
int arrowStep = 0;

int gasDanger = 330;

MFRC522 rfid(10, 9);

String cardUID[] = {"14 59 37 03"};
String cardName[] = {"Person 1"};
bool inside[] = {false};
const int cardCount = 1;

bool alarmOn = false;
bool doorOpen = false;

void setup() {
  Serial.begin(9600);
  pinMode(pumpPin, OUTPUT);
  digitalWrite(pumpPin, LOW);
  pinMode(buzzerPin, OUTPUT);
  pinMode(linkPin, OUTPUT);
  digitalWrite(linkPin, LOW);
  for (int i = 0; i < arrowCount; i++) pinMode(arrowLeds[i], OUTPUT);
  arrowsOff();
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("EV|A|Zone A ready");
}

void loop() {
  int gas = analogRead(mq2Pin);

  if (gas > gasDanger) {
    if (!alarmOn) {
      alarmOn = true;
      Serial.println("EV|A|GAS ALERT - door open, sprinkler ON");
      Serial.println("EV|A|Still inside: " + insideList());
    }
    digitalWrite(buzzerPin, HIGH);
    digitalWrite(pumpPin, HIGH);
    setDoor(true);
    runArrows();
  } else {
    if (alarmOn) {
      alarmOn = false;
      Serial.println("EV|A|Air clear - door closed");
    }
    digitalWrite(buzzerPin, LOW);
    digitalWrite(pumpPin, LOW);
    setDoor(false);
    arrowsOff();
    checkCard(gas);
  }

  sendStatus(gas);
  delay(200);
}

void setDoor(bool open) {
  doorOpen = open;
  digitalWrite(linkPin, open ? HIGH : LOW);
}

void runArrows() {
  arrowsOff();
  digitalWrite(arrowLeds[arrowStep], HIGH);
  arrowStep = (arrowStep + 1) % arrowCount;
}

void arrowsOff() {
  for (int i = 0; i < arrowCount; i++) digitalWrite(arrowLeds[i], LOW);
}

void sendStatus(int gas) {
  Serial.print("A|gas=");   Serial.print(gas);
  Serial.print("|alarm=");  Serial.print(alarmOn ? 1 : 0);
  Serial.print("|door=");   Serial.print(doorOpen ? 1 : 0);
  Serial.print("|fan=0|pump=");
  Serial.print(alarmOn ? 1 : 0);
  Serial.print("|lights=");
  Serial.print(alarmOn ? 1 : 0);
  Serial.print("|inside="); Serial.println(insideList());
}

void checkCard(int gas) {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  String uid = readUID();
  int person = findCard(uid);
  if (person == -1) {
    Serial.println("EV|A|ACCESS DENIED (" + uid + ")");
  } else {
    inside[person] = !inside[person];
    Serial.println("EV|A|" + cardName[person] + (inside[person] ? " IN" : " OUT"));
    setDoor(true);
    sendStatus(gas);
    delay(3000);
    setDoor(false);
  }
  rfid.PICC_HaltA();
}

String readUID() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (i > 0) uid += " ";
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

int findCard(String uid) {
  for (int i = 0; i < cardCount; i++) {
    if (uid == cardUID[i]) return i;
  }
  return -1;
}

String insideList() {
  String list = "";
  for (int i = 0; i < cardCount; i++) {
    if (inside[i]) {
      if (list != "") list += ", ";
      list += cardName[i];
    }
  }
  if (list == "") list = "nobody";
  return list;
}