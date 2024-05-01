import asyncio
import datetime
import random
import re
import time

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient


from config import BOT_TOKEN, MONGO_DB_URI
# Initialize MongoDB client
client = MongoClient("MONGO_DB_URI")
db = client["your_database"]
collection = db["your_collection"]
user_collection = db["user_collection"]
group_user_totals_collection = db["group_user_totals_collection"]
top_global_groups_collection = db["top_global_groups_collection"]

# Initialize bot and dispatcher
bot = Bot(token="BOT_TOKEN")
dp = Dispatcher(bot)

locks = {}
last_user = {}
message_counts = {}
sent_characters = {}
last_characters = {}
first_correct_guesses = {}
warned_users = {}
message_counters = {}


def escape_markdown(text):
    escape_chars = r'\*_`\\~>#+-=|{}.!'
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)


async def message_counter(update: types.Update, context: types.CallbackContext) -> None:
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id

    if chat_id not in locks:
        locks[chat_id] = asyncio.Lock()
    lock = locks[chat_id]

    async with lock:
        chat_frequency = await user_totals_collection.find_one({'chat_id': chat_id})
        if chat_frequency:
            message_frequency = chat_frequency.get('message_frequency', 100)
        else:
            message_frequency = 100

        if chat_id in last_user and last_user[chat_id]['user_id'] == user_id:
            last_user[chat_id]['count'] += 1
            if last_user[chat_id]['count'] >= 10:
                if user_id in warned_users and time.time() - warned_users[user_id] < 600:
                    return
                else:
                    await update.message.reply_text(
                        f"🥊 ʏᴏᴜ'ʀᴇ ɴᴏᴡ ʙʟᴏᴄᴋᴇᴅ ғᴏʀ 10 ᴍɪɴᴜᴛᴇs {update.effective_user.first_name} ......"
                        "🧬 ʀᴇᴀsᴏɴ: ғʟᴏᴏᴅɪɴɢ | sᴘᴀᴍᴍɪɴɢ")
                    warned_users[user_id] = time.time()
                    return
        else:
            last_user[chat_id] = {'user_id': user_id, 'count': 1}

        if chat_id in message_counts:
            message_counts[chat_id] += 1
        else:
            message_counts[chat_id] = 1

        if message_counts[chat_id] % message_frequency == 0:
            await send_image(update, context)
            message_counts[chat_id] = 0


async def send_image(update: types.Update, context: types.CallbackContext) -> None:
    chat_id = update.effective_chat.id
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")  # Get current date

    all_characters = list(await collection.find({}).to_list(length=None))

    if chat_id not in sent_characters:
        sent_characters[chat_id] = []

    if len(sent_characters[chat_id]) == len(all_characters):
        sent_characters[chat_id] = []

    rarities = {
        1: '🟢 Cᴏᴍᴍᴏɴ',
        2: '🟣 Rᴀʀᴇ',
        3: '🟡 Lᴇɢᴇɴᴅᴀʀʏ',
        4: '🔮 Lɪᴍɪᴛᴇᴅ',
        5: '💸 𝐏𝐫𝐞𝐦𝐢𝐮𝐦 𝐄𝐝𝐢𝐭𝐢𝐨𝐧'
    }

    spawn_counts = {
        '🟢 Cᴏᴍᴍᴏɴ': 4,
        '🟣 Rᴀʀᴇ': 3,
        '🟡 Lᴇɢᴇɴᴅᴀʀʏ': 4,
        '🔮 Lɪᴍɪᴛᴇᴅ': 2,
        '💸 𝐏𝐫𝐞𝐦𝐢𝐮𝐦 𝐄𝐝𝐢𝐭𝐢𝐨𝐧': 0  # Premium Edition won't spawn
    }

    # Adjust spawn counts for Limited Edition and Special Edition
    if chat_id in message_counters:
        today_message_count = message_counters[chat_id].get(current_time, 0)
    else:
        today_message_count = 0

    # Check if Special Edition characters can spawn based on daily message count
    if today_message_count <= 4:  # Special Edition can spawn up to 4 times in a day
        spawn_counts['🟡 Lᴇɢᴇɴᴅᴀʀʏ'] = 1
    else:
        spawn_counts['🟡 Lᴇɢᴇɴᴅᴀʀʏ'] = 0

    # Check if Limited Edition characters can spawn based on daily message count
    if today_message_count <= 2:  # Limited Edition can spawn up to 2 times in a day
        spawn_counts['🔮 Lɪᴍɪᴛᴇᴅ'] = 1
    else:
        spawn_counts['🔮 Lɪᴍɪᴛᴇᴅ'] = 0

    # Create a list of characters based on spawn counts
    characters_to_spawn = []
    for rarity, count in spawn_counts.items():
        characters_to_spawn.extend(
            [c for c in all_characters if c.get('id') not in sent_characters[chat_id] and c.get('rarity') == rarity] * count)

    if not characters_to_spawn:
        characters_to_spawn = all_characters

    character = random.choice(characters_to_spawn)

    rarity_name = rarities.get(character['rarity'], f'{character["rarity"]}')  # Get rarity name or fallback to the rarity ID

    sent_characters[chat_id].append(character.get('id'))
    last_characters[chat_id] = character

    if chat_id in first_correct_guesses:
        del first_correct_guesses[chat_id]

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=character['img_url'],
        caption=f"""🌟 A {rarity_name} Hᴜsʙᴇɴᴅᴏ Hᴀs Aᴘᴘᴇᴀʀᴇᴅ !Sᴇᴀʟ ʜᴇʀ ɪɴ ʏᴏᴜʀ ʜᴀʀᴇᴍ ʙʏ sᴇɴᴅɪɴɢ /seal [ ɴᴀᴍᴇ ]""",
        parse_mode='Markdown')


