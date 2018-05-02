import serial
import time

port = serial.Serial("/dev/ttyS0", baudrate = 9600, stopbits = serial.STOPBITS_ONE, bytesize = serial.EIGHTBITS, timeout = 2)

a=255
while True:
	print(a)
	port.write(chr(a).encode('latin_1'))
	time.sleep(1)
	if a == 0:
		a = 255
	else:
		a = a-1
