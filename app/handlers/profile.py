"""Viewing and editing the user's own profile."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MAX_PHOTOS, Intention
from app.database.models import User
from app.keyboards.profile import (
    edit_intentions_keyboard,
    edit_interests_keyboard,
    edit_menu_keyboard,
    edit_photos_keyboard,
    profile_keyboard,
)
from app.services.errors import CheersError, NotRegisteredError
from app.services.users import UserService
from app.states.forms import EditProfile
from app.utils.render import answer_callback, safe_edit, send_profile_card
from app.utils.validators import (
    ValidationError,
    parse_birth_date,
    validate_bio,
    validate_city,
    validate_first_name,
    validate_photo_count,
)

router = Router(name="profile")


async def _show_profile(message: Message, user: User, bot: Bot) -> None:
    UserService.ensure_registered(user)
    await send_profile_card(
        bot,
        message.chat.id,
        user,
        header="👤 <b>Your Cheers profile</b>",
        reply_markup=profile_keyboard(),
    )


async def _finish_edit(
    callback: CallbackQuery, state: FSMContext, user: User, bot: Bot
) -> None:
    await state.clear()
    await answer_callback(callback, "Profile updated ✅")
    await safe_edit(callback, "✅ <b>Profile updated.</b>")
    await send_profile_card(
        bot,
        callback.from_user.id,
        user,
        header="👤 <b>Your updated profile</b>",
        reply_markup=profile_keyboard(),
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, user: User, bot: Bot) -> None:
    await state.clear()
    try:
        await _show_profile(message, user, bot)
    except NotRegisteredError as exc:
        await message.answer(exc.user_message)


@router.message(Command("editprofile"))
async def cmd_edit_profile(
    message: Message, state: FSMContext, user: User
) -> None:
    await state.clear()
    if not user.is_registered:
        await message.answer("Please finish creating your profile first with /start.")
        return
    await message.answer(
        "✏️ <b>Edit profile</b>\n\nWhat would you like to change?",
        reply_markup=edit_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:profile")
async def cb_profile(
    callback: CallbackQuery, state: FSMContext, user: User, bot: Bot
) -> None:
    await state.clear()
    try:
        UserService.ensure_registered(user)
    except NotRegisteredError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return
    await answer_callback(callback)
    await send_profile_card(
        bot,
        callback.from_user.id,
        user,
        header="👤 <b>Your Cheers profile</b>",
        reply_markup=profile_keyboard(),
    )


@router.callback_query(F.data == "edit:menu")
async def cb_edit_menu(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    if not user.is_registered:
        await answer_callback(callback, "Finish registration with /start first.", alert=True)
        return
    await answer_callback(callback)
    await safe_edit(
        callback,
        "✏️ <b>Edit profile</b>\n\nWhat would you like to change?",
        edit_menu_keyboard(),
    )


@router.callback_query(F.data == "edit:field:first_name")
async def cb_edit_first_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.first_name)
    await answer_callback(callback)
    await safe_edit(callback, "👤 Send your new first name (2–32 characters).")


@router.message(StateFilter(EditProfile.first_name), F.text)
async def msg_edit_first_name(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
) -> None:
    try:
        name = validate_first_name(message.text or "")
        user = await UserService.update_profile(session, user, first_name=name)
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.clear()
    await message.answer("✅ Name updated.")
    await send_profile_card(bot, message.chat.id, user, reply_markup=profile_keyboard())


@router.callback_query(F.data == "edit:field:birth_date")
async def cb_edit_birth_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.birth_date)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "🎂 Send your date of birth as <code>DD/MM/YYYY</code>.\n"
        "You must remain 18 or older to use Cheers.",
    )


@router.message(StateFilter(EditProfile.birth_date), F.text)
async def msg_edit_birth_date(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
) -> None:
    try:
        birth_date = parse_birth_date(message.text or "")
        user = await UserService.update_profile(session, user, birth_date=birth_date)
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.clear()
    await message.answer("✅ Date of birth updated.")
    await send_profile_card(bot, message.chat.id, user, reply_markup=profile_keyboard())


@router.callback_query(F.data == "edit:field:city")
async def cb_edit_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.city)
    await answer_callback(callback)
    await safe_edit(callback, "📍 Send your city name.")


@router.message(StateFilter(EditProfile.city), F.text)
async def msg_edit_city(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
) -> None:
    try:
        city = validate_city(message.text or "")
        user = await UserService.update_profile(session, user, city=city)
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.clear()
    await message.answer("✅ City updated.")
    await send_profile_card(bot, message.chat.id, user, reply_markup=profile_keyboard())


@router.callback_query(F.data == "edit:field:bio")
async def cb_edit_bio(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.bio)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📝 Send your new bio (10–500 characters).\nKeep it friendly and avoid contact details.",
    )


@router.message(StateFilter(EditProfile.bio), F.text)
async def msg_edit_bio(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
) -> None:
    try:
        bio = validate_bio(message.text or "")
        user = await UserService.update_profile(session, user, bio=bio)
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.clear()
    await message.answer("✅ Bio updated.")
    await send_profile_card(bot, message.chat.id, user, reply_markup=profile_keyboard())


@router.callback_query(F.data == "edit:field:interests")
async def cb_edit_interests(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(EditProfile.interests)
    selected = list(user.interests or [])
    await state.update_data(interests=selected)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "✨ <b>Your interests</b>\nChoose up to 8, then save.",
        edit_interests_keyboard(selected),
    )


@router.callback_query(StateFilter(EditProfile.interests), F.data.startswith("edit:int:"))
async def cb_edit_interest_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":")[-1]
    from app.constants import INTERESTS

    if key not in INTERESTS:
        await answer_callback(callback, "Unknown interest.", alert=True)
        return
    data = await state.get_data()
    selected = list(data.get("interests", []))
    if key in selected:
        selected.remove(key)
    else:
        if len(selected) >= 8:
            await answer_callback(callback, "Choose up to 8 interests.", alert=True)
            return
        selected.append(key)
    await state.update_data(interests=selected)
    await answer_callback(callback)
    await safe_edit(
        callback,
        f"✨ <b>Your interests</b>\nSelected: {len(selected)}/8",
        edit_interests_keyboard(selected),
    )


@router.callback_query(StateFilter(EditProfile.interests), F.data == "edit:int_done")
async def cb_edit_interests_done(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    data = await state.get_data()
    selected = list(data.get("interests", []))
    try:
        user = await UserService.update_profile(session, user, interests=selected)
    except ValidationError as exc:
        await answer_callback(callback, str(exc), alert=True)
        return
    await _finish_edit(callback, state, user, bot)


@router.callback_query(F.data == "edit:field:intention")
async def cb_edit_intention(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.intention)
    await answer_callback(callback)
    await safe_edit(callback, "💞 What are you looking for?", edit_intentions_keyboard())


@router.callback_query(StateFilter(EditProfile.intention), F.data.startswith("edit:goal:"))
async def cb_edit_intention_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    raw = (callback.data or "").split(":")[-1]
    try:
        intention = Intention(raw)
        user = await UserService.update_profile(session, user, intention=intention)
    except (ValueError, ValidationError, CheersError) as exc:
        await answer_callback(callback, f"Could not update: {exc}", alert=True)
        return
    await _finish_edit(callback, state, user, bot)


@router.callback_query(F.data == "edit:field:photos")
async def cb_edit_photos(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditProfile.photos)
    await state.update_data(photos=[])
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📸 <b>Update your photos</b>\n\n"
        f"Send 1–{MAX_PHOTOS} new photos, one at a time. They will replace your current photos.\n"
        "Your first photo becomes your main photo.",
        edit_photos_keyboard(False),
    )


@router.message(StateFilter(EditProfile.photos), F.photo)
async def msg_edit_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    data = await state.get_data()
    photos = list(data.get("photos", []))
    if len(photos) >= MAX_PHOTOS:
        await message.answer("You already selected the maximum number of photos.")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(
        f"✅ Photo {len(photos)}/{MAX_PHOTOS} selected. Send another or save.",
        reply_markup=edit_photos_keyboard(True),
    )


@router.callback_query(StateFilter(EditProfile.photos), F.data == "edit:photos_done")
async def cb_edit_photos_done(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    data = await state.get_data()
    photos = list(data.get("photos", []))
    try:
        validate_photo_count(len(photos))
        user = await UserService.replace_photos(session, user, photos)
    except (ValidationError, CheersError) as exc:
        await answer_callback(callback, str(exc), alert=True)
        return
    await _finish_edit(callback, state, user, bot)
