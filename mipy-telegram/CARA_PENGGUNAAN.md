# Cara Penggunaan Aplikasi Mikrotik Hotspot Voucher Generator

## Persiapan Awal

1. Pastikan Python (versi 3.7 atau lebih baru) sudah terinstal di komputer Anda
2. Instal semua dependensi dengan menjalankan:
   ```
   pip install -r requirements.txt
   ```
3. Buat bot Telegram baru:
   - Buka Telegram dan cari @BotFather
   - Kirim perintah `/newbot` dan ikuti instruksi
   - Salin token yang diberikan

4. Dapatkan Chat ID Telegram Anda:
   - Mulai chat dengan bot @userinfobot di Telegram
   - Bot akan mengirimkan ID Anda, salin nomor ini

5. Pastikan API di Mikrotik sudah diaktifkan:
   - Login ke RouterOS
   - Buka menu IP > Services
   - Pastikan service API aktif (port default 8728)
   - Jika menggunakan SSL, aktifkan juga API-SSL (port default 8729)

## Menjalankan Aplikasi

### Cara Mudah (Windows)
1. Klik dua kali pada file `start.bat`
2. Browser akan terbuka secara otomatis dengan alamat http://localhost:5000

### Cara Manual
1. Jalankan semua dalam satu perintah: `python run.py`

### Cara Terpisah
1. Jalankan aplikasi web: `python app.py`
2. Buka browser dan akses http://localhost:5000
3. Setelah konfigurasi disimpan, jalankan bot telegram: `python telegram_bot.py`

## Konfigurasi Web Interface

1. Isi form konfigurasi:
   - **IP Mikrotik**: Alamat IP router Mikrotik Anda
   - **Port API Mikrotik**: Port API Mikrotik (default: 8728, untuk API-SSL: 8729)
   - **Gunakan SSL**: Aktifkan jika router menggunakan API-SSL
   - **Verifikasi SSL**: Matikan jika menggunakan sertifikat self-signed
   - **Username Mikrotik**: Username untuk login ke router
   - **Password Mikrotik**: Password untuk login ke router
   - **Token Bot Telegram**: Token yang diberikan oleh BotFather
   - **Chat ID Telegram**: ID chat Telegram Anda

2. Klik tombol "Test Koneksi Mikrotik" untuk memeriksa koneksi ke router
3. Klik tombol "Test Koneksi Telegram" untuk memeriksa koneksi ke Telegram
4. Klik "Simpan Konfigurasi" untuk menyimpan pengaturan

## Menggunakan Bot Telegram

1. Mulai chat dengan bot Telegram Anda (bot yang dibuat di BotFather)
2. Kirim perintah `/start` untuk memulai
3. Perintah yang tersedia:
   - `/voucher` - Untuk membuat voucher baru
   - `/list` - Untuk melihat daftar voucher yang ada
   - `/status` - Untuk melihat status koneksi Mikrotik
   - `/detail` - Untuk melihat detail penggunaan voucher tertentu

### Membuat Voucher Baru

1. Kirim perintah `/voucher`
2. Bot akan menampilkan daftar profile hotspot yang tersedia, pilih salah satu
3. Pilih tipe username:
   - **Random** - Username akan dibuat secara acak
   - **Custom** - Anda dapat menentukan username

4. Pilih tipe password:
   - **Random** - Password akan dibuat secara acak
   - **Sama dengan username** - Password akan sama dengan username
   - **Custom** - Anda dapat menentukan password

5. Masukkan limit waktu:
   - Format: 1h (1 jam), 1d (1 hari), 3d (3 hari), dll
   - Ketik `none` untuk tanpa batas waktu

6. Masukkan komentar (opsional):
   - Masukkan teks komentar
   - Ketik `none` untuk tanpa komentar

7. Bot akan membuat voucher dan menampilkan detailnya

### Melihat Detail Penggunaan Voucher

1. Kirim perintah `/detail`
2. Masukkan username voucher yang ingin dilihat detailnya
3. Bot akan menampilkan informasi lengkap tentang voucher tersebut:
   - Username dan profile
   - Status aktif/nonaktif
   - Limit waktu dan waktu yang terpakai
   - Status koneksi (online/offline)
   - Jika online: IP address, waktu tersisa, penggunaan data (download/upload)
   - Komentar (jika ada)

## Log dan Troubleshooting

File log tersedia untuk membantu troubleshooting:
- `app.log` - Log aplikasi web
- `telegram_bot.log` - Log bot Telegram

### Masalah Umum

1. **Tidak dapat terhubung ke Mikrotik**:
   - Pastikan IP, port, username, dan password benar
   - Pastikan API service aktif di RouterOS
   - Jika menggunakan SSL, pastikan API-SSL aktif
   - Periksa firewall Mikrotik
   - Coba matikan SSL verification jika menggunakan self-signed certificate

2. **Tidak dapat terhubung ke Telegram**:
   - Pastikan token bot valid (format: angka:string)
   - Pastikan bot sudah dimulai dengan `/start`
   - Periksa apakah chat ID benar
   - Periksa koneksi internet

3. **Bot tidak merespons**:
   - Pastikan skrip telegram_bot.py masih berjalan
   - Restart aplikasi dengan `python run.py`
   - Periksa file log untuk melihat error

4. **Voucher tidak muncul di Mikrotik**:
   - Periksa apakah user memiliki hak akses untuk membuat user hotspot
   - Pastikan profile yang dipilih memang ada di Mikrotik 