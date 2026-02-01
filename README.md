# Django Forum

Форум на Django с разделами, темами и сообщениями.

## Технологии

- Django 6.0
- PostgreSQL
- Bootstrap 5
- Font Awesome

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение: `python3 -m venv myenv`
3. Активируйте: `source myenv/bin/activate`
4. Установите зависимости: `pip install -r requirements.txt`
5. Создайте `.env` из `.env.example`
6. Создайте БД: `createdb forum_dev`
7. Примените миграции: `python manage.py migrate --settings=forum.settings.local`
8. Запустите: `python manage.py runserver --settings=forum.settings.local`

## Лицензия

MIT

