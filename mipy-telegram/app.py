import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import librouteros
from librouteros.query import Key
from librouteros import login
import logging
import telegram
import json
from dotenv import load_dotenv
import socket
import ssl

# Set up logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables jika ada
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mikrotik-telegram-secret-key')

# Default config
config = {
    'IP_MIKROTIK': os.environ.get('IP_MIKROTIK', ''),
    'PORT_API_MIKROTIK': os.environ.get('PORT_API_MIKROTIK', '8728'),
    'USE_SSL': os.environ.get('USE_SSL', 'False') == 'True',
    'VERIFY_SSL': os.environ.get('VERIFY_SSL', 'True') == 'True',
    'USERNAME_MIKROTIK': os.environ.get('USERNAME_MIKROTIK', ''),
    'PASSWORD_MIKROTIK': os.environ.get('PASSWORD_MIKROTIK', ''),
    'TELEGRAM_TOKEN': os.environ.get('TELEGRAM_TOKEN', ''),
    'TELEGRAM_CHAT_ID': os.environ.get('TELEGRAM_CHAT_ID', ''),
}

# Simpan config ke file
def save_config():
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f)
        logger.info("Konfigurasi berhasil disimpan ke config.json")
    except Exception as e:
        logger.error(f"Gagal menyimpan konfigurasi: {e}")

# Load config dari file
def load_config():
    global config
    try:
        with open('config.json', 'r') as f:
            loaded_config = json.load(f)
            config.update(loaded_config)
        logger.info("Konfigurasi berhasil dimuat dari config.json")
    except (FileNotFoundError, json.JSONDecodeError):
        # Jika file tidak ada atau tidak valid, simpan config default
        logger.warning("File konfigurasi tidak ditemukan atau tidak valid, menggunakan nilai default")
        save_config()

# Load config pada saat startup
load_config()

@app.route('/')
def index():
    return render_template('index.html', config=config)

@app.route('/save_config', methods=['POST'])
def save_config_route():
    config['IP_MIKROTIK'] = request.form.get('IP_MIKROTIK')
    config['PORT_API_MIKROTIK'] = request.form.get('PORT_API_MIKROTIK')
    config['USE_SSL'] = request.form.get('USE_SSL') == 'on'
    config['VERIFY_SSL'] = request.form.get('VERIFY_SSL') == 'on'
    config['USERNAME_MIKROTIK'] = request.form.get('USERNAME_MIKROTIK')
    config['PASSWORD_MIKROTIK'] = request.form.get('PASSWORD_MIKROTIK')
    config['TELEGRAM_TOKEN'] = request.form.get('TELEGRAM_TOKEN')
    config['TELEGRAM_CHAT_ID'] = request.form.get('TELEGRAM_CHAT_ID')
    
    save_config()
    flash('Konfigurasi telah disimpan!', 'success')
    return redirect(url_for('index'))

@app.route('/test_mikrotik', methods=['POST'])
def test_mikrotik():
    try:
        # Cek apakah host dapat dijangkau
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((config['IP_MIKROTIK'], int(config['PORT_API_MIKROTIK'])))
        if result != 0:
            return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Port {config["PORT_API_MIKROTIK"]} tertutup atau tidak dapat dijangkau'})
        sock.close()
        
        # Coba koneksi Mikrotik API
        mikrotik_api = connect_to_mikrotik()
        if mikrotik_api:
            # Coba akses resources untuk memastikan koneksi berfungsi
            resources = mikrotik_api.path('/system/resource')
            resource_list = list(resources)
            mikrotik_api.close()
            logger.info(f"Koneksi ke Mikrotik berhasil. Resource info: {resource_list}")
            return jsonify({'success': True, 'message': 'Berhasil terhubung ke Mikrotik!'})
    except socket.gaierror:
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Nama host tidak dapat diselesaikan'})
    except socket.timeout:
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Koneksi timeout'})
    except librouteros.exceptions.AuthenticationError:
        logger.error("Mikrotik authentication error: username/password salah")
        return jsonify({'success': False, 'message': 'Gagal terhubung ke Mikrotik: Username atau password salah'})
    except librouteros.exceptions.ConnectionClosed as e:
        logger.error(f"Mikrotik connection closed: {e}")
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Error koneksi. Pastikan API service aktif dan port benar.'})
    except librouteros.exceptions.FatalError as e:
        logger.error(f"Mikrotik fatal error: {e}")
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Error fatal - {str(e)}'})
    except ValueError as e:
        logger.error(f"Value error: {e}")
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Error konfigurasi SSL - {str(e)}'})
    except TypeError as e:
        logger.error(f"Type error: {e}")
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: Error SSL - {str(e)}'})
    except Exception as e:
        logger.error(f"Mikrotik connection error: {e}")
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Mikrotik: {str(e)}'})

