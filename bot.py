import asyncio
import json
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

OWNER_ID = 676415698
CHANNEL_ID = -1003981237494  # ВСТАВ СВІЙ ID КАНАЛУ

DATA_FILE = "data.json"
TIMEZONE = "Europe/Bratislava"

scheduler = AsyncIOScheduler(timezone=TIMEZONE)


def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "vehicles": [],
            "users": [],
            "dashboard_message_id": None,
            "last_action": None
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        old_data = json.load(f)

    if isinstance(old_data, list):
        data = {
            "vehicles": old_data,
            "users": [],
            "dashboard_message_id": None,
            "last_action": None
        }
        save_data(data)
        return data

    if "vehicles" not in old_data:
        old_data["vehicles"] = []
    if "users" not in old_data:
        old_data["users"] = []
    if "dashboard_message_id" not in old_data:
        old_data["dashboard_message_id"] = None
    if "last_action" not in old_data:
        old_data["last_action"] = None

    return old_data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_number(text):
    return text.strip().upper()


def register_user(user_id):
    data = load_data()

    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)


def get_keyboard():
    data = load_data()
    builder = InlineKeyboardBuilder()

    for v in data["vehicles"]:
        if v["checked"]:
            text = f"✅ {v['number']} — {v['checked_by']} {v['time']}"
        else:
            text = f"⬜ {v['number']}"

        builder.button(text=text, callback_data=f"toggle:{v['number']}")

    builder.button(text="↩️ Відмінити останню дію", callback_data="undo:last")
    builder.adjust(1)
    return builder.as_markup()


def dashboard_text():
    data = load_data()
    vehicles = data["vehicles"]

    total = len(vehicles)
    checked = sum(1 for v in vehicles if v["checked"])
    updated = datetime.now().strftime("%H:%M")

    text = "🚛 OVERSIZE FLEET STATUS\n"
    text += "🟢 LIVE\n\n"
    text += f"Оновлено: {updated}\n"
    text += f"Прогрес: {checked}/{total}\n\n"

    if not vehicles:
        text += "Список машин порожній"
        return text

    for i, v in enumerate(vehicles, start=1):
        if v["checked"]:
            text += f"{i}. 🟢 {v['number']}\n"
            text += f"   👤 {v['checked_by']} • 🕐 {v['time']}\n\n"
        else:
            text += f"{i}. ⚪ {v['number']}\n"
            text += "   — ще не звʼязались —\n\n"

    return text


async def update_dashboard():
    data = load_data()
    msg_id = data.get("dashboard_message_id")

    if not msg_id:
        return

    try:
        await bot.edit_message_text(
            chat_id=CHANNEL_ID,
            message_id=msg_id,
            text=dashboard_text()
        )
    except Exception:
        pass


@dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(f"Твій Telegram ID:\n{message.from_user.id}")


@dp.message(Command("start"))
async def start_handler(message: Message):
    register_user(message.from_user.id)

    await message.answer(
        "🚛 Oversize Bot запущений\n\n"
        "/checklist — чекліст\n"
        "/dashboard — створити dashboard в каналі\n"
        "/add AA 342 CE — додати машину\n"
        "/bulkadd — додати список машин\n"
        "/remove AA 342 CE — видалити машину\n"
        "/move AA 342 CE 1 — перемістити машину\n"
        "/reset — скинути галочки\n"
        "/myid — показати Telegram ID"
    )


@dp.message(Command("checklist"))
async def checklist_handler(message: Message):
    register_user(message.from_user.id)
    await message.answer("📋 Checklist:", reply_markup=get_keyboard())


@dp.message(Command("dashboard"))
async def dashboard_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Тільки owner може створити dashboard в каналі")
        return

    data = load_data()

    msg = await bot.send_message(
        chat_id=CHANNEL_ID,
        text=dashboard_text()
    )

    data["dashboard_message_id"] = msg.message_id
    save_data(data)

    await message.answer("✅ Dashboard створено в каналі")


@dp.message(Command("add"))
async def add_handler(message: Message):
    number = clean_number(message.text.replace("/add", ""))

    if not number:
        await message.answer("❌ Приклад:\n/add AA 342 CE")
        return

    data = load_data()

    if any(v["number"] == number for v in data["vehicles"]):
        await message.answer(f"⚠️ Вже є: {number}")
        return

    data["vehicles"].append({
        "number": number,
        "checked": False,
        "checked_by": None,
        "time": None
    })

    save_data(data)
    await update_dashboard()

    await message.answer(f"✅ Додано: {number}")


