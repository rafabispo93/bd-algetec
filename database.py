from flask import Flask, g, request
from threading import Timer
import sqlite3
import json
import socket
import serial
import sys
import string
import time
from flask_cors import CORS
import RPi.GPIO as gpio
app = Flask(__name__)
CORS(app)
DATABASE = './database.db'
CURRENT_RYTHM = 0
CURRENT_ANSWER = ''

@app.route("/")
def index():
	cur = get_db()
	return 'Database foi iniciada', 200

def get_db():
	try:
		db = getattr(g, '_database', None)
		database= sqlite3.connect(DATABASE)
		ritmos = [(None, 'Bradicardia Sinusal', 0), (None, 'Bradicardia Juncional', 1), (None, 'Taquicardia Ventricular Monomórfica', 2), (None, 'Bloqueio AV 1º grau', 3), (None, 'Bloqueio AV 2º grau Mobitz I', 4),
			 (None, 'Fluter Atrial', 5), (None, 'Fibrilação Ventricular', 6), (None, 'Bloqueio AV 2º grau Mobitz II', 7), (None, 'Bloqueio AV Total com Escape Juncional', 8), 
			 (None, 'Bloqueio AV Total com Escape Ventricular', 9), (None, 'Bloqueio AV 2:1', 10), (None, 'Indioventricular', 11), (None, 'Marcapasso', 12), (None, 'Assistolia', 13),
			 (None, 'Taquicardia Sinusal', 14), (None, 'Taquicardia Atrial', 15), (None, 'Taquicardia Supraventricular', 16),
			 (None, 'Fibrilação Atrial', 17), (None, 'Torsades de Points', 18), (None, 'Sinusal Normal', 19)]
		usuarios = [(None, 'instrutor', '123'), (None, 'aluno', '123')]
		if db is None:
			db = database.cursor()
			db.execute('CREATE TABLE IF NOT EXISTS ritmo (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, value INTEGER NOT NULL UNIQUE);')
			db.execute('CREATE TABLE IF NOT EXISTS usuario (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL);')
			data = db.execute('SELECT * FROM ritmo;').fetchall()
			if len(data) == 0:
				db.executemany('INSERT INTO ritmo (id, name, value) VALUES (?, ?, ?);', ritmos)
			data = db.execute('SELECT * FROM usuario;').fetchall()
			if len(data) == 0:
				db.executemany('INSERT INTO usuario (id, username, password) VALUES (?,?,?);', usuarios)
			database.commit()
		return database
	except Exception as error:
		print(error)
		database.rollback()
		return 'Ocorreu um erro interno no servidor', 500

@app.teardown_appcontext
def close_connection(exception):
	db = getattr(g, '_database', None)
	if db is not None:
		db.close()

@app.route("/get/ritmos")
def get_ritmos():
	try:
		db = get_db()
		db = db.cursor()
		ritmos = db.execute('SELECT * FROM ritmo;').fetchall()
		return json.dumps(ritmos)
	except Exception as error:
		print(error)
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/add/ritmo/<ritmo>")
def add_ritmo(ritmo):
	try:
		database = get_db()
		db = database.cursor()
		to_add = [(None, ritmo)]
		db.executemany('INSERT INTO ritmo (id, name) VALUES (?, ?);', to_add)
		database.commit()
		data = db.execute('SELECT * FROM ritmo;').fetchall()
		return json.dumps({'msg': 'Ritmo adicionado com sucesso.'}), 200
	except Exception as error:
		print(error)
		database.rollback()
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/remove/ritmo/<id>")
def remove_ritmo(id):
	try:
		database = get_db()
		db = database.cursor()
		db.execute('DELETE FROM ritmo WHERE id =' + id + ';')
		database.commit()
		return json.dumps({'msg': 'Ritmo apagado com sucesso'}), 200
	except Exception as error:
		print(error)
		database.rollback()
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/login", methods=['POST'])
def login():
	try:
		login_data = request.data
		login_data = json.loads(login_data.decode('utf-8'))
		database = get_db()
		db = database.cursor()
		for user in db.execute('SELECT * FROM usuario WHERE username=?', [login_data['username']]):
			if user[1] == login_data['username'] and user[2] == login_data['password']:
				return 'Login realizado com sucesso', 200
			else:
				return 'Login ou senha inválido', 500
		return 'Username inválido', 500
	except Exception as error:
		print(error)
		return 'Ocoreu um erro interno no servidor', 500

@app.route("/send/ritmo", methods=['POST'])
def send_ritmo():
	try:
		data = request.data
		data = json.loads(data.decode('utf-8'))
		gpio.setmode(gpio.BOARD)
		send_to_port(int(data['ritmo']))
		send_via_serial(int(data['ritmo']))
		global CURRENT_RYTHM
		CURRENT_RYTHM = int(data['ritmo'])
		#gpio.cleanup()
		return 'Ritmo enviado com sucesso', 200
	except Exception as error:
		print(error)
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/send/multiple/ritmos", methods=['POST'])
def send_multiple_ritmos():
	try:
		data = request.data
		data = json.loads(data.decode('utf-8'))
		print(data)
		gpio.setmode(gpio.BOARD)
		for rythm in data['ritmos']:
			print(int(rythm))
			global CURRENT_ANSWER
			global CURRENT_RYTHM
			send_via_serial(int(rythm))
			time.sleep(30)
			#while CURRENT_ANSWER != CURRENT_RYTHM:
			#t = Timer(30.0, send_via_serial(int(rythm)))
		return 'Sequência realizada', 200
	except Exception as error:
		print(error)
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/get/current/ritmo", methods=['GET'])
def get_current_ritmo():
	try:
		database = get_db()
		db = database.cursor()
		global CURRENT_RYTHM
		result = db.execute('SELECT * FROM ritmo WHERE value=?', [CURRENT_RYTHM]).fetchall()
		return json.dumps(result), 200
	except Exception as error:
		print(error)
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/send/answer", methods=['POST'])
def send_answer():
	try:
		data = request.data
		data = json.loads(data.decode('utf-8'))
		global CURRENT_ANSWER
		CURRENT_ANSWER = data['answer']
		return json.dumps({'msg': 'Resposta enviada com sucesso'}), 200
	except exception as error:
		print(error)
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/get/current/answer", methods=['GET'])
def get_answer():
	try:
		global CURRENT_ANSWER
		return json.dumps({'answer': CURRENT_ANSWER}), 200
	except exception as error:
		print(error)
		return 'Ocorreu um erro interno no servidor', 500

def send_to_port(value):
	list = [29, 31, 33, 35, 37]
	gpio.setup(list, gpio.OUT)
	for port in list:
		print('Value: ', value, 'Porta: ', port)
		gpio.output(port, value)
		value = int(bin(value), 2) >> 1
def send_via_serial(value):
	try:
		port = serial.Serial('/dev/ttyS0', baudrate = 9600, stopbits = serial.STOPBITS_ONE, bytesize = serial.EIGHTBITS, timeout = 2)
		port.write(chr(value).encode('latin_1'))
		return True
	except:
		return False

if __name__ == '__main__':
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.connect(('8.8.8.8',80))
	host_ip = s.getsockname()[0]
	#host_ip = socket.gethostbyname(socket.gethostname())
	s.close()
	app.run(debug=True, host=host_ip, port=5000)
