import os
from peewee import SqliteDatabase, Model, IntegerField, DateTimeField, AutoField, TextField, FloatField, BooleanField

db_path = os.path.join("persistence", 'users.db')
db = SqliteDatabase(
    db_path,
    pragmas={
        'journal_mode': 'wal',      # обязательно для многопоточности
        'cache_size': -64000,       # 64 МБ кэш
        'synchronous': 1,           # NORMAL
        'foreign_keys': 1,
        'busy_timeout': 5000,       # 5 секунд ждём разблокировки
    })


class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    id = AutoField()
    chat_id = IntegerField()
    subject_id = IntegerField(null=True)
    exam_date = DateTimeField(null=True)
    date_save_plan = DateTimeField(null=True)
    next_topic_notify_time = DateTimeField(null=True)
    plan = TextField(null=True)
    number_current_topic = IntegerField(null=True)
    last_activity_date = DateTimeField(null=True)

class Subject(BaseModel):
    id = AutoField()
    name = TextField(null=True)
    topics = TextField(null=True)

class ScheduledTask(BaseModel):
    id = AutoField()
    chat_id = IntegerField()
    topic_name = TextField()
    index_day = IntegerField()
    run_time = DateTimeField()
    c = FloatField()
    k = FloatField()
    flag = BooleanField()

# Контекстный менеджер для работы с БД
class DatabaseContext:
    def __enter__(self):
        db.connect(reuse_if_open=True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_or_create_user(self, chat_id):
        """Получить пользователя или создать нового"""
        with db.atomic():
            try:
                user = User.get(User.chat_id == chat_id)
                return user
            except User.DoesNotExist:
                user = User.create(chat_id=chat_id)
                return user
    
    def get_all_users(self):
        with db.atomic():
            return User.select()
        
    def delete_user(self, id):
        with db.atomic():
            User.delete_by_id(id)
    
    def create_subject(self, name, topics):
        with db.atomic():
            subject = Subject.create(name=name, topics=topics)
            return subject

    def get_subject_by_id(self, id):
        with db.atomic():
            subject = Subject.get_or_none(Subject.id == id)
            return subject
    
    def get_subject_by_name(self, name):
        with db.atomic():
            subject = Subject.get_or_none(Subject.name == name)
            return subject
    
    def create_scheduled_task(self, chat_id, topic_name, index_day, run_time, c, k, flag):
        with db.atomic():
            return ScheduledTask.create(
                chat_id=chat_id,
                topic_name=topic_name,
                index_day=index_day,
                run_time=run_time,
                c=c,
                k=k,
                flag=flag
            )
        
    def get_all_scheduled_task(self):
        with db.atomic():
            return ScheduledTask.select()
    
    def get_scheduled_task_by_chat_id(self, chat_id):
        with db.atomic():
            task = ScheduledTask.get_or_none(ScheduledTask.chat_id == chat_id)
            return task
        
    def delete_scheduled_task(self, id):
        with db.atomic():
            ScheduledTask.delete_by_id(id)

# Инициализация таблиц
def init_db():
    with DatabaseContext():
        db.execute_sql('PRAGMA journal_mode=wal;')
        db.create_tables([User, Subject, ScheduledTask], safe=True)
        if Subject.select().count() == 0:
            base_subjects = ["math", "physics", "informatics"]
            for sub in base_subjects:
                file_path = os.path.join("persistence", "topics", f"{sub}.txt")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        topics = f.read()
                    Subject.create(name=sub,topics=topics)