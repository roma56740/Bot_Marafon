import telebot
from telebot import types
import os
import json
import datetime
import threading
import time
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

PROGRESS_FILE = 'data/user_progress.json'

if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, 'r') as f:
        user_progress = json.load(f)
else:
    user_progress = {}

with open('data/course_days.json', 'r', encoding='utf-8') as f:
    course_days = json.load(f)

user_messages = {}

def save_progress():
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(user_progress, f)

def get_next_day(user_id):
    return user_progress.get(str(user_id), 0) + 1

def schedule_daily_send():
    def run():
        while True:
            now = datetime.datetime.now()
            if now.hour == 8 and now.minute == 0:
                for user_id in user_progress:
                    next_day = get_next_day(user_id)
                    if str(next_day) in course_days:
                        send_day_content(int(user_id), next_day)
                time.sleep(60)
            time.sleep(10)
    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('🌿 Начать'))

    photo_path = "audio/start.jpeg"  # или другой путь/имя
    if os.path.exists(photo_path):
        with open(photo_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo)

    # Приветствие
    bot.send_message(message.chat.id, course_days["intro"], reply_markup=markup)

    # 📎 Отправка и закрепление документа
    doc_path = "audio/Дневник.docx"
    if os.path.exists(doc_path):
        with open(doc_path, 'rb') as doc_file:
            doc_msg = bot.send_document(message.chat.id, doc_file, caption="📝 Твой личный дневник курса")
            try:
                bot.pin_chat_message(message.chat.id, doc_msg.message_id)
            except Exception as e:
                print("Не удалось закрепить сообщение:", e)

    # 🎧 Отправка аудио-вступления
    audio_intro = "audio/intro.m4a"
    if os.path.exists(audio_intro):
        warning = bot.send_message(message.chat.id, "⏳ Подождите, загружается аудиофайл. Не нажимайте на кнопки в это время...")
        bot.send_audio(message.chat.id, open(audio_intro, 'rb'))
        bot.delete_message(message.chat.id, warning.message_id)

@bot.message_handler(func=lambda message: message.text == '🌿 Начать')
def start_course(message):
    user_id = str(message.chat.id)
    current_day = user_progress.get(user_id)

    if current_day is None:
        user_progress[user_id] = 1
        save_progress()

        send_day_content(message.chat.id, 1)
    else:
        bot.send_message(message.chat.id, "Ты уже начал курс. Новый день откроется завтра в 8:00 по МСК, после выполнения предыдущего.")

@bot.message_handler(func=lambda message: message.text == '❓ Помощь')
def send_help(message):
    bot.send_message(message.chat.id,
        "Добро пожаловать в телесный курс.\n\n"
        "🟢 'Начать' — запускает курс с самого начала.\n"
        "📖 'Открытые дни' — показывает список уже выполненных дней, их можно переслушать.\n"
        "✅ 'Выполнил(а)' — нажмите после выполнения практики, чтобы открыть доступ к следующему дню.\n"
        "❗ Дни приходят автоматически в 8:00 по МСК.\n"
        "❗ Не нажимайте кнопки во время загрузки аудио — дождитесь окончания!\n"
        "Если что-то непонятно — просто напишите сюда, я помогу."
    )

@bot.message_handler(func=lambda message: message.text == '📖 Открытые дни')
def show_open_days(message):
    user_id = str(message.chat.id)
    max_day = user_progress.get(user_id, 0)
    if max_day < 1:
        bot.send_message(message.chat.id, "У тебя пока нет выполненных дней. Начни с кнопки 🌿 'Начать'")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for day in range(1, max_day + 1):
        row.append(types.KeyboardButton(f"📅 День {day}"))
        if len(row) == 2:
            markup.add(*row)
            row = []
    if row:
        markup.add(*row)
    markup.add(types.KeyboardButton('🔙 Назад'))
    bot.send_message(message.chat.id, "Выбери день, чтобы пересмотреть его:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text.startswith('📅 День'))
def view_day_content(message):
    try:
        day = int(message.text.replace('📅 День', '').strip())
        day_str = str(day)
        day_data = course_days[day_str]

        warn_msg = bot.send_message(message.chat.id, "⏳ Подождите, загружается аудиофайл. Не нажимайте на кнопки в это время...")

        bot.send_message(message.chat.id, f"📅 {day_data['title']}\n\n👋 {day_data['intro']}")
        audio_path = f"audio/{day_str}.m4a"
        if os.path.exists(audio_path):
            bot.send_audio(message.chat.id, open(audio_path, 'rb'))
        bot.delete_message(message.chat.id, warn_msg.message_id)

        bot.send_message(message.chat.id, f"📝 Практика:\n{day_data['practice']}")
        bot.send_message(message.chat.id, f"📩 {day_data['closing']}")
    except:
        bot.send_message(message.chat.id, "Произошла ошибка при загрузке дня. Попробуй снова.")

def send_day_content(chat_id, day):
    day_str = str(day)
    if day_str not in course_days:
        return
    day_data = course_days[day_str]

    user_progress[str(chat_id)] = day
    save_progress()

    sent = bot.send_message(chat_id, f"📅 {day_data['title']}\n\n👋 {day_data['intro']}")
    user_messages[chat_id] = {'text': sent.message_id}

    audio_path = f"audio/{day_str}.m4a"
    if os.path.exists(audio_path):
        warn_msg = bot.send_message(chat_id, "⏳ Подождите, загружается аудиофайл. Не нажимайте на кнопки в это время...")
        audio_msg = bot.send_audio(chat_id, open(audio_path, 'rb'))
        bot.delete_message(chat_id, warn_msg.message_id)
        user_messages[chat_id]['audio'] = audio_msg.message_id

    practice_msg = bot.send_message(chat_id, f"📝 Практика:\n{day_data['practice']}")
    user_messages[chat_id]['practice'] = practice_msg.message_id

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("✅ Выполнил(а)"))
    markup.add(types.KeyboardButton("📖 Открытые дни"), types.KeyboardButton("❓ Помощь"))
    instruction_msg = bot.send_message(chat_id, "Когда выполнишь практику — нажми кнопку:", reply_markup=markup)
    user_messages[chat_id]['instruction'] = instruction_msg.message_id

@bot.message_handler(func=lambda message: message.text == "✅ Выполнил(а)")
def handle_day_done(message):
    user_id = str(message.chat.id)
    current_day = user_progress.get(user_id, 0)
    if current_day >= 1:
        user_progress[user_id] = current_day
        save_progress()

        # ❌ Удаляем только кнопку "Выполнил(а)" — меняем клавиатуру
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📖 Открытые дни"), types.KeyboardButton("❓ Помощь"))
        bot.send_message(message.chat.id, 
                         f"📩 День {current_day} выполнен! Его можно пересмотреть через 📖 Открытые дни.\n⏰ Следующий день откроется завтра в 8:00 по МСК.", 
                         reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '🔙 Назад')
def back_to_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("✅ Выполнил(а)"))
    markup.add(types.KeyboardButton("📖 Открытые дни"), types.KeyboardButton("❓ Помощь"))
    msg = bot.send_message(message.chat.id, "🔁 Переход в меню...", reply_markup=markup)

    # Удалить сообщение через 3 секунды, не блокируя поток
    def delete_msg():
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

    threading.Timer(3, delete_msg).start()


schedule_daily_send()
bot.polling(none_stop=True)