@app.route('/test_telegram', methods=['POST'])
def test_telegram():
    try:
        # Validasi format token
        token = config['TELEGRAM_TOKEN']
        if not token or len(token.split(':')) != 2:
            return jsonify({'success': False, 'message': 'Token Telegram tidak valid: Format salah. Seharusnya [numbers]:[alphanumeric]'})

        bot = telegram.Bot(token=token)
        bot_info = bot.get_me()
        logger.info(f"Bot info: {bot_info.username}")
        
        chat_id = config['TELEGRAM_CHAT_ID']
        bot.send_message(chat_id=chat_id, 
                         text="✅ Koneksi ke Bot Telegram berhasil!")
        return jsonify({'success': True, 'message': f'Berhasil terhubung ke Telegram Bot: @{bot_info.username}!'})
    except telegram.error.InvalidToken:
        logger.error("Invalid Telegram token")
        return jsonify({'success': False, 'message': 'Gagal terhubung ke Telegram: Token tidak valid'})
    except telegram.error.Unauthorized:
        logger.error("Unauthorized Telegram token")
        return jsonify({'success': False, 'message': 'Gagal terhubung ke Telegram: Token tidak sah atau sudah dicabut'})
    except telegram.error.BadRequest as e:
        if 'chat not found' in str(e).lower():
            logger.error(f"Telegram chat ID not found: {e}")
            return jsonify({'success': False, 'message': 'Gagal terhubung ke Telegram: Chat ID tidak ditemukan'})
        else:
            logger.error(f"Telegram bad request: {e}")
            return jsonify({'success': False, 'message': f'Gagal terhubung ke Telegram: {str(e)}'})
    except Exception as e:
        logger.error(f"Telegram connection error: {e}")
        return jsonify({'success': False, 'message': f'Gagal terhubung ke Telegram: {str(e)}'})

def connect_to_mikrotik():
    """Fungsi untuk terhubung ke API Mikrotik"""
    api = None
    try:
        # Persiapkan argumen koneksi
        kwargs = {
            'host': config['IP_MIKROTIK'],
            'port': int(config['PORT_API_MIKROTIK']),
            'username': config['USERNAME_MIKROTIK'],
            'password': config['PASSWORD_MIKROTIK']
        }
        
        # Konfigurasi SSL jika digunakan
        if config.get('USE_SSL', False):
            logger.info("Menggunakan koneksi SSL untuk API Mikrotik")
            
            # Inisialisasi context SSL
            ctx = ssl.create_default_context()
            
            # Konfigurasi verifikasi SSL
            if not config.get('VERIFY_SSL', True):
                logger.warning("Verifikasi SSL dinonaktifkan")
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            
            # Buat fungsi wrapper khusus yang menyediakan server_hostname
            def ssl_wrapper(sock):
                return ctx.wrap_socket(sock, server_hostname=config['IP_MIKROTIK'])
            
            # Tambahkan wrapper ke argumen
            kwargs['ssl_wrapper'] = ssl_wrapper
        
        # Koneksi ke Mikrotik dengan argumen yang telah disiapkan
        api = librouteros.connect(**kwargs)
        return api
    except Exception as e:
        logger.error(f"Error connecting to Mikrotik: {e}")
        raise

def create_voucher(username, password, profile, limit=None, comment=None):
    """Fungsi untuk membuat voucher di Mikrotik Hotspot"""
    try:
        api = connect_to_mikrotik()
        if not api:
            return False, "Tidak dapat terhubung ke Mikrotik"
        
        params = {
            'name': username,
            'password': password,
            'profile': profile,
        }
        
        if limit:
            params['limit-uptime'] = limit
        
        if comment:
            params['comment'] = comment
        
        # Tambahkan user hotspot baru
        api.path('ip/hotspot/user').add(**params)
        
        api.close()
        logger.info(f"Voucher berhasil dibuat untuk username: {username}")
        return True, "Voucher berhasil dibuat"
    except Exception as e:
        logger.error(f"Error creating voucher: {e}")
        return False, str(e)

if __name__ == '__main__':
    # Pastikan folder templates ada
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        logger.info(f"Membuat direktori templates: {templates_dir}")
    
    # Buat file log untuk tracking
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
    if not os.path.exists(log_file):
        open(log_file, 'w').close()
        logger.info(f"Membuat file log: {log_file}")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 