import telebot
from telebot import types
from datetime import datetime
from datetime import timedelta
import os
import sys
from dotenv import load_dotenv
from db import db, init_db, DatabaseContext

# Загрузка токена для бота из переменной окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализируем БД
init_db()

bot = telebot.TeleBot(BOT_TOKEN)

topics_base_path = os.path.join("persistence", "topics")

# Работа с файлами планов пользователей
def save_plan(chat_id, plan):
    with DatabaseContext() as ctx:
        user = ctx.get_or_create_user(chat_id)
        user.plan = plan
        user.save()

def load_plan(chat_id):
    with DatabaseContext() as ctx:
        user = ctx.get_or_create_user(chat_id)
        return user.plan

def load_topics(filename):
    topics = []
    try:
        with open (filename, "r", encoding="utf-8") as file:
            for line in file :
                topics.append(line.strip())
        return topics 
    except FileNotFoundError:
        return "файл не найден"
    
def get_exam_date(message):
    try:
        examdate = datetime.strptime(message.text, "%d.%m.%Y")
        today = datetime.now()
        day_left = (examdate - today).days
        if day_left < 0 :
            bot.send_message(message.chat.id, "Эта дата уже прошла. Введите дату в будущем")
            bot.register_next_step_handler(message, get_exam_date)
            return
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(message.chat.id)            
            user.exam_date = examdate
            user.day_left = day_left
            user.save()
        bot.send_message(message.chat.id, f"До экзамена осталось {day_left} дней.")

    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат даты. Введите в формате ДД.ММ.ГГГГ ")
        bot.register_next_step_handler(message, get_exam_date)

def generate_plan(topics, day_left):
    plan = []
    topics_count = len(topics)
    topics_per_day = topics_count//day_left
    dop_topics = topics_count%day_left
    index = 0 
    for day in range(1, day_left + 1):
        day_topics = []
        count = topics_per_day
        if dop_topics > 0:
            count += 1
            dop_topics -= 1
        for i in range(count):
            if index< topics_count:
                day_topics.append(topics[index])
                index +=1 
        if day_topics :
            day_plan = f"День {day}:/n" +"/n".join(day_topics)
            plan.append(day_plan)

    return "/n".join(plan)


@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.InlineKeyboardMarkup()
    but1 = types.InlineKeyboardButton("Создать новый план подготовки", callback_data="new_plan")
    but2 = types.InlineKeyboardButton("Продолжить подготовку", callback_data="continue_plan")
    markup.add(but1)
    markup.add(but2)
    bot.send_message(message.chat.id, "Привет! 👋\n\nЯ помогу тебе подготовиться к экзамену.\n\nВыбери действие:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "new_plan":
        markup = types.InlineKeyboardMarkup()
        but_math = types.InlineKeyboardButton("Математика", callback_data="sub_math")
        but_physics = types.InlineKeyboardButton("Физика", callback_data="sub_physics")
        but_informatics = types.InlineKeyboardButton("Информатика", callback_data="sub_informatics")
        markup.add(but_math)
        markup.add(but_physics)
        markup.add(but_informatics)
        bot.edit_message_text("Отлично! Давай создадим новый план 📚\nВыбери дисциплину:", chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup=markup)
    
    elif call.data == "continue_plan":
        bot.edit_message_text("Продолжаем подготовку", chat_id = call.message.chat.id, message_id = call.message.message_id)
        plan = load_plan(call.message.chat.id)
        bot.send_message(call.message.chat.id, f"План подготовки: \n\n {plan}")
        
    elif call.data == "sub_math":
        topics = load_topics(os.path.join(topics_base_path, "math.txt"))
        bot.edit_message_text(f"Вы выбрали дисциплину 📚Математика📚\nСписок тем: \n\n{topics}", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)
        save_plan(str(call.message.chat.id), "какой-то план")
        # plan = generate_plan(topics, user_data.day_left)
        # bot.send_message(call.message.chat.id, f"План подготовки: \n\n {plan}")
        # save_plan(str(call.message.chat.id), plan)

    elif call.data == "sub_physics":
        topics = load_topics(os.path.join(topics_base_path, "physics.txt"))
        bot.edit_message_text(f"Вы выбрали дисциплину 📚Физика📚\nСписок тем: \n\n{topics}", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)
        # plan = generate_plan(topics, user_data.day_left)
        # bot.send_message(call.message.chat.id, f"План подготовки: \n\n {plan}")
        # save_plan(str(call.message.chat.id), plan)

    elif call.data == "sub_informatics":
        topics = load_topics(os.path.join(topics_base_path, "informatics.txt"))
        bot.edit_message_text(f"Вы выбрали дисциплину 📚Информатика📚\nСписок тем: \n\n{topics}", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)
        # plan = generate_plan(topics, user_data.day_left)
        # bot.send_message(call.message.chat.id, f"План подготовки: \n\n {plan}")
        # save_plan(str(call.message.chat.id), plan)

    bot.answer_callback_query(call.id)

    

if __name__ == "__main__":
    print("="*50)
    print("Бот успешно запущен и готов к работе!")
    print("="*50)
    
    bot.polling(none_stop=True)
