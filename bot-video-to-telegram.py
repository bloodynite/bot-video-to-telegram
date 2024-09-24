import logging
import os

import instaloader
import yt_dlp as youtube_dl
from dotenv import load_dotenv
from telegram import Update
from telegram.error import NetworkError, TelegramError
from telegram.ext import (Application, CallbackContext, CommandHandler,
                          ConversationHandler, MessageHandler, filters)

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Token del bot de Telegram y credenciales de Instagram desde .env
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

# Carpeta donde se guardarán los videos
DOWNLOAD_FOLDER = 'telegramBotVideos'

# Crear la carpeta si no existe
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Ajustar el nivel de logging para la biblioteca de Telegram
telegram_logger = logging.getLogger('telegram')
telegram_logger.setLevel(logging.WARNING)  # Solo mostrará advertencias y errores, no solicitudes de "getUpdates"


# Estados de la conversación
WAITING_FOR_URL = range(1)

# Función para limpiar la carpeta antes de una nueva descarga
def clean_download_folder():
    logging.info("Limpiando la carpeta de descargas.")
    for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file_path}")
            except Exception as e:
                logging.error(f"Error al eliminar el archivo {file_path}: {e}")

# Función para descargar el video de Instagram
def download_instagram_video(post_url):
    clean_download_folder()  # Limpiar la carpeta antes de la descarga

    L = instaloader.Instaloader(
        download_video_thumbnails=False, 
        save_metadata=False, 
        download_comments=False,
        filename_pattern="{shortcode}"  # Evitar sobrescribir por nombre repetido
    )

    # Iniciar sesión en Instagram
    try:
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        logging.info("Sesión iniciada correctamente en Instagram.")
    except instaloader.exceptions.BadCredentialsException:
        logging.error("Credenciales de Instagram incorrectas.")
        return None
    except instaloader.exceptions.ConnectionException:
        logging.error("Error de conexión a Instagram.")
        return None
    except Exception as e:
        logging.error(f"Error al iniciar sesión en Instagram: {e}")
        return None

    try:
        shortcode = post_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=DOWNLOAD_FOLDER)
        for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
            for file in files:
                if file.endswith(".mp4"):
                    logging.info(f"Video descargado correctamente: {file}")
                    return os.path.join(root, file)
        logging.warning("No se encontró ningún archivo de video en el directorio.")
        return None
    except instaloader.exceptions.QueryReturnedBadRequestException:
        logging.error("Consulta incorrecta a Instagram.")
        return None
    except instaloader.exceptions.LoginRequiredException:
        logging.error("Se requiere inicio de sesión para acceder al contenido de Instagram.")
        return None
    except Exception as e:
        logging.error(f"Error descargando el video de Instagram: {e}")
        return None

# Función para descargar el video de Twitter o TikTok
def download_video(url):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title).40s.%(ext)s'),  # Guardar en la carpeta videosConverter
            'format': 'best[ext=mp4]',
            'nocheckcertificate': True,  # Ignorar verificación de certificado si es necesario
            'restrictfilenames': True  # Remueve caracteres problemáticos del nombre del archivo
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(result)
            logging.info(f"Video descargado correctamente: {filename}")
            return filename
    except Exception as e:
        logging.error(f"Error descargando el video: {e}")
        return None

# Comando de inicio
async def start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user = update.message.from_user
    first_name = user.first_name
    last_name = user.last_name
    username = user.username

    if last_name is not None:
        full_name = f"{first_name} {last_name}"
    else:
        full_name = first_name

    logging.info(f"El usuario {full_name} ({username}#{user_id}) está utilizando el bot.")

    await update.message.reply_text(
        'Hola! Por favor, envíame la URL de la publicación de Instagram, Twitter o TikTok para descargar el video.'
    )
    logging.info("Esperando URL")
    return WAITING_FOR_URL

# Manejar mensajes con URL de Instagram, Twitter o TikTok
async def handle_message(update: Update, context: CallbackContext) -> int:
    post_url = update.message.text
    chat_id = update.message.chat_id

    video_path = None
    if "instagram.com" in post_url:
        await context.bot.send_message(chat_id=chat_id, text='Iniciando descarga de Instagram...')
        logging.info(f"Iniciando descarga de Instagram para URL: {post_url}")
        video_path = download_instagram_video(post_url)
    elif "twitter.com" in post_url or "x.com" in post_url:
        await context.bot.send_message(chat_id=chat_id, text='Iniciando descarga de Twitter...')
        logging.info(f"Iniciando descarga de Twitter para URL: {post_url}")
        video_path = download_video(post_url)
    elif "tiktok.com" in post_url:
        await context.bot.send_message(chat_id=chat_id, text='Iniciando descarga de TikTok...')
        logging.info(f"Iniciando descarga de TikTok para URL: {post_url}")
        video_path = download_video(post_url)
    else:
        await context.bot.send_message(chat_id=chat_id, text='Estoy esperando una URL válida de Instagram, Twitter o TikTok.')
        logging.warning(f"URL no válida recibida: {post_url}")
        return WAITING_FOR_URL

    if video_path:
        try:
            with open(video_path, 'rb') as video_file:
                await context.bot.send_video(chat_id=chat_id, video=video_file)
            await context.bot.send_message(chat_id=chat_id, text='Aquí está tu video.')
            logging.info(f"Video enviado correctamente a {chat_id}.")
        except (NetworkError, TelegramError) as e:
            await context.bot.send_message(chat_id=chat_id, text=f'Error al enviar el video: {e}')
            logging.error(f"Error al enviar el video: {e}")
    else:
        await context.bot.send_message(chat_id=chat_id, text='No se pudo descargar el video. Por favor, verifica la URL.')
        logging.error("No se pudo descargar el video. Verificar la URL.")
    return WAITING_FOR_URL

# Cancelar la conversación
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Operación cancelada.')
    logging.info("Operación cancelada por el usuario.")
    return ConversationHandler.END

# Configurar y ejecutar el bot
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_FOR_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    logging.info("Bot iniciado y esperando mensajes.")
    application.run_polling()

if __name__ == "__main__":
    main()