@dp.message(Command("bulkadd"))
async def bulkadd_handler(message: Message):
    lines = message.text.split("\n")[1:]

    if not lines:
        await message.answer(
            "❌ Приклад:\n\n"
            "/bulkadd\n"
            "AA 342 CE\n"
            "AO 7819 BM"
        )
        return

    data = load_data()
    added = []
    skipped = []

    for line in lines:
        number = clean_number(line)

        if not number:
            continue

        if any(v["number"] == number for v in data["vehicles"]):
            skipped.append(number)
            continue

        data["vehicles"].append({
            "number": number,
            "checked": False,
            "checked_by": None,
            "time": None
        })

        added.append(number)

    save_data(data)
    await update_dashboard()

    text = f"✅ Додано машин: {len(added)}"

    if added:
        text += "\n\n" + "\n".join(added)

    if skipped:
        text += f"\n\n⚠️ Пропущено дублікати: {len(skipped)}"

    await message.answer(text)


@dp.message(Command("remove"))
async def remove_handler(message: Message):
    number = clean_number(message.text.replace("/remove", ""))

    if not number:
        await message.answer("❌ Приклад:\n/remove AA 342 CE")
        return

    data = load_data()
    old_count = len(data["vehicles"])

    data["vehicles"] = [
        v for v in data["vehicles"]
        if v["number"] != number
    ]

    if len(data["vehicles"]) == old_count:
        await message.answer(f"⚠️ Не знайдено: {number}")
        return

    save_data(data)
    await update_dashboard()

    await message.answer(f"🗑 Видалено: {number}")


@dp.message(Command("move"))
async def move_handler(message: Message):
    parts = message.text.replace("/move", "").strip().split()

    if len(parts) < 2:
        await message.answer("❌ Приклад:\n/move AA 342 CE 1")
        return

    position_text = parts[-1]
    number = " ".join(parts[:-1]).upper()

    try:
        position = int(position_text)
    except ValueError:
        await message.answer("❌ Останнє значення має бути числом")
        return

    data = load_data()
    vehicles = data["vehicles"]

    vehicle = None

    for v in vehicles:
        if v["number"] == number:
            vehicle = v
            break

    if not vehicle:
        await message.answer(f"⚠️ Не знайдено: {number}")
        return

    vehicles.remove(vehicle)

    if position < 1:
        position = 1

    if position > len(vehicles) + 1:
        position = len(vehicles) + 1

    vehicles.insert(position - 1, vehicle)

    save_data(data)
    await update_dashboard()

    await message.answer(f"✅ {number} переміщено на позицію {position}")


async def reset_all():
    data = load_data()

    for v in data["vehicles"]:
        v["checked"] = False
        v["checked_by"] = None
        v["time"] = None

    data["last_action"] = None

    save_data(data)
    await update_dashboard()


@dp.message(Command("reset"))
async def reset_handler(message: Message):
    await reset_all()
    await message.answer("🔄 Всі галочки скинуто")


async def undo_last_action(callback: types.CallbackQuery):
    data = load_data()
    last_action = data.get("last_action")

    if not last_action:
        await callback.answer("Немає дії для відміни", show_alert=True)
        return

    number = last_action["number"]
    previous_state = last_action["previous_state"]

    for v in data["vehicles"]:
        if v["number"] == number:
            v["checked"] = previous_state["checked"]
            v["checked_by"] = previous_state["checked_by"]
            v["time"] = previous_state["time"]
            break

    data["last_action"] = None
    save_data(data)

    await callback.message.edit_reply_markup(reply_markup=get_keyboard())
    await update_dashboard()
    await callback.answer("Останню дію відмінено")


@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    if callback.data == "undo:last":
        await undo_last_action(callback)
        return

    if not callback.data.startswith("toggle:"):
        return

    number = callback.data.replace("toggle:", "")
    user = callback.from_user.first_name
    now = datetime.now().strftime("%H:%M")

    data = load_data()

    for v in data["vehicles"]:
        if v["number"] == number:
            data["last_action"] = {
                "number": number,
                "previous_state": {
                    "checked": v["checked"],
                    "checked_by": v["checked_by"],
                    "time": v["time"]
                }
            }

            if not v["checked"]:
                v["checked"] = True
                v["checked_by"] = user
                v["time"] = now
            else:
                v["checked"] = False
                v["checked_by"] = None
                v["time"] = None

            break

    save_data(data)

    await callback.message.edit_reply_markup(reply_markup=get_keyboard())
    await update_dashboard()
    await callback.answer()


async def send_reminder():
    data = load_data()

    for user_id in data["users"]:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="⏰ Час оновити статус по машинах",
                reply_markup=get_keyboard()
            )
        except Exception:
            pass


async def main():
    scheduler.add_job(reset_all, "cron", hour=0, minute=0)
    scheduler.add_job(send_reminder, "cron", hour=10, minute=0)
    scheduler.add_job(send_reminder, "cron", hour=16, minute=0)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())