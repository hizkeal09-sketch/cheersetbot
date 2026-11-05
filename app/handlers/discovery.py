"""Discovery cards, likes, passes, filters, and received likes."""

from __future__ import annotations

import contextlib
import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import InlineKeyboardButton as Btn
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.constants import (
    AGE_PRESETS,
    CITIES,
    GENDER_LABELS_SHORT,
    PREFERENCE_LABELS_SHORT,
    RELIGION_LABELS_SHORT,
    Gender,
    Preference,
)
from app.database.models import Match, User, UserFilter
from app.keyboards.discovery import (
    discovery_card_keyboard,
    filter_cities_keyboard,
    filters_keyboard,
    likes_card_keyboard,
    likes_summary_keyboard,
)
from app.services.discovery import DiscoveryService
from app.services.errors import (
    AccountBannedError,
    CheersError,
    DailyLimitReached,
    ProfilePausedError,
    TargetUnavailableError,
)
from app.services.premium import daily_discovery_limit, has_premium
from app.services.users import UserService
from app.utils.render import (
    answer_callback,
    safe_delete,
    safe_edit,
    send_profile_card,
)

router = Router(name="discovery")


async def _notify_match(
    bot: Bot, user: User, partner: User, match: Match
) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="💬 Say hello", callback_data=f"chat:open:{match.id}")],
            [Btn(text="🍻 Cheers", callback_data="menu:matches")],
        ]
    )
    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(
            partner.telegram_id,
            "💥 <b>It's a match!</b>\n\n"
            f"You and <b>{html.escape(user.first_name)}</b> liked each other. "
            "Send the first message — you both said yes! 🍻",
            reply_markup=keyboard,
        )


