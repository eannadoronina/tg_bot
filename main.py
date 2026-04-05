import telebot
from telebot import types
from datetime import datetime
from datetime import timedelta
import os
import sys
from dotenv import load_dotenv
from db import db, init_db, DatabaseContext
import math

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
        user.date_save_plan = datetime.now().date()
        user.save()

def load_plan(chat_id):
    with DatabaseContext() as ctx:
        user = ctx.get_or_create_user(chat_id)
        return user.plan

# Работа с темами
def load_topics(filename):
    topics = []
    try:
        with open (filename, "r", encoding="utf-8") as file:
            for line in file :
                topics.append(line.strip())
        return topics 
    except FileNotFoundError:
        return []

# Обработка даты 
def get_exam_date(message):
    try:
        examdate = datetime.strptime(message.text, "%d.%m.%Y")
        today = datetime.now()
        day_left = (examdate - today).days
        if day_left <= 0 :
            bot.send_message(message.chat.id, "Эта дата уже прошла или сегодня. Введите дату в будущем 📆")
            bot.register_next_step_handler(message, get_exam_date)
            return
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(message.chat.id)            
            user.exam_date = examdate
            user.day_left = day_left
            subject = user.subject
            user.save()
        # Загружаем темы
        topics_file = os.path.join(topics_base_path, f"{subject}.txt")
        topics = load_topics(topics_file)
        if not topics:
            bot.send_message(message.chat.id, "Не удалось загрузить темы 😢")
            return
        # Генерируем план
        plan = generate_plan(topics, day_left)
        # Отправляем и сохраняем план
        bot.send_message(message.chat.id, f"До экзамена осталось {day_left} дней.\n\n📚 План подготовки:\n\n{plan}")
        save_plan(message.chat.id, plan)
        # Сообщение с кнопками "Начнем подготовку?"
        markup = types.InlineKeyboardMarkup()
        but_yes = types.InlineKeyboardButton("Да ✅", callback_data="start_study")
        but_no = types.InlineKeyboardButton("Нет ❌", callback_data="stop_study")
        markup.add(but_yes, but_no)
        bot.send_message(message.chat.id, "Начнем подготовку?", reply_markup=markup)
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат даты. Введите в формате ДД.ММ.ГГГГ ")
        bot.register_next_step_handler(message, get_exam_date)

# Генерация плана
def generate_plan(topics, day_left):
    if day_left <= 0:
        return "Слишком мало времени для составления плана 😢"
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
            day_plan = f"\nДень {day}🗓:\n" +"\n".join(day_topics)
            plan.append(day_plan)

    return "\n".join(plan)

# Повторение изученных тем
def repeat_topics (c_new, k_new, count_repeat):
    b = 60
    c=1.1
    k=2.2
    t = round(10 ** (((100 * k)/b - k) ** (1/c)) )

# Обработка команды start
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.InlineKeyboardMarkup()
    but1 = types.InlineKeyboardButton("📝 Создать новый план подготовки", callback_data="new_plan")
    but2 = types.InlineKeyboardButton("📚 Продолжить подготовку", callback_data="continue_plan")
    markup.add(but1)
    markup.add(but2)
    bot.send_message(message.chat.id, "Привет! 👋\n\nЯ помогу тебе подготовиться к экзамену.\n\nВыбери действие:", reply_markup=markup)

