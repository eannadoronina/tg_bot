import telebot
from telebot import types
from datetime import datetime
from datetime import timedelta
import os
import time
from dotenv import load_dotenv
from db import init_db, DatabaseContext
import threading

# Загрузка токена для бота из переменной окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализируем БД
init_db()

bot = telebot.TeleBot(BOT_TOKEN)

# ------------------------Работа с отправкой уведомлений------------------------
  
# Функция исполнения запланированных оповещений
def scheduler():
    while True:
        try:
            with DatabaseContext() as ctx: 
                users = ctx.get_all_users()
                for user in users:
                    plan_lines = user.plan.split("\n\n")  # План по дням
                    today_index = (datetime.now().date() - user.date_save_plan.date()).days
                    if user.next_topic_notify_time and datetime.now() >= user.next_topic_notify_time and today_index < len(plan_lines):
                        start_study(user.chat_id, None, True)
                        user.next_topic_notify_time = datetime.now() + timedelta(days=1)
                        user.save()
                task_all = ctx.get_all_scheduled_task()
                for task in task_all:
                    if datetime.now() >= task.run_time:
                        send_repeat_notification(task.chat_id, task.topic_name, task.c, task.k, task.flag)
                        ctx.delete_scheduled_task(task.id)             
        except Exception:
            pass
        time.sleep(2)

# Отправка уведомления
def send_repeat_notification(chat_id, topic_name, c, k, flag):
    with DatabaseContext() as ctx: 
        task = ctx.get_scheduled_task_by_chat_id(chat_id)
        today_index = task.index_day
    markup = types.InlineKeyboardMarkup()
    but_1 = types.InlineKeyboardButton("Легко ✅", callback_data=f"easy|{c}|{k}|{today_index}|{flag}")
    but_2 = types.InlineKeyboardButton("Нормально 🙂", callback_data=f"ok|{c}|{k}|{today_index}|{flag}")
    but_3 = types.InlineKeyboardButton("Сложно 🤯", callback_data=f"hard|{c}|{k}|{today_index}|{flag}")
    markup.add(but_1, but_2, but_3)
    bot.send_message(chat_id, f"⏰ Пора повторить материал: \n\n <blockquote>{topic_name}</blockquote>\n\n Как тебе далось изучение этих материалов?", reply_markup=markup, parse_mode="HTML")

# ------------------------Работа с файлами------------------------
def save_plan(chat_id, plan):
    with DatabaseContext() as ctx:
        user = ctx.get_or_create_user(chat_id)
        user.plan = plan
        user.date_save_plan = datetime.now()
        user.number_current_topic = 0
        user.last_activity_date = datetime.now()
        user.next_topic_notify_time = user.date_save_plan + timedelta(days=1)
        user.save()

def load_plan(chat_id):
    with DatabaseContext() as ctx:
        user = ctx.get_or_create_user(chat_id)
        return user.plan

# ------------------------Работа с новой дисциплиной------------------------
# Добавление новой дисциплины
def save_new_subject_name(message):
    with DatabaseContext() as ctx:
        subject = ctx.create_subject(message.text, "")
        user = ctx.get_or_create_user(message.chat.id)
        user.subject_id = subject.id
        user.save()
    bot.send_message(message.chat.id, "Введите темы через перенос строки 📖\n\nПример:\nТема 1\nТема 2\nТема 3")
    bot.register_next_step_handler(message, save_new_subject_topics, subject.id)