async def guess(update: types.Update, context: types.CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in last_characters:
        return

    if chat_id in first_correct_guesses:
        await update.message.reply_text(f'❌️ Already Guessed By Someone... Try Next Time Cʜᴀᴍᴘ! 🌟')
        return

    guess = ' '.join(context.args).lower() if context.args else ''

    if "()" in guess or "&" in guess.lower():
        await update.message.reply_text("Nahh You Can't use This Types of words in your guess..❌️")
        return

    name_parts = last_characters[chat_id]['name'].lower().split()

    if sorted(name_parts) == sorted(guess.split()) or any(part == guess for part in name_parts):
        first_correct_guesses[chat_id] = user_id

        # Add 60 coins to the user's wallet
        await add_coins(int(user_id), 40)

        user = await user_collection.find_one({'id': user_id})
        if user:
            update_fields = {}
            if hasattr(update.effective_user, 'username') and update.effective_user.username != user.get('username'):
                update_fields['username'] = update.effective_user.username
            if update.effective_user.first_name != user.get('first_name'):
                update_fields['first_name'] = update.effective_user.first_name
            if update_fields:
                await user_collection.update_one({'id': user_id}, {'$set': update_fields})

            await user_collection.update_one({'id': user_id}, {'$push': {'characters': last_characters[chat_id]}})

        elif hasattr(update.effective_user, 'username'):
            await user_collection.insert_one({
                'id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'characters': [last_characters[chat_id]],
            })

        group_user_total = await group_user_totals_collection.find_one({'user_id': user_id, 'group_id': chat_id})
        if group_user_total:
            update_fields = {}
            if hasattr(update.effective_user, 'username') and update.effective_user.username != group_user_total.get('username'):
                update_fields['username'] = update.effective_user.username
            if update.effective_user.first_name != group_user_total.get('first_name'):
                update_fields['first_name'] = update.effective_user.first_name
            if update_fields:
                await group_user_totals_collection.update_one({'user_id': user_id, 'group_id': chat_id}, {'$set': update_fields})

            await group_user_totals_collection.update_one({'user_id': user_id, 'group_id': chat_id}, {'$inc': {'count': 1}})

        else:
            await group_user_totals_collection.insert_one({
                'user_id': user_id,
                'group_id': chat_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'count': 1,
            })

        group_info = await top_global_groups_collection.find_one({'group_id': chat_id})
        if group_info:
            update_fields = {}
            if update.effective_chat.title != group_info.get('group_name'):
                update_fields['group_name'] = update.effective_chat.title
            if update_fields:
                await top_global_groups_collection.update_one({'group_id': chat_id}, {'$set': update_fields})

            await top_global_groups_collection.update_one({'group_id': chat_id}, {'$inc': {'count': 1}})

        else:
            await top_global_groups_collection.insert_one({
                'group_id': chat_id,
                'group_name': update.effective_chat.title,
                'count': 1,
            })

        keyboard = [[InlineKeyboardButton(f"See Harem", switch_inline_query_current_chat=f"collection.{user_id}")]]

        await update.message.reply_text("Cᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs! Yᴏᴜ'ᴠᴇ Jᴜsᴛ Eᴀʀɴᴇᴅ Yᴏᴜʀsᴇʟғ 𝟼𝟶 Dᴀᴢᴢʟɪɴɢ Cᴏɪɴs Fᴏʀ Sᴇsᴀʟɪɴɢ Tʜᴇ Cʜᴀʀᴀᴄᴛᴇʀ Sᴘᴏᴛ-ᴏɴ!")
        await update.message.reply_text(f'<b><a href="tg://user?id={user_id}">{escape(update.effective_user.first_name)}</a></b> 🎉 Bʀᴀᴠᴏ! Yᴏᴜ\'ᴠᴇ Sᴇᴀʟᴇᴅ A Nᴇᴡ Cʜᴀʀᴀᴄᴛᴇʀ \u2705️ \n\n🍁NAME🍁: <b>{last_characters[chat_id]["name"]}</b> \n⛩ANIME⛩: <b>{last_characters[chat_id]["anime"]}</b> \n🎐RARITY🎐: <b>{last_characters[chat_id]["rarity"]}</b>\n\nThis Character added in Your harem.. use /harem To see your harem', parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        await update.message.reply_text('Oᴏᴘs! Cʜᴀᴍᴘ Yᴏᴜ Sᴇᴀʟᴇᴅ Tʜᴇ Wʀᴏɴɢ Cʜᴀʀᴀᴄᴛᴇʀ Nᴀᴍᴇ... ❌️')


async def fav(update: types.Update, context: types.CallbackContext) -> None:
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text('Aᴛᴛᴇɴᴛɪᴏɴ! Wᴇ Nᴇᴇᴅ Tʜᴇ Cʜᴀʀᴀᴄᴛᴇʀ ID Tᴏ Pʀᴏᴄᴇᴇᴅ. Cᴏᴜʟᴅ Yᴏᴜ Pʟᴇᴀsᴇ Pʀᴏᴠɪᴅᴇ Iᴛ? 🕵️‍♂️')
        return

    character_id = context.args[0]

    user = await user_collection.find_one({'id': user_id})
    if not user:
        await update.message.reply_text(
            "Lᴏᴏᴋs Lɪᴋᴇ Yᴏᴜ Hᴀᴠᴇɴ'ᴛ Sᴇᴀʟᴇᴅ Aɴʏ Cʜᴀʀᴀᴄᴛᴇʀs Yᴇᴛ! Lᴇᴛ's Dɪᴠᴇ Iɴ Aɴᴅ Sᴛᴀʀᴛ Sᴇᴀʟɪɴɢ Sᴏᴍᴇ Fᴀɴᴛᴀsᴛɪᴄ Cʜᴀʀᴀᴄᴛᴇʀs Tᴏɢᴇᴛʜᴇʀ!🎉 ")
        return

    character = next((c for c in user['characters'] if c['id'] == character_id), None)
    if not character:
        await update.message.reply_text('This Character is Not In your collection')
        return

    user['favorites'] = [character_id]

    await user_collection.update_one({'id': user_id}, {'$set': {'favorites': user['favorites']}})

    await update.message.reply_text(f'Character {character["name"]} has been added to your favorite...')


@dp.errors_handler()
async def error_handler(update: types.Update, context: types.CallbackContext):
    """Log the error and handle it gracefully."""
    LOGGER.error("An error occurred: %s", context.error)


def main() -> None:
    """Run bot."""
    dp.register_message_handler(message_counter, types.ChatType.ALL)
    dp.register_command_handler(guess, commands=["seal", "protecc", "collect", "grab", "hunt"])
    dp.register_command_handler(fav, commands=["fav"])

    # Start the bot
    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    main()
