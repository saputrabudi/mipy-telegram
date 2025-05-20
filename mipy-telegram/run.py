import subprocess
import sys
import threading
import time
import os

def run_flask_app():
    print("Menjalankan aplikasi web Flask...")
    subprocess.run([sys.executable, 'app.py'])

def run_telegram_bot():
    print("Menjalankan bot Telegram...")
    subprocess.run([sys.executable, 'telegram_bot.py'])

def main():
    # Buat direktori templates jika belum ada
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Jalankan aplikasi web dan bot secara parallel
    web_thread = threading.Thread(target=run_flask_app)
    bot_thread = threading.Thread(target=run_telegram_bot)
    
    web_thread.daemon = True
    bot_thread.daemon = True
    
    web_thread.start()
    
    # Tunggu beberapa detik sebelum memulai bot
    time.sleep(5)
    bot_thread.start()
    
    print("====================================================")
    print("Aplikasi Mikrotik Hotspot Voucher Generator berjalan")
    print("====================================================")
    print("Akses web interface di: http://localhost:5000")
    print("Bot Telegram sudah aktif (jika konfigurasi sudah diatur)")
    print("\nTekan Ctrl+C untuk keluar")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMenghentikan aplikasi...")

if __name__ == "__main__":
    main() 