# Добавление тем для новой дисциплины
def save_new_subject_topics(message, subject_id):
    with DatabaseContext() as ctx:
        subject = ctx.get_subject_by_id(subject_id)
        if not subject:
            bot.send_message(message.chat.id, "Ошибка 😢")
            return
        subject.topics = message.text
        subject.save()
    bot.send_message(message.chat.id, "Дисциплина добавлена ✅")
    bot.send_message(message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
    bot.register_next_step_handler(message, get_exam_date)

# ------------------------Работа с планами------------------------
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
            subject = ctx.get_subject_by_id(user.subject_id)
            if not subject:
                bot.send_message(message.chat.id, "Предмет не найден 😢")
                return
            user.save()
        # Загружаем темы
        topics = subject.topics.split("\n")
        if not topics:
            bot.send_message(message.chat.id, "Не удалось загрузить темы 😢")
            return
        # Генерируем план
        plan = generate_plan(topics, day_left, message.chat.id)
        formatted_plan = format_plan_for_display(plan)
        # Отправляем и сохраняем план
        bot.send_message(message.chat.id, f"До экзамена осталось {day_left} дней.")
        bot.send_message(message.chat.id, f"<blockquote>\n📚 <b>План подготовки:</b>\n\n{formatted_plan}</blockquote>", parse_mode="HTML")
        save_plan(message.chat.id, plan)
        start_study(message.chat.id, None, False)# Сообщение с кнопками "Начнем подготовку?"
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат даты. Введите в формате ДД.ММ.ГГГГ ")
        bot.register_next_step_handler(message, get_exam_date)

# Генерация плана
def generate_plan(topics, day_left, chat_id):
    if day_left <= 0:
        bot.send_message(chat_id, "Слишком мало времени для составления плана 😢\n\nНажми 👉 /start")
        return None
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
        if day_topics:
            plan.append("\n".join(day_topics))

    return "\n\n".join(plan)

# Пересчет плана
def regenerate_plan(user):
    plan_days = user.plan.split("\n")  # все темы
    all_topics = []
    for topic in plan_days:
        all_topics.extend(topic.split("\n"))
    remaining_topics = plan_days[user.number_current_topic:] # оставшиеся темы
    if not remaining_topics:
        return None
    days_left = (user.exam_date.date() - datetime.now().date()).days # дни до экзамена
    if days_left <= 0:
        bot.send_message(user.chat_id, "Слишком мало времени для составления плана 😢\n\nНажми 👉 /start")
    new_plan = generate_plan(remaining_topics, days_left, user.chat_id)
    return new_plan

# Повторение изученных тем
def repeat_topics (chat_id, topic_name, index_day, c, k, c_deb, k_deb, flag):
    b = 60
    k = k * k_deb
    c = c * c_deb
    # Вычисляем время до следующего повторения в минутах по модели Эббингауза
    t = round(10 ** (((100 * k)/b - k) ** (1/c)))
    if t < 3500:
        flag = True
    else:
        flag = False
    t_seconds = t * 60
    # Планируем уведомление через t секунд
    run_time = datetime.now() + timedelta(seconds=t_seconds)
    with DatabaseContext() as ctx:
        ctx.create_scheduled_task(chat_id, topic_name, index_day, run_time, c, k, flag)

# Форматирование выводы плана
def format_plan_for_display(plan):
    days = plan.split("\n\n")
    formatted_days = []
    for i, day in enumerate(days, start=1):
        topics = [t.strip() for t in day.split("\n") if t.strip()]        
        if topics:
            day_text = f"День {i} 🗓:\n" + "\n".join(topics)
            formatted_days.append(day_text)
    return "\n\n".join(formatted_days)

def start_study(chat_id, message_id, repeat):
    plan = load_plan(chat_id)
    if plan:
        if message_id:
            formatted_plan = format_plan_for_display(plan)
            bot.edit_message_text("Продолжаем подготовку 🤓", chat_id = chat_id, message_id = message_id)
            bot.send_message(chat_id, f"<blockquote><b>📚 Твой план:</b>\n\n{formatted_plan}</blockquote>", parse_mode="HTML")
        markup = types.InlineKeyboardMarkup()
        but_yes = types.InlineKeyboardButton("Да ✅", callback_data="start_study")
        but_no = types.InlineKeyboardButton("Нет ❌", callback_data="stop_study")
        markup.add(but_yes, but_no)
        if repeat:
            bot.send_message(chat_id, "Новый день - новые знания 🤓\n\nНачнем подготовку?", reply_markup=markup)
        else:
            bot.send_message(chat_id, "Начнем подготовку?", reply_markup=markup)
    else:
        bot.send_message(chat_id, "План пока не создан 😢")



# ------------------------Обработчики команд и кнопок------------------------
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
        start_study(call.message.chat.id, call.message.message_id, False)
        
        
    elif call.data == "sub_math":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            subject = ctx.get_subject_by_name( "math")
            user.subject_id = subject.id
            user.save()
        bot.edit_message_text("Вы выбрали дисциплину 📚Математика📚\n\n", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)

    elif call.data == "sub_physics":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            subject = ctx.get_subject_by_name("physics")
            user.subject_id = subject.id
            user.save()
        bot.edit_message_text("Вы выбрали дисциплину 📚Физика📚\n\n", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)

    elif call.data == "sub_informatics":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            subject = ctx.get_subject_by_name("informatics")
            user.subject_id = subject.id
            user.save()
        bot.edit_message_text("Вы выбрали дисциплину 📚Информатика📚\n\n", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.send_message(call.message.chat.id, "Введите дату экзамена в формате ДД.ММ.ГГГГ")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_exam_date)
     
    elif call.data == "sub_new":
        bot.edit_message_text("Вы хотите добавить новую дисциплину \n\n📝 Введите название дисциплины:", chat_id = call.message.chat.id, message_id = call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, save_new_subject_name)

    elif call.data == "start_study":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            today_index = int((datetime.now().date() - user.date_save_plan.date()).days)
            days_missed = today_index - user.number_current_topic
            if days_missed > 1:
                new_plan = regenerate_plan(user)
                if new_plan:
                    user.plan = new_plan
                    user.number_current_topic = 0  # начинаем с начала нового плана
                    user.date_save_plan = datetime.now()
                    user.save()
                    formatted_plan = format_plan_for_display(new_plan)
                    bot.edit_message_text( 
                        f"Ты пропустил {days_missed} дней 😢\nЯ пересчитал план, чтобы ты всё успел 💪\n\n<blockquote>📚 Новый план:\n{formatted_plan}</blockquote>", 
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id,
                        parse_mode="HTML"
                    )
                start_study(call.message.chat.id, None, False) 
            else:
                plan_lines = user.plan.split("\n\n")  # План по дням
                # Определяем сегодняшние темы
                if user.number_current_topic < len(plan_lines):
                    today_topics = plan_lines[user.number_current_topic]
                    bot.edit_message_text(f"\n\n‼️Сегодня нужно изучить:\n\n<blockquote>{today_topics}</blockquote>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
                    # Спрашиваем про прогресс
                    markup = types.InlineKeyboardMarkup()
                    but_good = types.InlineKeyboardButton("Материал оказался легким✅", callback_data="learned_good")
                    but_ok = types.InlineKeyboardButton("Выучил нормально, позже надо повторить🙂", callback_data="learned_ok")
                    but_bad = types.InlineKeyboardButton("Очень сложная тема🤯, плохо запоминается", callback_data="learned_bad")
                    markup.add(but_good)
                    markup.add(but_ok)
                    markup.add(but_bad)
                    bot.send_message(call.message.chat.id, "\nКак выучил этот материал? Сложно ли далось изучение?", reply_markup=markup)
                else:
                    bot.send_message(call.message.chat.id, "Все темы уже изучены! 🎉\n\nНажми 👉 /start")
                    ctx.delete_user(user.id)

    elif call.data == "stop_study":
        bot.edit_message_text("Хорошо, возвращайся, когда будешь готов 😌\n\nНажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif call.data == "learned_good":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            user.last_activity_date = datetime.now()
            plan_lines = user.plan.split("\n\n")  # План по дням
            today_index = user.number_current_topic
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
            user.number_current_topic+=1
            user.save()
        c = 1.1
        k = 2.2
        c_deb = 1
        k_deb = 1
        
        repeat_topics(call.message.chat.id, today_topics, today_index, c, k, c_deb, k_deb, True)
        bot.edit_message_text("Ты молодец! Но помни, повторение - фундамент усвоения знаний 😌\nКогда нужно будет повторить материал, я тебе сообщу 😉\nДо скорых встреч!\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif call.data == "learned_ok":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            user.last_activity_date = datetime.now()
            plan_lines = user.plan.split("\n\n")  # План по дням
            today_index = user.number_current_topic
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
            user.number_current_topic+=1
            user.save()
        c = 1.1
        k = 2.2
        c_deb = 1
        k_deb = 1
        repeat_topics(call.message.chat.id, today_topics, today_index, c, k, c_deb, k_deb, True)
        bot.edit_message_text("Не переживай, скоро мы обязательно вернемся к повторению этого материала 😌. \nДо скорых встреч!\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif call.data == "learned_bad":
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            user.last_activity_date = datetime.now()
            plan_lines = user.plan.split("\n\n")  # План по дням
            today_index = user.number_current_topic
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
            user.number_current_topic+=1
            user.save()
        c = 1.1
        k = 2.2
        c_deb = 1
        k_deb = 1
        repeat_topics(call.message.chat.id, today_topics, today_index, c, k, c_deb, k_deb, True)
        bot.edit_message_text("Не расстраивайся, частое повторение - залог успеха 😌, а я напомню тебе о повторении, когда это потребуется!\nДо скорых встреч!\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)   
    
    elif call.data.split("|")[0] == "easy":
        data = call.data.split("|")
        c = float(data[1])
        k = float(data[2])
        today_index = int((data[3]))
        flag = data[4] == "True"
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            plan_lines = user.plan.split("\n\n")  # План по дням
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
        c_deb = 0.98
        k_deb = 1.25
        if flag == True:
            repeat_topics(call.message.chat.id, today_topics, today_index, c, k, c_deb, k_deb, True)
        bot.edit_message_text("Отлично! Пока отдохни, но скоро мы продолжим изучение 😌\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id) 
    
    elif call.data.split("|")[0] == "ok":
        data = call.data.split("|")
        c = float(data[1])
        k = float(data[2])
        today_index = int((data[3]))
        flag = data[4] == "True"
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            plan_lines = user.plan.split("\n\n")  # План по дням
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
        c_deb = 1.02
        k_deb = 1.25
        if flag == True:
            repeat_topics(call.message.chat.id, today_topics, today_index, c, k, c_deb, k_deb, True)
        bot.edit_message_text("Ты молодец! Скоро мы продолжим изучение 😌\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)
    
    elif call.data.split("|")[0] == "hard":
        data = call.data.split("|")
        c = float(data[1])
        k = float(data[2])
        today_index = int((data[3]))
        flag = data[4] == "True"
        with DatabaseContext() as ctx:
            user = ctx.get_or_create_user(call.message.chat.id)
            plan_lines = user.plan.split("\n\n")  # План по дням
            # Определяем сегодняшние темы
            if today_index < len(plan_lines):
                today_topics = plan_lines[today_index]
        c_deb = 1.02
        k_deb = 1.15
        if flag == True:
            repeat_topics(call.message.chat.id, today_topics, today_index, c, k, c_deb, k_deb, True)
        bot.edit_message_text("Хорошо! Будем учить усерднее 😌\n\nЕсли хочешь выйти в главное меню, нажми 👉 /start", chat_id=call.message.chat.id, message_id=call.message.message_id)

    bot.answer_callback_query(call.id)

# ------------------------Запуск------------------------
if __name__ == "__main__":
    thread = threading.Thread(target=scheduler)
    thread.start()
    print("="*50)
    print("Бот успешно запущен и готов к работе!")
    print("="*50)
    bot.polling(none_stop=True)
