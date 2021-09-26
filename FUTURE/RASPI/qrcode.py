from imutils.video import VideoStream
from pyzbar import pyzbar
import RPi.GPIO as GPIO
import argparse
import datetime
import imutils
import time
import cv2
import serial
 
# video setup
#vs = VideoStream(src=0).start()  #Uncomment this if you are using Webcam
vs = VideoStream(usePiCamera=True).start() # For Pi Camera
time.sleep(2.0)

# serial setup
ser = serial.Serial('/dev/ttyS0')  # open serial port

# gpio setup
GPIO.setwarnings(False)    # Ignore warning for now
GPIO.setmode(GPIO.BOARD)  
GPIO.setup(12, GPIO.OUT, initial=GPIO.LOW)  

# variables
flag = False
node_type = 'QR'
player = 'X'
send_payload = ''
 
while True:
  frame = vs.read()
  frame = imutils.resize(frame, width=400)
  barcodes = pyzbar.decode(frame)

  if len(barcodes) == 0:
    flag = False

  for barcode in barcodes:
    (x, y, w, h) = barcode.rect
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
    barcodeData = barcode.data.decode("utf-8")
    barcodeType = barcode.type
    text = "{} ({})".format(barcodeData, barcodeType)
    #print (text)
    cv2.putText(frame, text, (x, y - 10),
    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    if barcodeType == 'QRCODE':
      flag = True
      send_payload = node_type + ',' + player + ',' + str(int(time.time())) + ',' + barcodeData + '\r\n'
      print(send_payload)
      ser.write(send_payload.encode('ascii'))

  if flag:
    GPIO.output(12, GPIO.HIGH)
  else:
    GPIO.output(12, GPIO.LOW)
 
  # cv2.imshow("Barcode Reader", frame)
  key = cv2.waitKey(1) & 0xFF
 
  # if the `s` key is pressed, break from the loop
  if key == ord("s"):
    break

print("[INFO] cleaning up...")

ser.close()
csv.close()
cv2.destroyAllWindows()
vs.stop()