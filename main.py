import telebot
from telebot import types
import requests
import os
import subprocess
from openai import OpenAI
import translators as ts

token = 'API_KEY'
bot = telebot.TeleBot(token)
client = OpenAI(
    api_key='API_KEY')
LANG = None


def translate_to_user_lang(text, source_lang, user_lang):
    result = ts.translate_text(text, translator='bing', from_language=source_lang, to_language=user_lang)
    return result


def create_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = types.KeyboardButton("ru-zh")
    button2 = types.KeyboardButton("zh-ru")
    keyboard.add(button1, button2)
    return keyboard


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Выбери одну из кнопок ниже:", reply_markup=create_keyboard())


@bot.message_handler(func=lambda message: True)
def handle_text(message):
    global LANG
    if message.text == "ru-zh":
        bot.reply_to(message, "Russian to Chinese")
        LANG = 'ru'
    elif message.text == "zh-ru":
        LANG = 'zh'
        bot.reply_to(message, "Chinese to Russian")


@bot.message_handler(content_types=['voice'])
def get_audio_messages(message):
    file_info = bot.get_file(message.voice.file_id)
    path = file_info.file_path
    fname = os.path.basename(path).lstrip('file_')
    doc = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(token, file_info.file_path))
    with open('tmp/' + fname, 'wb') as f:
        f.write(doc.content)
    subprocess.call(['ffmpeg', '-y', '-i', f'tmp/{fname}', f'tmp/{fname[:-4]}.wav'])
    with open(f"tmp/{fname[:-4]}.wav", "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text")
    if LANG == 'ru':
        transcription = translate_to_user_lang(transcription, source_lang='ru', user_lang='zh-Hans')
        bot.send_message(message.chat.id, transcription)
    elif LANG == 'zh':
        transcription = translate_to_user_lang(transcription, source_lang='zh-Hans', user_lang='ru')
        bot.send_message(message.chat.id, transcription)

    os.remove(f'tmp/{fname[:-4]}.wav')
    os.remove(f'tmp/{fname}')
