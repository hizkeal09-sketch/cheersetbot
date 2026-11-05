"""Start, help, privacy, and global navigation."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Settings
from app.database.models import User
from app.keyboards.common import main_menu, onboarding_keyboard, remove_reply_keyboard
from app.states.forms import ChatStates, DeleteAccount
from app.utils.render import safe_edit

router = Router(name="common")

WELCOME_TEXT = (
    "🍻 <b>Welcome to Cheers Dating!</b>\n\n"
    "Meet interesting people across Ethiopia — safely, privately and on your terms.\n\n"
    "Here is what makes Cheers different:\n"
    "• 🔒 Your Telegram username and ID stay private\n"
    "• 💌 You only chat after a mutual match\n"
    "• 🛡 Report or block anyone at any time\n"
    "• 🍻 A friendly, adults-only (18+) community\n\n"
    "<b>Are you 18 or older?</b>"
)

HELP_TEXT = (
    "🍻 <b>Cheers Dating — Help & Safety</b>\n\n"
    "<b>Main commands</b>\n"
    "/start — Welcome & main menu\n"
    "/discover — Meet new people\n"
    "/likes — See who liked you\n"
    "/matches — Your matches & chats\n"
    "/profile — View your profile\n"
    "/editprofile — Edit your profile\n"
    "/settings — Filters, pause & privacy\n"
    "/premium — Premium features\n"
    "/pause — Hide your profile temporarily\n"
    "/report — Report someone\n"
    "/block — Block someone\n"
    "/deleteaccount — Delete your account\n"
    "/help — This help page\n\n"
    "<b>Safety tips</b>\n"
    "• Never send money to someone you met online.\n"
    "• Keep conversations inside Cheers until you trust someone.\n"
    "• Video call before meeting in person, and meet in a public place.\n"
    "• Tell a friend where you are going.\n\n"
    "Phone numbers, usernames, emails and links are blocked in chat by default.\n"
    "If someone makes you uncomfortable, use 🚩 Report or 🚫 Block."
)

PRIVACY_TEXT = (
    "🔒 <b>Privacy at Cheers Dating</b>\n\n"
    "• Your Telegram username and numeric ID are never shown to other members.\n"
    "• People see only the profile you create: first name, age, city, bio, interests and photos.\n"
    "• Chats are private between matched members. Messages are stored so we can investigate reports.\n"
    "• You can edit your profile, pause discovery, clear matches, or delete your account at any time.\n"
    "• We never sell personal data.\n\n"
    "Your date of birth is used only to confirm you are 18+ and to power age filters.\n"
    "Use /deleteaccount to permanently erase your profile and data."
)


async def _clear_chat_state(state: FSMContext) -> None:
    current = await state.get_state()
    if current in (ChatStates.active.state, DeleteAccount.confirm.state):
        await state.clear()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User, settings: Settings) -> None:
    await state.clear()
    if user.is_registered:
        await message.answer(
            f"👋 Welcome back, <b>{user.first_name}</b>!\n\nWhat would you like to do?",
            reply_markup=main_menu(message.from_user.id in settings.admin_id_list),
        )
        return
    await message.answer(WELCOME_TEXT, reply_markup=onboarding_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await _clear_chat_state(state)
    await message.answer(HELP_TEXT, reply_markup=home_only_keyboard())


def home_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Main menu", callback_data="menu:home")]]
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(PRIVACY_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "✖️ Cancelled. You can pick up where you left off whenever you're ready.",
        reply_markup=remove_reply_keyboard(),
    )
    await message.answer("What next?", reply_markup=main_menu())


@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery, state: FSMContext, user: User, settings: Settings) -> None:
    await state.clear()
    if not user.is_registered:
        await safe_edit(callback, WELCOME_TEXT, onboarding_keyboard())
        return
    await safe_edit(
        callback,
        f"🏠 <b>Main menu</b>\n\nHey {user.first_name}! What would you like to do?",
        main_menu(callback.from_user.id in settings.admin_id_list),
    )


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery, state: FSMContext) -> None:
    await _clear_chat_state(state)
    await safe_edit(callback, HELP_TEXT, home_only_keyboard())
