import os
import json
import logging
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import random
import string
from dotenv import load_dotenv
import librouteros
import ssl
import socket

# Set up logging
logging.basicConfig(
    filename='telegram_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables jika ada
load_dotenv()

# States untuk conversation handler
PROFILE = 0
USERNAME_TYPE = 1
USERNAME = 2
PASSWORD = 3
LIMIT = 4
COMMENT = 5

# States untuk detail handler
DETAIL_USERNAME = 0

# Load config dari file
def load_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            logger.info("Konfigurasi berhasil dimuat dari config.json")
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Config file tidak ditemukan atau tidak valid: {e}")
        return None

def connect_to_mikrotik(config):
    """Fungsi untuk terhubung ke API Mikrotik"""
    try:
        # Validasi konfigurasi
        if not config or not config.get('IP_MIKROTIK') or not config.get('USERNAME_MIKROTIK'):
            logger.error("Konfigurasi Mikrotik tidak lengkap")
            return None
            
        # Cek koneksi dasar ke host/port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((config['IP_MIKROTIK'], int(config['PORT_API_MIKROTIK'])))
        sock.close()
        
        if result != 0:
            logger.error(f"Port {config['PORT_API_MIKROTIK']} pada {config['IP_MIKROTIK']} tertutup atau tidak dapat dijangkau")
            return None
            
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
        
        logger.info(f"Berhasil terhubung ke Mikrotik API {config['IP_MIKROTIK']}:{config['PORT_API_MIKROTIK']}")
        return api
    except socket.gaierror:
        logger.error(f"Nama host tidak dapat diselesaikan: {config['IP_MIKROTIK']}")
        return None
    except socket.timeout:
        logger.error(f"Koneksi timeout ke {config['IP_MIKROTIK']}:{config['PORT_API_MIKROTIK']}")
        return None
    except librouteros.exceptions.AuthenticationError:
        logger.error("Login gagal: username/password salah")
        return None
    except librouteros.exceptions.ConnectionClosed as e:
        logger.error(f"Error koneksi ke Mikrotik: {e}. Pastikan API service aktif.")
        return None
    except ValueError as e:
        logger.error(f"Error SSL konfigurasi: {e}")
        return None
    except TypeError as e:
        logger.error(f"Error SSL wrapper: {e}")
        return None
    except Exception as e:
        logger.error(f"Error connecting to Mikrotik: {e}")
        return None

def get_hotspot_profiles(api):
    """Mendapatkan daftar profile hotspot dari Mikrotik"""
    try:
        if not api:
            logger.error("Tidak dapat mengambil profile hotspot: API tidak terhubung")
            return []
            
        profiles = api.path('ip/hotspot/user/profile')
        profiles_list = [profile.get('name') for profile in profiles]
        logger.info(f"Berhasil mendapatkan {len(profiles_list)} profile hotspot")
        return profiles_list
    except Exception as e:
        logger.error(f"Error getting hotspot profiles: {e}")
        return []

def generate_random_string(length):
    """Generate random string untuk username/password"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def start(update: Update, context: CallbackContext) -> None:
    """Handler untuk command /start"""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.first_name}) memulai bot")
    update.message.reply_text(
        f'Selamat datang {user.first_name} di Bot Mikrotik Hotspot Voucher Generator!\n'
        'Gunakan /voucher untuk membuat voucher hotspot baru.\n'
        'Gunakan /list untuk melihat daftar voucher yang ada.\n'
        'Gunakan /status untuk melihat status koneksi ke Mikrotik.\n'
        'Gunakan /detail untuk melihat detail penggunaan voucher.'
    )

def cancel(update: Update, context: CallbackContext) -> int:
    """Handler untuk membatalkan operasi"""
    user = update.effective_user
    logger.info(f"User {user.id} membatalkan operasi")
    update.message.reply_text('Operasi dibatalkan.')
    return ConversationHandler.END

def status(update: Update, context: CallbackContext) -> None:
    """Handler untuk command /status, memeriksa status koneksi Mikrotik"""
    config = load_config()
    if not config:
        update.message.reply_text('❌ Konfigurasi tidak ditemukan. Silakan atur melalui web interface.')
        return
    
    user = update.effective_user
    logger.info(f"User {user.id} memeriksa status koneksi")
    
    update.message.reply_text('🔄 Memeriksa koneksi ke Mikrotik...')
    
    try:
        api = connect_to_mikrotik(config)
        if not api:
            update.message.reply_text('❌ Gagal terhubung ke Mikrotik. Periksa konfigurasi dan pastikan API aktif.')
            return
            
        # Ambil informasi sistem
        system_info = list(api.path('/system/resource'))
        if system_info:
            info = system_info[0]
            uptime = info.get('uptime', 'unknown')
            version = info.get('version', 'unknown')
            cpu_load = info.get('cpu-load', '0')
            free_memory = info.get('free-memory', '0')
            
            message = (
                f"✅ Terhubung ke Mikrotik\n\n"
                f"🖥️ IP: {config['IP_MIKROTIK']}\n"
                f"🔄 Versi: {version}\n"
                f"⏱️ Uptime: {uptime}\n"
                f"📊 CPU: {cpu_load}%\n"
                f"🧠 Free Memory: {int(free_memory)/1024/1024:.2f} MB"
            )
            update.message.reply_text(message)
        else:
            update.message.reply_text('✅ Terhubung ke Mikrotik, tetapi tidak dapat mengambil informasi sistem.')
            
        api.close()
    except Exception as e:
        logger.error(f"Error memeriksa status: {e}")
        update.message.reply_text(f'❌ Error saat memeriksa status Mikrotik: {str(e)}')

def detail_start(update: Update, context: CallbackContext) -> int:
    """Handler untuk command /detail"""
    config = load_config()
    if not config:
        update.message.reply_text('❌ Konfigurasi tidak ditemukan. Silakan atur melalui web interface.')
        return ConversationHandler.END
    
    user = update.effective_user
    logger.info(f"User {user.id} memulai melihat detail voucher")
    
    # Cek koneksi ke Mikrotik terlebih dahulu
    api = connect_to_mikrotik(config)
    if not api:
        update.message.reply_text('❌ Gagal terhubung ke Mikrotik. Periksa konfigurasi dan pastikan API aktif.')
        return ConversationHandler.END
    
    # Tutup koneksi setelah cek
    api.close()
    
    # Minta username voucher yang ingin dilihat detailnya
    update.message.reply_text(
        'Masukkan username voucher yang ingin dilihat detailnya:',
    )
    return DETAIL_USERNAME

def detail_get_username(update: Update, context: CallbackContext) -> int:
    """Handler untuk menerima username voucher yang akan dilihat detailnya"""
    username = update.message.text.strip()
    user = update.effective_user
    logger.info(f"User {user.id} melihat detail voucher untuk username: {username}")
    
    config = load_config()
    if not config:
        update.message.reply_text('❌ Konfigurasi tidak ditemukan.')
        return ConversationHandler.END
    
    update.message.reply_text(f'🔍 Mencari detail untuk username: {username}...')
    
    try:
        # Coba terhubung ke Mikrotik
        api = connect_to_mikrotik(config)
        if not api:
            update.message.reply_text('❌ Gagal terhubung ke Mikrotik.')
            return ConversationHandler.END
        
        # Cari user hotspot berdasarkan username
        try:
            users = api.path('ip/hotspot/user').select('name', 'profile', 'limit-uptime', 'uptime', 'disabled', 'comment', '.id')
            user_found = False
            user_data = None
            
            for u in users:
                if u.get('name') == username:
                    user_found = True
                    user_data = u
                    break
            
            if not user_found:
                api.close()
                update.message.reply_text(f'❌ Username "{username}" tidak ditemukan di daftar user hotspot.')
                return ConversationHandler.END
            
            # Ambil data tambahan dari active users jika ada
            active_data = None
            try:
                active_users = api.path('ip/hotspot/active').select('user', 'uptime', 'session-time-left', 'address', 'bytes-in', 'bytes-out')
                for active in active_users:
                    if active.get('user') == username:
                        active_data = active
                        break
            except Exception as e:
                logger.error(f"Error mengambil data active users: {e}")
            
            # Format pesan
            message = f"📋 Detail Voucher: {username}\n\n"
            message += f"👤 Username: {user_data.get('name', 'N/A')}\n"
            message += f"🔑 Profile: {user_data.get('profile', 'N/A')}\n"
            
            # Status aktif/nonaktif
            is_disabled = user_data.get('disabled', 'false') == 'true'
            message += f"🔴 Status: {'Dinonaktifkan' if is_disabled else 'Aktif'}\n"
            
            # Limit waktu dan penggunaan waktu
            limit_uptime = user_data.get('limit-uptime', 'Tidak ada')
            uptime = user_data.get('uptime', '0s')
            message += f"⏱️ Limit Waktu: {limit_uptime}\n"
            message += f"⌛ Waktu Terpakai: {uptime}\n"
            
            # Tambahkan data dari active user jika tersedia
            if active_data:
                message += f"\n📲 Status Koneksi: ONLINE\n"
                message += f"🕐 Sesi Waktu Tersisa: {active_data.get('session-time-left', 'N/A')}\n"
                message += f"🖥️ IP Address: {active_data.get('address', 'N/A')}\n"
                
                # Format penggunaan data
                bytes_in = int(active_data.get('bytes-in', '0'))
                bytes_out = int(active_data.get('bytes-out', '0'))
                download = format_bytes(bytes_in)
                upload = format_bytes(bytes_out)
                total = format_bytes(bytes_in + bytes_out)
                
                message += f"📥 Download: {download}\n"
                message += f"📤 Upload: {upload}\n"
                message += f"📊 Total Penggunaan: {total}\n"
            else:
                message += f"\n📲 Status Koneksi: OFFLINE\n"
            
            # Tambahkan komentar jika ada
            comment = user_data.get('comment')
            if comment:
                message += f"\n📝 Komentar: {comment}\n"
            
            # Tambahkan ID untuk keperluan admin
            message += f"\n🔢 ID: {user_data.get('.id', 'N/A')}"
            
            api.close()
            update.message.reply_text(message)
            
        except Exception as e:
            api.close()
            logger.error(f"Error mencari user: {e}")
            update.message.reply_text(f'❌ Error saat mencari user: {str(e)}')
    
    except Exception as e:
        logger.error(f"Error saat melihat detail voucher: {e}")
        update.message.reply_text(f'❌ Error: {str(e)}')
    
    return ConversationHandler.END

def format_bytes(size):
    """Format bytes menjadi ukuran yang readable"""
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def voucher(update: Update, context: CallbackContext) -> int:
    """Handler untuk command /voucher"""
    config = load_config()
    if not config:
        update.message.reply_text('❌ Konfigurasi tidak ditemukan. Silakan atur melalui web interface.')
        return ConversationHandler.END
    
    user = update.effective_user
    logger.info(f"User {user.id} memulai pembuatan voucher")
    
    update.message.reply_text('🔄 Menghubungkan ke Mikrotik...')
    
    api = connect_to_mikrotik(config)
    if not api:
        update.message.reply_text('❌ Gagal terhubung ke Mikrotik. Periksa konfigurasi dan pastikan API aktif.')
        return ConversationHandler.END
    
    profiles = get_hotspot_profiles(api)
    api.close()
    
    if not profiles:
        update.message.reply_text('❌ Tidak ada profile hotspot yang ditemukan. Pastikan konfigurasi hotspot sudah dibuat di Mikrotik.')
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(profile, callback_data=f'profile_{profile}')] for profile in profiles]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text('Pilih profile hotspot:', reply_markup=reply_markup)
    return PROFILE

def profile_callback(update: Update, context: CallbackContext) -> int:
    """Handler untuk callback pilihan profile"""
    query = update.callback_query
    query.answer()
    
    profile = query.data.replace('profile_', '')
    context.user_data['profile'] = profile
    logger.info(f"User memilih profile: {profile}")
    
    keyboard = [
        [InlineKeyboardButton("Random", callback_data='username_random')],
        [InlineKeyboardButton("Custom", callback_data='username_custom')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(text=f"Profile: {profile}\nPilih tipe username:", reply_markup=reply_markup)
    return USERNAME_TYPE

def username_type_callback(update: Update, context: CallbackContext) -> int:
    """Handler untuk callback tipe username"""
    query = update.callback_query
    query.answer()
    
    username_type = query.data.replace('username_', '')
    context.user_data['username_type'] = username_type
    logger.info(f"User memilih tipe username: {username_type}")
    
    if username_type == 'random':
        # Generate random username
        username = generate_random_string(8)
        context.user_data['username'] = username
        logger.info(f"Generated random username: {username}")
        
        # Langsung ke pilihan password
        keyboard = [
            [InlineKeyboardButton("Random", callback_data='password_random')],
            [InlineKeyboardButton("Sama dengan username", callback_data='password_same')],
            [InlineKeyboardButton("Custom", callback_data='password_custom')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            text=f"Profile: {context.user_data['profile']}\nUsername: {username}\nPilih tipe password:",
            reply_markup=reply_markup
        )
        return PASSWORD
    else:
        query.edit_message_text(text="Masukkan username yang diinginkan:")
        return USERNAME

def username_input(update: Update, context: CallbackContext) -> int:
    """Handler untuk input username custom"""
    username = update.message.text
    context.user_data['username'] = username
    logger.info(f"User memasukkan username custom: {username}")
    
    keyboard = [
        [InlineKeyboardButton("Random", callback_data='password_random')],
        [InlineKeyboardButton("Sama dengan username", callback_data='password_same')],
        [InlineKeyboardButton("Custom", callback_data='password_custom')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"Profile: {context.user_data['profile']}\nUsername: {username}\nPilih tipe password:",
        reply_markup=reply_markup
    )
    return PASSWORD

def password_callback(update: Update, context: CallbackContext) -> int:
    """Handler untuk callback tipe password"""
    query = update.callback_query
    query.answer()
    
    password_type = query.data.replace('password_', '')
    logger.info(f"User memilih tipe password: {password_type}")
    
    if password_type == 'random':
        # Generate random password
        password = generate_random_string(8)
        context.user_data['password'] = password
        logger.info(f"Generated random password: {password}")
        
        # Tanyakan limit
        query.edit_message_text(
            text=f"Profile: {context.user_data['profile']}\n"
                 f"Username: {context.user_data['username']}\n"
                 f"Password: {password}\n\n"
                 f"Masukkan limit waktu (contoh: 1h, 1d, none untuk tanpa batas):"
        )
        return LIMIT
    elif password_type == 'same':
        # Gunakan username sebagai password
        password = context.user_data['username']
        context.user_data['password'] = password
        logger.info(f"Menggunakan username sebagai password: {password}")
        
        # Tanyakan limit
        query.edit_message_text(
            text=f"Profile: {context.user_data['profile']}\n"
                 f"Username: {context.user_data['username']}\n"
                 f"Password: {password}\n\n"
                 f"Masukkan limit waktu (contoh: 1h, 1d, none untuk tanpa batas):"
        )
        return LIMIT
    else:
        # Custom password
        query.edit_message_text(text="Masukkan password yang diinginkan:")
        return PASSWORD

def password_input(update: Update, context: CallbackContext) -> int:
    """Handler untuk input password custom"""
    password = update.message.text
    context.user_data['password'] = password
    logger.info(f"User memasukkan password custom")
    
    update.message.reply_text(
        f"Profile: {context.user_data['profile']}\n"
        f"Username: {context.user_data['username']}\n"
        f"Password: {password}\n\n"
        f"Masukkan limit waktu (contoh: 1h, 1d, none untuk tanpa batas):"
    )
    return LIMIT

def limit_input(update: Update, context: CallbackContext) -> int:
    """Handler untuk input limit waktu"""
    limit = update.message.text.strip().lower()
    logger.info(f"User memasukkan limit waktu: {limit}")
    
    if limit == 'none':
        context.user_data['limit'] = None
    else:
        context.user_data['limit'] = limit
    
    update.message.reply_text(
        f"Profile: {context.user_data['profile']}\n"
        f"Username: {context.user_data['username']}\n"
        f"Password: {context.user_data['password']}\n"
        f"Limit: {limit}\n\n"
        f"Masukkan komentar (opsional, ketik 'none' untuk kosong):"
    )
    return COMMENT

def comment_input(update: Update, context: CallbackContext) -> int:
    """Handler untuk input komentar"""
    comment = update.message.text.strip()
    logger.info(f"User memasukkan komentar: {comment}")
    
    if comment.lower() == 'none':
        context.user_data['comment'] = None
    else:
        context.user_data['comment'] = comment
    
    update.message.reply_text("🔄 Membuat voucher...")
    
    # Buat voucher
    result = create_voucher(context.user_data)
    
    if result[0]:
        # Berhasil
        update.message.reply_text(
            f"✅ Voucher berhasil dibuat!\n\n"
            f"Profile: {context.user_data['profile']}\n"
            f"Username: {context.user_data['username']}\n"
            f"Password: {context.user_data['password']}\n"
            f"Limit: {context.user_data['limit'] if context.user_data['limit'] else 'Tidak ada'}\n"
            f"Komentar: {context.user_data['comment'] if context.user_data['comment'] else 'Tidak ada'}"
        )
    else:
        # Gagal
        update.message.reply_text(f"❌ Gagal membuat voucher: {result[1]}")
    
    return ConversationHandler.END

def create_voucher(user_data):
    """Fungsi untuk membuat voucher di Mikrotik Hotspot"""
    config = load_config()
    if not config:
        return False, "Konfigurasi tidak ditemukan"
    
    logger.info(f"Membuat voucher untuk username: {user_data['username']}")
    
    try:
        api = connect_to_mikrotik(config)
        if not api:
            return False, "Tidak dapat terhubung ke Mikrotik. Periksa konfigurasi dan pastikan API aktif."
        
        params = {
            'name': user_data['username'],
            'password': user_data['password'],
            'profile': user_data['profile'],
        }
        
        if user_data.get('limit'):
            params['limit-uptime'] = user_data['limit']
        
        if user_data.get('comment'):
            params['comment'] = user_data['comment']
        
        # Tambahkan user hotspot baru
        api.path('ip/hotspot/user').add(**params)
        
        api.close()
        logger.info(f"Voucher berhasil dibuat untuk username: {user_data['username']}")
        return True, "Voucher berhasil dibuat"
    except librouteros.exceptions.ConnectionClosed as e:
        logger.error(f"Error koneksi saat membuat voucher: {e}")
        return False, f"Error koneksi: {str(e)}"
    except Exception as e:
        logger.error(f"Error creating voucher: {e}")
        return False, str(e)

def list_vouchers(update: Update, context: CallbackContext) -> None:
    """Handler untuk command /list"""
    config = load_config()
    if not config:
        update.message.reply_text('❌ Konfigurasi tidak ditemukan. Silakan atur melalui web interface.')
        return
    
    user = update.effective_user
    logger.info(f"User {user.id} meminta daftar voucher")
    
    update.message.reply_text('🔄 Mengambil daftar voucher...')
    
    api = connect_to_mikrotik(config)
    if not api:
        update.message.reply_text('❌ Gagal terhubung ke Mikrotik. Periksa konfigurasi dan pastikan API aktif.')
        return
    
    try:
        users = api.path('ip/hotspot/user')
        user_list = list(users)
        api.close()
        
        if not user_list:
            update.message.reply_text('ℹ️ Tidak ada user hotspot yang ditemukan.')
            return
        
        # Batasi daftar ke 10 user terakhir
        last_users = user_list[-10:] if len(user_list) > 10 else user_list
        
        message = "📋 Daftar 10 User Hotspot Terakhir:\n\n"
        for user in last_users:
            message += f"👤 Username: {user.get('name', 'N/A')}\n"
            message += f"🔑 Profile: {user.get('profile', 'N/A')}\n"
            message += f"⏱️ Limit: {user.get('limit-uptime', 'Tidak ada')}\n"
            message += f"📝 Komentar: {user.get('comment', 'Tidak ada')}\n"
            message += "----------------------\n"
        
        update.message.reply_text(message)
        logger.info(f"Berhasil menampilkan {len(last_users)} voucher")
    except Exception as e:
        logger.error(f"Error saat mengambil daftar user: {e}")
        update.message.reply_text(f'❌ Gagal mendapatkan daftar user: {str(e)}')

def main():
    """Fungsi utama untuk menjalankan bot"""
    # Periksa file konfigurasi
    config = load_config()
    if not config:
        logger.error("Config file tidak ditemukan. Buat konfigurasi melalui web interface terlebih dahulu.")
        print("ERROR: Config file tidak ditemukan. Buat konfigurasi melalui web interface terlebih dahulu.")
        return
    
    # Periksa token Telegram
    token = config.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("Token Telegram tidak ditemukan di konfigurasi")
        print("ERROR: Token Telegram tidak ditemukan di konfigurasi")
        return
    
    try:
        logger.info(f"Memulai bot dengan token: {token[:5]}...{token[-5:]}")
        updater = Updater(token)
        dispatcher = updater.dispatcher
        
        # Menambahkan handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("list", list_vouchers))
        dispatcher.add_handler(CommandHandler("status", status))
        
        # Conversation handler untuk pembuatan voucher
        voucher_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('voucher', voucher)],
            states={
                PROFILE: [CallbackQueryHandler(profile_callback, pattern='^profile_')],
                USERNAME_TYPE: [CallbackQueryHandler(username_type_callback, pattern='^username_')],
                USERNAME: [MessageHandler(Filters.text & ~Filters.command, username_input)],
                PASSWORD: [
                    CallbackQueryHandler(password_callback, pattern='^password_'),
                    MessageHandler(Filters.text & ~Filters.command, password_input)
                ],
                LIMIT: [MessageHandler(Filters.text & ~Filters.command, limit_input)],
                COMMENT: [MessageHandler(Filters.text & ~Filters.command, comment_input)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        dispatcher.add_handler(voucher_conv_handler)
        
        # Conversation handler untuk detail voucher
        detail_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('detail', detail_start)],
            states={
                DETAIL_USERNAME: [MessageHandler(Filters.text & ~Filters.command, detail_get_username)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        dispatcher.add_handler(detail_conv_handler)
        
        # Memulai polling
        logger.info("Bot started polling")
        print("Bot Telegram sudah berjalan!")
        updater.start_polling()
        updater.idle()
    except telegram.error.InvalidToken:
        logger.error("Token Telegram tidak valid")
        print("ERROR: Token Telegram tidak valid")
    except telegram.error.Unauthorized:
        logger.error("Token Telegram tidak sah atau sudah dicabut")
        print("ERROR: Token Telegram tidak sah atau sudah dicabut")
    except Exception as e:
        logger.error(f"Error saat menjalankan bot: {e}")
        print(f"ERROR: Terjadi kesalahan saat menjalankan bot: {e}")

if __name__ == '__main__':
    # Pastikan folder log ada
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_bot.log')
    if not os.path.exists(log_file):
        open(log_file, 'w').close()
        print(f"Membuat file log: {log_file}")
    
    main() 