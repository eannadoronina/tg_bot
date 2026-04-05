import os
from peewee import SqliteDatabase, Model, IntegerField, DateTimeField, AutoField, TextField

db_path = os.path.join("persistence", 'users.db')
db = SqliteDatabase(db_path)

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    id = AutoField()
    chat_id = IntegerField()
    subject = TextField(null=True)
    exam_date = DateTimeField(null=True)
    day_left = IntegerField(null=True)
    date_save_plan = DateTimeField(null=True)
    plan = TextField(null=True)

# Контекстный менеджер для работы с БД
class DatabaseContext:
    def __enter__(self):
        db.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not db.is_closed():
            db.close()

    def get_or_create_user(self, chat_id):
        """Получить пользователя или создать нового"""
        try:
            user = User.get(User.chat_id == chat_id)
            return user
        except User.DoesNotExist:
            user = User.create(chat_id=chat_id)
            return user

# Инициализация таблиц
def init_db():
    with DatabaseContext():
        db.create_tables([User], safe=True)