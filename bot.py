# bot.py — обновлённая версия с /cancel
import os
import json
import telebot
from telebot import types

BOT_TOKEN = "8577173864:AAFiASRL3RJRiXIrYIgnEdusbYjRuR9yzlc"
ADMIN_IDS = [6671272735]
DATA_FILE = "questions.json"

CATEGORIES = {
    "cat1": "Категория 1",
    "cat2": "Категория 2",
    "cat3": "Категория 3",
    "cat4": "Категория 4",
    "cat5": "Категория 5",
    "other": "Прочее",
}

def load_questions():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_questions(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

questions = load_questions()
user_states = {}  # {user_id: {"state": "...", "data": {...}}}

bot = telebot.TeleBot(BOT_TOKEN)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    for key, name in CATEGORIES.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"cat_{key}"))
    return markup

def get_admin_keyboard():
    counts = {k: 0 for k in CATEGORIES}
    for q in questions:
        if q.get("status") == "new":
            cat = q.get("category", "")
            counts[cat] = counts.get(cat, 0) + 1
    markup = types.InlineKeyboardMarkup()
    for k in CATEGORIES:
        if counts[k] > 0:
            name = CATEGORIES[k]
            markup.add(types.InlineKeyboardButton(f"{name} ({counts[k]})", callback_data=f"adm_cat_{k}"))
    if not markup.keyboard:
        markup.add(types.InlineKeyboardButton("Нет новых вопросов ✅", callback_data="noop"))
    markup.add(types.InlineKeyboardButton("← Назад", callback_data="back_main"))
    return markup

def get_question_list_keyboard(category):
    markup = types.InlineKeyboardMarkup()
    for q in questions:
        if q.get("category") == category and q.get("status") == "new":
            short = q["text"][:30].replace("\n", " ")
            markup.add(types.InlineKeyboardButton(f"#{q['id']} — {short}...", callback_data=f"ans_{q['id']}"))
    markup.add(types.InlineKeyboardButton("← Назад", callback_data="back_admin"))
    return markup

# === /cancel — ОТМЕНА ЛЮБОГО ДЕЙСТВИЯ ===
@bot.message_handler(commands=['cancel'])
def cancel_action(message):
    user_id = message.from_user.id
    # Очищаем состояние пользователя
    if user_id in user_states:
        del user_states[user_id]
    bot.send_message(
        message.chat.id,
        "❌ Действие отменено.\n\nВыберите категорию вопроса:",
        reply_markup=get_main_keyboard()
    )

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "🔧 Техническая поддержка предприятия\n\nВыберите категорию вопроса:",
        reply_markup=get_main_keyboard()
    )

# === Выбор категории ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def category_chosen(call):
    category = call.data.split("_", 1)[1]
    user_states[call.from_user.id] = {"state": "choosing_category", "category": category}
    if category == "other":
        bot.edit_message_text(
            "Укажите тему вопроса (например: «Сервер недоступен»).\n\n⚠️ Отменить: /cancel",
            call.message.chat.id, call.message.id
        )
        user_states[call.from_user.id]["state"] = "entering_topic"
    else:
        bot.edit_message_text(
            "Опишите проблему.\n\n⚠️ Отменить: /cancel",
            call.message.chat.id, call.message.id
        )
        user_states[call.from_user.id]["state"] = "entering_text"

# === Ввод темы (для 'Прочее') ===
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("state") == "entering_topic")
def topic_entered(message):
    if message.text == "/cancel":
        return  # уже обработано в handlers выше
    user_states[message.from_user.id]["custom_topic"] = message.text[:50]
    user_states[message.from_user.id]["state"] = "entering_text"
    bot.send_message(message.chat.id, "Теперь опишите вопрос.\n\n⚠️ Отменить: /cancel")