async def _run_discovery(
    bot: Bot, chat_id: int, user: User, session: AsyncSession, settings: Settings
) -> None:
    try:
        remaining = await DiscoveryService.remaining_discoveries(session, user, settings)
        target = await DiscoveryService.get_next_candidate(session, user, settings)
    except DailyLimitReached as exc:
        limit = exc.limit
        text = (
            "🌙 <b>That's all for today!</b>\n\n"
            f"You've used all {limit} profile discoveries. Your limit resets at midnight "
            "(Addis Ababa time)."
        )
        rows = []
        if settings.premium_enabled:
            text += "\n\n👑 Premium members get many more discoveries every day."
            rows.append([Btn(text="👑 See Premium", callback_data="menu:premium")])
        rows.append([Btn(text="⚙️ Adjust filters", callback_data="f:menu")])
        rows.append([Btn(text="🏠 Main menu", callback_data="menu:home")])
        await bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        return
    except ProfilePausedError as exc:
        await bot.send_message(
            chat_id,
            f"⏸ {exc.user_message}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="▶️ Resume profile", callback_data="set:resume")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return
    except AccountBannedError as exc:
        await bot.send_message(chat_id, f"🚫 {exc.user_message}")
        return

    if target is None:
        await bot.send_message(
            chat_id,
            "🌿 <b>No more profiles right now.</b>\n\n"
            "You've seen everyone who matches your filters. Try widening your age, "
            "gender or city filters, or check back later as new people join.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="⚙️ Adjust filters", callback_data="f:menu")],
                    [Btn(text="🔄 Try again", callback_data="menu:discover")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return

    limit = daily_discovery_limit(user, settings)
    left = max(remaining - 1, 0)
    footer = f"✨ {left} of {limit} daily discoveries left"
    await send_profile_card(
        bot,
        chat_id,
        target,
        header="💌 <b>Someone new</b>",
        footer=footer,
        reply_markup=discovery_card_keyboard(target.id),
    )
    await DiscoveryService.record_shown(session, user, target, settings)


@router.message(Command("discover"))
async def cmd_discover(
    message: Message, state: FSMContext, user: User, session: AsyncSession, settings: Settings, bot: Bot
) -> None:
    await state.clear()
    await _run_discovery(bot, message.chat.id, user, session, settings)


@router.callback_query(F.data == "menu:discover")
async def cb_discover(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    await state.clear()
    await answer_callback(callback)
    await _run_discovery(bot, callback.from_user.id, user, session, settings)


@router.callback_query(F.data.startswith("like:"))
async def cb_like(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    await state.clear()
    try:
        target_id = int((callback.data or "").split(":")[1])
        target = await UserService.get_by_id(session, target_id)
        result = await DiscoveryService.like(
            session, user, target, settings.app_timezone
        )
    except (ValueError, IndexError):
        await answer_callback(callback, "Invalid profile.", alert=True)
        return
    except CheersError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return

    await safe_delete(callback.message)
    if result.already_liked:
        await answer_callback(callback, "You already liked this person.")
    else:
        await answer_callback(callback, "❤️ Like sent!")

    if result.matched and result.match:
        await _notify_match(bot, user, target, result.match)
        await bot.send_message(
            callback.from_user.id,
            f"💥 <b>It's a match!</b>\n\nYou and <b>{html.escape(target.first_name)}</b> "
            "liked each other. Don't keep them waiting! 🍻",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="💬 Say hello", callback_data=f"chat:open:{result.match.id}")],
                    [Btn(text="🔍 Keep discovering", callback_data="menu:discover")],
                ]
            ),
        )
        return

    await _run_discovery(bot, callback.from_user.id, user, session, settings)


@router.callback_query(F.data.startswith("pass:"))
async def cb_pass(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    await state.clear()
    try:
        target_id = int((callback.data or "").split(":")[1])
        target = await UserService.get_by_id(session, target_id)
        await DiscoveryService.pass_profile(session, user, target)
    except (ValueError, IndexError, TargetUnavailableError) as exc:
        await answer_callback(callback, str(exc), alert=True)
        return
    await safe_delete(callback.message)
    await answer_callback(callback, "👎 Passed")
    await _run_discovery(bot, callback.from_user.id, user, session, settings)


@router.callback_query(F.data.startswith("likes:page:"))
async def cb_likes_page(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    try:
        page = max(0, int((callback.data or "").split(":")[2]))
    except (ValueError, IndexError):
        page = 0
    await answer_callback(callback)
    await _send_likes(callback.from_user.id, user, session, settings, bot, page)


@router.message(Command("likes"))
async def cmd_likes(
    message: Message, state: FSMContext, user: User, session: AsyncSession, settings: Settings, bot: Bot
) -> None:
    await state.clear()
    await _send_likes(message.chat.id, user, session, settings, bot, 0)


@router.callback_query(F.data == "menu:likes")
async def cb_likes(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    await state.clear()
    await answer_callback(callback)
    await _send_likes(callback.from_user.id, user, session, settings, bot, 0)


async def _send_likes(
    chat_id: int,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
    page: int,
) -> None:
    UserService.ensure_registered(user)
    per_page = 5
    people, total = await DiscoveryService.likes_received(
        session, user, offset=page * per_page, limit=per_page
    )
    if total == 0:
        await bot.send_message(
            chat_id,
            "💌 <b>No likes yet</b>\n\n"
            "Keep discovering and liking people who catch your eye. "
            "When someone likes you back, you'll match instantly!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="🔍 Discover people", callback_data="menu:discover")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return

    unlocked = has_premium(user, settings)
    if not unlocked:
        await bot.send_message(
            chat_id,
            f"💌 <b>{total} {plural(total)} liked you</b>\n\n"
            "👑 With Cheers Premium you can see exactly who liked you and match instantly.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="👑 See Premium", callback_data="menu:premium")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return

    has_next = total > (page + 1) * per_page
    await bot.send_message(
        chat_id,
        f"💌 <b>{total} {plural(total)} liked you</b>\n\n"
        "Like them back to create a match instantly. 💘",
        reply_markup=likes_summary_keyboard(page, has_next),
    )
    for person in people:
        await send_profile_card(
            bot,
            chat_id,
            person,
            header="💌 <b>They liked you</b>",
            reply_markup=likes_card_keyboard(person.id),
        )


def plural(count: int) -> str:
    return "person" if count == 1 else "people"


@router.callback_query(F.data.startswith("likes:back:"))
async def cb_like_back(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, target_id)
        result = await DiscoveryService.like(session, user, target, settings.app_timezone)
    except (ValueError, IndexError):
        await answer_callback(callback, "Invalid profile.", alert=True)
        return
    except CheersError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return

    await safe_delete(callback.message)
    if result.matched and result.match:
        await answer_callback(callback, "💥 It's a match!")
        await _notify_match(bot, user, target, result.match)
        await bot.send_message(
            callback.from_user.id,
            f"💥 <b>It's a match!</b> You and <b>{html.escape(target.first_name)}</b> "
            "liked each other.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="💬 Say hello", callback_data=f"chat:open:{result.match.id}")],
                    [Btn(text="💌 Back to likes", callback_data="menu:likes")],
                ]
            ),
        )
    else:
        await answer_callback(callback, "❤️ Like sent!")


@router.callback_query(F.data == "f:menu")
async def cb_filters_menu(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    UserService.ensure_registered(user)
    flt = await DiscoveryService.get_filter(session, user)
    await answer_callback(callback)
    await _render_filters(callback, flt, user, settings)


async def _render_filters(
    callback: CallbackQuery, flt: UserFilter, user: User, settings: Settings
) -> None:
    age_text = f"{flt.min_age}–{flt.max_age}" if not (flt.min_age == 18 and flt.max_age == 60) else "Any (18–60)"
    # Effective gender: explicit filter > preference > auto opposite-sex > Any.
    if flt.gender is not None:
        gender_text = GENDER_LABELS_SHORT.get(flt.gender, str(flt.gender))
    elif user.interested_in == Preference.MEN:
        gender_text = GENDER_LABELS_SHORT[Gender.MAN]
    elif user.interested_in == Preference.WOMEN:
        gender_text = GENDER_LABELS_SHORT[Gender.WOMAN]
    elif user.gender == Gender.MAN:
        gender_text = GENDER_LABELS_SHORT[Gender.WOMAN] + " (opposite sex)"
    elif user.gender == Gender.WOMAN:
        gender_text = GENDER_LABELS_SHORT[Gender.MAN] + " (opposite sex)"
    else:
        gender_text = "Any"
    city_text = html.escape(flt.city) if flt.city else "Any city"
    premium = has_premium(user, settings)
    active_text = "On" if flt.active_recently_only else "Off"
    lock = "" if premium else " 🔒"
    # Effective religion: explicit filter > Any.
    if flt.religion is not None:
        religion_text = RELIGION_LABELS_SHORT.get(flt.religion, str(flt.religion))
    else:
        religion_text = "Any"
    text = (
        "⚙️ <b>Discovery filters</b>\n\n"
        f"🎂 Age: <b>{age_text}</b>\n"
        f"⚧ Gender: <b>{gender_text}</b>\n"
        f"🙏 Religion: <b>{religion_text}</b>\n"
        f"📍 City: <b>{city_text}</b>\n"
        f"🕒 Recently active only: <b>{active_text}</b>{lock}\n"
        f"\n👀 You prefer: <b>{PREFERENCE_LABELS_SHORT.get(user.interested_in, 'Everyone')}</b>"
    )
    if not premium:
        text += "\n\n👑 Advanced filters are part of Premium."
    await safe_edit(callback, text, filters_keyboard(flt))


@router.callback_query(F.data.startswith("f:age:"))
async def cb_filter_age(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    raw = (callback.data or "").split(":")[2]
    if raw == "any":
        min_age, max_age = 18, 99
    else:
        try:
            preset = AGE_PRESETS[int(raw)]
        except (ValueError, IndexError):
            await answer_callback(callback, "Invalid age range.", alert=True)
            return
        min_age, max_age = preset[0], preset[1]
    flt = await DiscoveryService.update_filter(
        session, user, min_age=min_age, max_age=max_age
    )
    await answer_callback(callback)
    await _render_filters(callback, flt, user, settings)


@router.callback_query(F.data.startswith("f:gender:"))
async def cb_filter_gender(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    raw = (callback.data or "").split(":")[2]
    gender = None if raw == "any" else raw
    try:
        flt = await DiscoveryService.update_filter(session, user, gender=gender)
    except (ValueError, CheersError) as exc:
        await answer_callback(callback, str(exc), alert=True)
        return
    await answer_callback(callback)
    await _render_filters(callback, flt, user, settings)


@router.callback_query(F.data.startswith("f:religion:"))
async def cb_filter_religion(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    raw = (callback.data or "").split(":")[2]
    religion = None if raw == "any" else raw
    try:
        flt = await DiscoveryService.update_filter(session, user, religion=religion)
    except (ValueError, CheersError) as exc:
        await answer_callback(callback, str(exc), alert=True)
        return
    await answer_callback(callback)
    await _render_filters(callback, flt, user, settings)


@router.callback_query(F.data == "f:city_menu")
async def cb_filter_city_menu(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📍 <b>Choose a city</b>\n\nYou'll see people in this city only.",
        filter_cities_keyboard(),
    )


@router.callback_query(F.data.startswith("f:city:"))
async def cb_filter_city(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    raw = (callback.data or "").split(":")[2]
    if raw == "any":
        city = None
    else:
        try:
            city = CITIES[int(raw)]
        except (ValueError, IndexError):
            await answer_callback(callback, "Invalid city.", alert=True)
            return
    flt = await DiscoveryService.update_filter(session, user, city=city)
    await answer_callback(callback)
    await _render_filters(callback, flt, user, settings)


@router.callback_query(F.data == "f:active")
async def cb_filter_active(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    if not has_premium(user, settings):
        await answer_callback(
            callback,
            "🕒 'Recently active only' is a Premium filter.",
            alert=True,
        )
        return
    flt = await DiscoveryService.get_filter(session, user)
    flt = await DiscoveryService.update_filter(
        session, user, active_recently_only=not flt.active_recently_only
    )
    await answer_callback(callback)
    await _render_filters(callback, flt, user, settings)


@router.callback_query(F.data == "f:reset")
async def cb_filter_reset(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    flt = await DiscoveryService.reset_filter(session, user)
    await answer_callback(callback, "Filters reset.")
    await _render_filters(callback, flt, user, settings)


@router.callback_query(F.data == "f:done")
async def cb_filter_done(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    await answer_callback(callback, "Filters saved ✅")
    flt = await DiscoveryService.get_filter(session, user)
    summary = (
        f"⚙️ <b>Filters saved</b>\n\n"
        f"🎂 {flt.min_age}–{flt.max_age} · "
        f"⚧ {GENDER_LABELS_SHORT.get(flt.gender, 'Any') if flt.gender else 'Any'} · "
        f"📍 {html.escape(flt.city) if flt.city else 'Any city'}"
    )
    await safe_edit(
        callback,
        summary,
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="🔍 Start discovering", callback_data="menu:discover")],
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
            ]
        ),
    )
