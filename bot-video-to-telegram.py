import asyncio
import logging
import os

import instaloader
import yt_dlp as youtube_dl
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InputFile
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
print(InputFile)

# Configuración de logging con fecha y hora
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Inicializa el bot y el despachador
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Carpeta donde se guardarán los videos
DOWNLOAD_FOLDER = 'telegramBotVideos'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Reuse the Instagram downloader session
L = instaloader.Instaloader(download_video_thumbnails=False, save_metadata=False, download_comments=False)

async def login_instagram():
    """Función para iniciar sesión en Instagram."""
    try:
        L.login(os.getenv('INSTAGRAM_USERNAME'), os.getenv('INSTAGRAM_PASSWORD'))
        logging.info("Login exitoso en Instagram")
        return True
    except instaloader.exceptions.BadCredentialsException:
        logging.error("Credenciales de Instagram incorrectas.")
        return False
    except instaloader.exceptions.ConnectionException:
        logging.error("Error de conexión a Instagram.")
        return False

async def download_instagram_video(post_url):
    """Descargar video de Instagram."""
    logging.info(f"Descargando video de Instagram desde URL: {post_url}")
    try:
        shortcode = post_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=DOWNLOAD_FOLDER)
        for root, _, files in os.walk(DOWNLOAD_FOLDER):
            for file in files:
                if file.endswith(".mp4"):
                    logging.info(f"Video descargado: {file}")
                    return os.path.join(root, file)
        logging.warning("No se encontró ningún archivo de video en el directorio.")
        return None
    except Exception as e:
        logging.error(f"Error descargando el video de Instagram: {e}")
        return None

async def download_video(url):
    """Descargar video de Twitter o TikTok."""
    logging.info(f"Descargando video de URL: {url}")
    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title).40s.%(ext)s'),
            'format': 'best[ext=mp4]',
            'nocheckcertificate': True,
            'restrictfilenames': True
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(result)
            logging.info(f"Video descargado: {filename}")
            return filename
    except Exception as e:
        logging.error(f"Error descargando el video: {e}")
        return None

# Comando /start
@dp.message(F.text.startswith('/start'))
async def send_welcome(message: types.Message):
    await message.reply("¡Hola! Envíame la URL de un video de Instagram, Twitter o TikTok para descargarlo.")

# Manejo de mensajes para links de Instagram, Twitter, TikTok y X.com (Twitter)
@dp.message(F.text.contains("instagram.com") | 
            F.text.contains("twitter.com") | 
            F.text.contains("tiktok.com") | 
            F.text.contains("x.com"))
async def handle_message(message: types.Message):
    post_url = message.text
    logging.info(f"Recibido mensaje con URL: {post_url}")
    video_path = None

    if "instagram.com" in post_url:
        await message.reply('Iniciando descarga de Instagram...')
        video_path = await download_instagram_video(post_url)
    elif any(domain in post_url for domain in ["twitter.com", "x.com", "tiktok.com"]):
        await message.reply('Iniciando descarga de video...')
        video_path = await download_video(post_url)
    else:
        await message.reply('URL no válida. Envíame una URL de Instagram, Twitter o TikTok.')
        return
    if video_path:
        try:
            # Convert the relative path to an absolute path
            absolute_video_path = os.path.abspath(video_path)
            logging.info(f"Sending video from: {absolute_video_path}")

            # Check if the file exists
            if os.path.exists(absolute_video_path):
                logging.info(f"File found: {absolute_video_path}")

                # Open the file explicitly and pass as InputFile
                with open(absolute_video_path, 'rb') as video_file:
                    logging.info(f"File opened successfully: {absolute_video_path}")
                    
                    # Wrap the file object in InputFile
                    video = types.InputFile(video_file, filename=os.path.basename(absolute_video_path))
                    
                    # Send the file as a document
                    await bot.send_document(chat_id=message.chat.id, document=video)

                os.remove(absolute_video_path)  # Clean up after sending
            else:
                logging.error(f"File not found: {absolute_video_path}")
                await message.reply("No se pudo encontrar el archivo de video.")
        except Exception as e:
            logging.error(f"Exception when sending video: {e}")
            await message.reply(f'Error al enviar el video: {e}')


# Manejo de todos los demás mensajes no filtrados
@dp.message()
async def handle_unhandled_message(message: types.Message):
    logging.warning(f"Mensaje no manejado: {message.text}")
    await message.reply("No pude procesar el mensaje. Por favor, envía una URL válida.")


async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