# === Ввод вопроса ===
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("state") == "entering_text")
def question_entered(message):
    if message.text == "/cancel":
        return  # уже обработано
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    category = state.get("category")
    text = message.text.strip()
    if not text:
        bot.send_message(message.chat.id, "❌ Пустой вопрос. Попробуйте ещё раз.\n\n⚠️ Отменить: /cancel")
        return

    q_id = max([q.get("id", 0) for q in questions], default=0) + 1
    question = {
        "id": q_id,
        "user_id": user_id,
        "username": message.from_user.username or f"id{user_id}",
        "category": category,
        "custom_topic": state.get("custom_topic"),
        "text": text,
        "status": "new"
    }
    questions.append(question)
    save_questions(questions)
    user_states.pop(user_id, None)

    cat_name = CATEGORIES.get(category, category)
    if category == "other" and state.get("custom_topic"):
        cat_name += f" → {state['custom_topic']}"
    bot.send_message(message.chat.id, f"✅ Вопрос #{q_id} принят.\nКатегория: {cat_name}\nОжидайте ответа.")

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🆕 Новый вопрос #{q_id}\nКатегория: {cat_name}\nОт: @{question['username']}\n\n{text[:100]}{'…' if len(text) > 100 else ''}"
            )
        except:
            pass

# === Админка ===
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Доступ запрещён.")
        return
    bot.send_message(message.chat.id, "🛠 Панель модератора", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "back_admin")
def back_to_admin(call):
    if is_admin(call.from_user.id):
        bot.edit_message_text("🛠 Панель модератора", call.message.chat.id, call.message.id, reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_cat_"))
def admin_category(call):
    if not is_admin(call.from_user.id):
        return
    category = call.data.split("_", 2)[2]
    bot.edit_message_text(
        f"Вопросы в: {CATEGORIES[category]}\n\n⚠️ Отменить: /cancel",
        call.message.chat.id, call.message.id,
        reply_markup=get_question_list_keyboard(category)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("ans_"))
def answer_question(call):
    if not is_admin(call.from_user.id):
        return
    try:
        q_id = int(call.data.split("_", 1)[1])
        question = next((q for q in questions if q.get("id") == q_id), None)
    except:
        question = None
    if not question:
        bot.answer_callback_query(call.id, "❌ Вопрос не найден", show_alert=True)
        return

    user_states[call.from_user.id] = {"state": "answering", "q_id": q_id}
    cat_disp = CATEGORIES[question["category"]]
    if question["category"] == "other" and question.get("custom_topic"):
        cat_disp += f" → {question['custom_topic']}"
    text = f"❓ Вопрос #{q_id}\nКатегория: {cat_disp}\nОт: @{question['username']}\n\n{question['text']}\n\n✍️ Напишите ответ.\n\n⚠️ Отменить: /cancel"
    bot.edit_message_text(text, call.message.chat.id, call.message.id)

# === Ввод ответа админом ===
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("state") == "answering")
def send_answer(message):
    if message.text == "/cancel":
        return  # уже обработано
    if not is_admin(message.from_user.id):
        return
    state = user_states.get(message.from_user.id)
    q_id = state.get("q_id")
    question = next((q for q in questions if q.get("id") == q_id), None)
    if not question:
        bot.send_message(message.chat.id, "❌ Вопрос не найден.")
        return

    question["answer"] = message.text
    question["status"] = "answered"
    save_questions(questions)
    user_states.pop(message.from_user.id, None)

    try:
        bot.send_message(question["user_id"], f"✅ Ответ на вопрос #{q_id}:\n\n{message.text}")
    except:
        bot.send_message(message.chat.id, "⚠️ Пользователь не получил ответ.")

    bot.send_message(message.chat.id, "✅ Ответ отправлен.")

@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def back_main(call):
    bot.edit_message_text(
        "Выберите категорию вопроса:",
        call.message.chat.id, call.message.id,
        reply_markup=get_main_keyboard()
    )

# === Запуск ===
if __name__ == "__main__":
    print("=" * 50)
    print("✅ Бот запущен! Добавлена команда /cancel")
    print("📝 Примеры:")
    print("   • Вводите вопрос → передумали? Напишите /cancel")
    print("   • Пишете ответ → решили отменить? /cancel")
    print("=" * 50)
    bot.infinity_polling()