# Callback - обработчики кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "new_plan":
        markup = types.InlineKeyboardMarkup()
        but_math = types.InlineKeyboardButton("📕 Математика", callback_data="sub_math")
        but_physics = types.InlineKeyboardButton("📗 Физика", callback_data="sub_physics")
        but_informatics = types.InlineKeyboardButton("📘 Информатика", callback_data="sub_informatics")
        but_new_subjects = types.InlineKeyboardButton("📙 Добавить свою дисциплину", callback_data="sub_new")
        markup.add(but_math)
        markup.add(but_physics)
        markup.add(but_informatics)
        markup.add(but_new_subjects)
        bot.edit_message_text("Отлично👍 Давай создадим новый план подготовки 📚\nВыбери дисциплину:", chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup=markup)
    
    elif call.data == "continue_plan":
        plan = load_plan(call.message.chat.id)
        if plan:
            bot.edit_message_text("Продолжаем подготовку 🤓", chat_id = call.message.chat.id, message_id = call.message.message_id)
            bot.send_message(call.message.chat.id, f"📚 Твой план:\n\n{plan}")
            # Сообщение с кнопками "Начнем подготовку?"
            markup = types.InlineKeyboardMarkup()
            but_yes = types.InlineKeyboardButton("Да ✅", callback_data="start_study")
            but_no = types.InlineKeyboardButton("Нет ❌", callback_data="stop_study")
            markup.add(but_yes, but_no)
            bot.send_message(call.message.chat.id, "Начнем подготовку?", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "План пока не создан 😢")
        
        
    elif call.data == "sub_math":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            user.subject = "math"
            user.save()
        topics = load_topics(os.path.join(topics_base_path, "math.txt"))
        bot.edit_message_text(f"Вы выбрали дисциплину 📚Математика📚\nСписок тем: \n\n{topics}", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)

    elif call.data == "sub_physics":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            user.subject = "physics"
            user.save()
        topics = load_topics(os.path.join(topics_base_path, "physics.txt"))
        bot.edit_message_text(f"Вы выбрали дисциплину 📚Физика📚\nСписок тем: \n\n{topics}", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)

    elif call.data == "sub_informatics":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            user.subject = "informatics"
            user.save()
        topics = load_topics(os.path.join(topics_base_path, "informatics.txt"))
        bot.edit_message_text(f"Вы выбрали дисциплину 📚Информатика📚\nСписок тем: \n\n{topics}", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)
     
    elif call.data == "sub_new":
        bot.edit_message_text("Вы хотите добавить новую дисциплину \n\n📝 Введите название дисциплины", chat_id = call.message.chat.id, message_id = call.message.message_id)

    elif call.data == "start_study":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            plan_lines = user.plan.split("\n\n")  # План по дням
            today_index = (datetime.now().date() - user.date_save_plan.date()).days
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
                bot.edit_message_text(f"Сегодня нужно изучить:\n\n{today_topics}", chat_id=call.message.chat.id, message_id=call.message.message_id)
            
                # Спрашиваем про прогресс
                markup = types.InlineKeyboardMarkup()
                but_good = types.InlineKeyboardButton("Материал оказался легким, выучил его хорошо ✅", callback_data="learned_good")
                but_ok = types.InlineKeyboardButton("В целом выучил нормально, но позже надо повторить 🙂", callback_data="learned_ok")
                but_bad = types.InlineKeyboardButton("Очень сложная тема 🤯, плохо запоминается", callback_data="learned_bad")
                markup.add(but_good)
                markup.add(but_ok)
                markup.add(but_bad)
                bot.send_message(call.message.chat.id, "\nКак выучил этот материал? Сложно ли далось изучение?", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "Все темы уже изучены! 🎉\n\nНажми 👉 /start")

    elif call.data == "stop_study":
        bot.edit_message_text("Хорошо, возвращайся, когда будешь готов 😌\n\nНажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)
    
    elif call.data == "learned_good":
        c = 0.98
        k = 1.25
        count_repeat = 4
        repeat_topics(c, k, count_repeat)
        bot.edit_message_text("Ты молодец! Но помни, повторение - фундамент усвоения знаний 😌. \nДо скорых встреч в новом дне!\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif call.data == "learned_ok":
        c = 0.98
        k = 1.25
        count_repeat = 4
        repeat_topics(c, k, count_repeat)
        bot.edit_message_text("Не переживай, мы обязательно вернемся к повторению этого материала 😌. \nДо скорых встреч в новом дне!\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif call.data == "learned_bad":
        c = 0.98
        k = 1.25
        count_repeat = 4
        repeat_topics(c, k, count_repeat)
        bot.edit_message_text("Не расстраивайся, частое повторение - залог успеха 😌! \nДо скорых встреч в новом дне!\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)   
    
    bot.answer_callback_query(call.id)

# Запуск
if __name__ == "__main__":
    print("="*50)
    print("Бот успешно запущен и готов к работе!")
    print("="*50)
    
    bot.polling(none_stop=True)
