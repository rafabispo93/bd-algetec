from flask import Flask, g, request
from threading import Timer
from flask_cors import CORS
from multiprocessing import Process
import sqlite3, json, csv, socket, serial, sys, string, time, numpy
import http.client, urllib.parse
import RPi.GPIO as gpio

app = Flask(__name__)
CORS(app) # Pemite que browsers possam realizar requisições sem problemas de cross-origin
DATABASE = './database.db' #arquivo previamente criado para armazenar o banco sqlite
CURRENT_RYTHM = 0
CURRENT_ANSWER = ''
RYTHMS_LIST = []
CURRENT_LEVEL = 0
CURRENT_COMPRESSION = ""

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
		send_via_serial(int(data['ritmo'])) #manda um valor via porta serial
		global CURRENT_RYTHM
		CURRENT_RYTHM = int(data['ritmo']) # atualiza o ritmo atual
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
		global CURRENT_RYTHM
		global RYTHMS_LIST
		global CURRENT_LEVEL
		RYTHMS_LIST = data['ritmos']
		CURRENT_LEVEL = 0
		CURRENT_RYTHM = int(RYTHMS_LIST[0])
		send_via_serial(int(RYTHMS_LIST[0]))
		#for rythm in data['ritmos']:
		#	print(int(rythm))
		#	global CURRENT_ANSWER
		#	global CURRENT_RYTHM
		#	send_via_serial(int(rythm))
		#	time.sleep(30)
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
		database = get_db()
		db = database.cursor()
		result = db.execute('SELECT * FROM ritmo WHERE name=?', [data['rythm']]).fetchall()
		result = json.dumps(result[0][2])
		global CURRENT_ANSWER
		global CURRENT_LEVEL
		global RYTHMS_LIST

		#Se a etapa atual da sequência da atividade chegar ao último ritmo programado, retorna msg de exercíco finalizado 
		if int(CURRENT_LEVEL) >= len(RYTHMS_LIST):
			return json.dumps({'msg': 'Exercício Finalizado', 'status': 200}), 200
		elif RYTHMS_LIST[int(CURRENT_LEVEL)] == result and int(CURRENT_LEVEL) < len(RYTHMS_LIST):
			CURRENT_LEVEL = CURRENT_LEVEL + 1 #atualiza estado atual da atividade
			CURRENT_ANSWER = data['answer'] #atualiza a resposta atual do aluno
			if CURRENT_LEVEL >= len(RYTHMS_LIST):
				return json.dumps({'msg': 'Resposta Correta e Fim da Atividade', 'status': 200})
			else:
				send_via_serial(int(RYTHMS_LIST[int(CURRENT_LEVEL)]))
				return json.dumps({'msg': 'Resposta Correta, direcionado para próximo ritmo', 'status': 200})
		CURRENT_ANSWER = data['answer']
		return json.dumps({'msg': 'Resposta enviada com sucesso', 'status': 200 }), 200
	except Exception as error:
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

@app.route("/get/current/compression_value", methods=['GET'])
def get_compression_value():
	try:
		global CURRENT_COMPRESSION
		print(CURRENT_COMPRESSION)
		return json.dumps({'msg': 'Valor de compressão retornado com sucesso', 'value': CURRENT_COMPRESSION, 'status': 200}), 200
	except exception as error:
		print(error, "ERROR")
		return 'Ocorreu um erro interno no servidor', 500

@app.route("/post/compression_value", methods=['POST'])
def post_compression_value():
	data = request.data
	data = json.loads(data.decode('utf-8'))
	global CURRENT_COMPRESSION
	CURRENT_COMPRESSION = data['value']
	return json.dumps({'msg': 'Valor de comrpessao atualizado'}), 200

def send_to_port(value):
	list = [29, 31, 33, 35, 37]
	gpio.setup(list, gpio.OUT)
	for port in list:
		print('Value: ', value, 'Porta: ', port)
		gpio.output(port, value)
		value = int(bin(value), 2) >> 1

#Manda via porta serial um valor
def send_via_serial(value):
	try:
		port = serial.Serial('/dev/ttyS0', baudrate = 115385, stopbits = serial.STOPBITS_ONE, bytesize = serial.EIGHTBITS, timeout = 2)
		port.write(chr(value).encode('latin_1'))
		print(value, port)
		return True
	except:
		return False

# Escuta na porta serial indefinidamente todos os valores que chegam
def listen_via_serial(host_ip):
	try:
			port = serial.Serial('/dev/ttyS0', baudrate = 115385, stopbits = serial.STOPBITS_ONE, bytesize = serial.EIGHTBITS, timeout = 0)
			conn = http.client.HTTPConnection(host_ip+":5000")
			freq_numbers = [] #armazena os valores referentes a frequência da compressão cardíaca
			values_compression = [] #armazena todos os valores que chegam desde que estejam dentro da quantidade esperada
			n = 3 #número de informações diferentes que serão tratadas (defino em protocolo de comunicação PI3 - PIC
			while True:
				if port.inWaiting() > 0:
					value = port.read(1)
					#print(value[0])
					if value[0] > 0 and len(values_compression) <= n:
						values_compression.append(value[0])
					elif value[0] > 0 and len(values_compression) == n:
						freq_numbers.append(values_compression[0])
					else:
						freq_numbers = [0]
						values_compression = [0]
					if len(freq_numbers) > 0 and conn:
						result = numpy.mean(freq_numbers, axis=0) #calcula média dos valores da frequência da compressão cardíaca
						result = numpy.around(result, decimals=0) # arredonda valores da média da frequência da compressao cardíaca
						#print(result, "results")
						#print(values_compression)
						headers = {"Content-type": "application/json", "Accept": "text/plain"}
						conn.request('POST', '/post/compression_value', json.dumps({'value': result}), headers) #atualiza valor da frequência no servidor
						response = conn.getresponse()
						#print(value[0])
	except Exception as error:
		print(error, "ERROR Listen Serial")
		pass

if __name__ == '__main__':
	#Identifica ip atual atribuído a essa máquina 
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.connect(('8.8.8.8',80))
	host_ip = s.getsockname()[0]
	s.close()

	#Cria e dispara a thread para escutar os valores que chegam na porta serial sem interromper funcionamento do servidor
	p = Process(target=listen_via_serial, args=(str(host_ip),))
	p.start()
	app.run(debug=True, host=host_ip, port=5000)
	p.join()

