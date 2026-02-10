import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER
from aiogram.types import ChatMemberUpdated
# Предположим, у вас есть эта функция из документации SubGram
from utils.subgram_api import get_subgram_sponsors

# Ваши токены
BOT_TOKEN = "8088366355:AAEbbEmb3uCT_5hR9kOVL20oe0a6zEM8pcw"
SUBGRAM_API_KEY = "37519606843a1a613141d46b7ae7ab972575d7db465a11325b73b51fde25ec61"

# ⚡ КРИТИЧЕСКИ ВАЖНО: ID вашего основного чата (группы или канала)
# Узнать ID можно, отправив сообщение в чат и посмотрев в логах бота,
# или с помощью бота @userinfobot, @getidsbot
TARGET_CHAT_ID = -1001234567890  # Замените на реальный ID вашего чата!

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER)
)
async def on_user_joined(event: ChatMemberUpdated):
    """Обработчик вступления пользователя в чат."""
    
    # ⚡ ФИЛЬТР: Проверяем, что пользователь зашел именно в ЦЕЛЕВОЙ чат
    if event.chat.id != TARGET_CHAT_ID:
        # Игнорируем вступления в другие чаты
        logging.info(f"Пользователь {event.from_user.id} зашел в другой чат {event.chat.id}, игнорируем")
        return
    
    user = event.new_chat_member.user
    chat = event.chat
    
    logging.info(f"Пользователь {user.id} зашел в целевой чат {chat.id}")
    
    try:
        # Запрос к SubGram API
        response = await get_subgram_sponsors(
            user_id=user.id,
            chat_id=chat.id,  # Важно передавать ID чата
            first_name=user.first_name,
            username=user.username,
            language_code=user.language_code,
            is_premium=user.is_premium,
            # Другие параметры по необходимости
        )
        
        if response:
            status = response.get('status')
            
            if status == 'warning':
                # Показать сообщение с подписками
                sponsors = response.get('additional', {}).get('sponsors', [])
                # Формируем сообщение с кнопками
                message_text = "📢 Для участия в чате необходимо подписаться:\n\n"
                keyboard_buttons = []
                
                for sponsor in sponsors:
                    if sponsor.get('available_now') and sponsor.get('status') == 'unsubscribed':
                        channel_name = sponsor.get('resource_name', 'Канал')
                        button_text = sponsor.get('button_text', 'Подписаться')
                        link = sponsor.get('link')
                        
                        message_text += f"• {channel_name}\n"
                        # Добавляем inline-кнопку с ссылкой
                        keyboard_buttons.append(
                            [types.InlineKeyboardButton(
                                text=button_text, 
                                url=link
                            )]
                        )
                
                # Кнопка "Я подписался" для проверки
                keyboard_buttons.append(
                    [types.InlineKeyboardButton(
                        text="✅ Я подписался", 
                        callback_data="subgram_check"
                    )]
                )
                
                keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                # Отправляем сообщение пользователю
                await bot.send_message(
                    chat_id=chat.id,
                    text=message_text,
                    reply_markup=keyboard,
                    reply_to_message_id=None  # или ID приветственного сообщения
                )
                logging.info(f"Отправили запрос на подписку пользователю {user.id}")
                elif status == 'ok':
                # Пользователь уже подписан или проверка не требуется
                await bot.send_message(
                    chat_id=chat.id,
                    text=f"👋 Добро пожаловать, {user.first_name}! Рады видеть вас в чате!"
                )
            else:
                # Ошибка API - лучше пропустить пользователя, чтобы не блокировать
                logging.error(f"Ошибка SubGram API: {response.get('message')}")
                await bot.send_message(
                    chat_id=chat.id,
                    text=f"Привет, {user.first_name}! Добро пожаловать."
                )
        else:
            # Не удалось получить ответ от API
            logging.error("Не удалось получить ответ от SubGram API")
            await bot.send_message(
                chat_id=chat.id,
                text=f"Привет, {user.first_name}! Технические неполадки, добро пожаловать."
            )
            
    except Exception as e:
        logging.error(f"Ошибка при обработке вступления: {e}")
        # В случае ошибки лучше пропустить пользователя
        await bot.send_message(
            chat_id=chat.id,
            text=f"Привет, {user.first_name}! Возникли технические сложности."
        )

@dp.callback_query(F.data == "subgram_check")
async def check_subscriptions(callback: types.CallbackQuery):
    """Обработка нажатия кнопки 'Я подписался'."""
    
    # ⚡ ФИЛЬТР: Проверяем, что проверка происходит в целевом чате
    if callback.message.chat.id != TARGET_CHAT_ID:
        await callback.answer("Эта кнопка не для этого чата", show_alert=True)
        return
    
    user = callback.from_user
    chat = callback.message.chat
    
    await callback.answer("⏳ Проверяем подписки...")
    
    try:
        # Повторный запрос к SubGram API для проверки
        response = await get_subgram_sponsors(
            user_id=user.id,
            chat_id=chat.id,
            first_name=user.first_name,
            username=user.username,
            language_code=user.language_code,
            is_premium=user.is_premium
        )
        
        if response and response.get('status') != 'warning':
            # Все подписки выполнены
            await callback.message.edit_text(
                f"✅ {user.first_name}, проверка пройдена! Добро пожаловать в чат!"
            )
            # Можно удалить старое сообщение с кнопками через 5 секунд
            # await asyncio.sleep(5)
            # await callback.message.delete()
        else:
            # Не все подписки выполнены
            await callback.answer(
                "❌ Вы подписались не на все каналы. Проверьте и попробуйте снова.",
                show_alert=True
            )
            
    except Exception as e:
        logging.error(f"Ошибка при проверке подписок: {e}")
        await callback.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)

async def main():
    await dp.start_polling(bot)

if name == "main":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())
