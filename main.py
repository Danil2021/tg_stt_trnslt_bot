import telebot
from telebot import types
import requests
import os
import subprocess
from openai import OpenAI
import translators as ts
from resemble import Resemble
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient
from httpx import HTTPStatusError

token = 'API_KEY'
bot = telebot.TeleBot(token)
API_KEY = "API_KEY"
Resemble.api_key('API_KEY')
LANG = None



def tts(text, lang):
    project_uuid = '019a1e23'
    voice_uuid = Resemble.v2.voices.all(1, 10)['items'][0]['uuid']
    if lang == 'ru':
        body = f'<lang xml:lang="ru-ru">{text}</lang>'
    else:
        body = f'<lang xml:lang="zh-cn">{text}</lang>'
    response = Resemble.v2.clips.create_sync(project_uuid,
                                             voice_uuid,
                                             body,
                                             title='clip1',
                                             sample_rate=22050,
                                             output_format='wav',
                                             precision='PCM_16',
                                             include_timestamps=None,
                                             is_archived=None,
                                             raw=None)
    print(response)
    audio_url = response['item']['audio_src']
    audio_response = requests.get(audio_url)
    with open('tmp/output.wav', 'wb') as file:
        file.write(audio_response.content)
    return 1


def translate_to_user_lang(text, source_lang, user_lang):
    result = ts.translate_text(text, translator='bing', from_language=source_lang, to_language=user_lang)
    return result

def stt(file, lang):

    settings = ConnectionSettings(
        url="https://asr.api.speechmatics.com/v2",
        auth_token=API_KEY,
    )
    conf = {
        "type": "transcription",
        "transcription_config": {
            "language": lang
        }
    }
    with BatchClient(settings) as client:
        try:
            job_id = client.submit_job(
                audio=file,
                transcription_config=conf,
            )
            transcript = client.wait_for_completion(job_id, transcription_format='txt')
            return transcript
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                return 'Invalid API key - Check your API_KEY at the top of the code!'
            elif e.response.status_code == 400:
                return e.response.json()['detail']
            else:
                raise e


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
    #with open(f"tmp/{fname[:-4]}.wav", "rb") as audio_file:
    #    transcription = client.audio.transcriptions.create(
    #        model="whisper-1",
    #        file=audio_file,
    #        response_format="text")
    bot.send_message(message.chat.id, text='Странно, почему настолько дольше')
    if LANG == 'ru':
        transcription = stt(f"tmp/{fname[:-4]}.wav", 'ru')
        bot.send_message(message.chat.id, text=transcription)
        transcription = translate_to_user_lang(transcription, source_lang='ru', user_lang='zh-Hans')
        a = tts(transcription, lang='zh')
        with open('tmp/output.wav', 'rb') as audio:
            bot.send_audio(message.from_user.id, audio)
            bot.send_message(message.chat.id, transcription)
    elif LANG == 'zh':
        transcription = stt(f"tmp/{fname[:-4]}.wav", 'cmn')
        bot.send_message(message.chat.id, text=transcription)
        transcription = translate_to_user_lang(transcription, source_lang='zh-Hans', user_lang='ru')
        a = tts(transcription, lang='ru')
        bot.send_message(message.chat.id, transcription)
        with open('tmp/output.wav', 'rb') as audio:
            bot.send_audio(message.from_user.id, audio)
    else:
        bot.send_message(message.chat.id, "Unknown translation")

    os.remove(f'tmp/{fname[:-4]}.wav')
    os.remove(f'tmp/{fname}')
