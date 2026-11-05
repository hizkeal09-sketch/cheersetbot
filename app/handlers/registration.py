"""Conversational 18+ onboarding and profile creation."""

from __future__ import annotations

import contextlib
import html
from datetime import date, datetime

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    CITIES,
    GENDER_LABELS,
    INTENTION_LABELS,
    INTERESTS,
    MAX_PHOTOS,
    Gender,
    Intention,
    Preference,
)
from app.database.models import User
from app.keyboards.common import (
    main_menu,
    onboarding_keyboard,
    remove_reply_keyboard,
)
from app.keyboards.registration import (
    city_keyboard,
    confirm_keyboard,
    gender_keyboard,
    intention_keyboard,
    interests_keyboard,
    photos_keyboard,
)
from app.services.errors import CheersError
from app.services.users import RegistrationData, UserService
from app.states.forms import Registration
from app.utils.render import answer_callback, safe_edit, send_profile_card
from app.utils.time import calculate_age, utcnow
from app.utils.validators import (
    ValidationError,
    parse_birth_date,
    validate_bio,
    validate_city,
    validate_first_name,
    validate_photo_count,
)

router = Router(name="registration")


def _privacy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ I'm 18 — continue", callback_data="reg:age_ok")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:home")],
        ]
    )


def _preview(data: dict) -> str:
    name = html.escape(str(data.get("first_name", "You")))
    dob_raw = data.get("birth_date")
    age = "—"
    if dob_raw:
        with contextlib.suppress(ValueError):
            age = str(calculate_age(date.fromisoformat(dob_raw)))
    gender = GENDER_LABELS.get(Gender(data["gender"]), "") if data.get("gender") else ""
    city = html.escape(str(data.get("city", "")))
    intention = INTENTION_LABELS.get(Intention(data["intention"]), "") if data.get("intention") else ""
    bio = html.escape(str(data.get("bio") or "No bio yet"))
    interests = [INTERESTS[key] for key in data.get("interests", []) if key in INTERESTS]
    return (
        "✨ <b>Here's your profile preview</b>\n\n"
        f"<b>{name}, {age}</b>\n"
        f"📍 {city}, Ethiopia\n"
        f"{gender}\n"
        f"💞 {intention}\n\n"
        f"<i>{bio}</i>\n\n"
        f"✨ {' · '.join(interests)}\n"
        f"📸 {len(data.get('photos', []))} photo(s)\n\n"
        "Everything look good?"
    )


@router.callback_query(F.data == "reg:privacy")
async def cb_privacy(callback: CallbackQuery) -> None:
    from app.handlers.common import PRIVACY_TEXT

    await answer_callback(callback)
    await safe_edit(callback, PRIVACY_TEXT, _privacy_keyboard())


@router.callback_query(F.data == "reg:age_ok")
async def cb_age_ok(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await answer_callback(callback)
    if user.is_registered:
        await safe_edit(
            callback,
            "✅ You're already registered! Use the menu to keep exploring.",
            main_menu(),
        )
        return

    await state.clear()
    await state.update_data(consent_at=utcnow().isoformat())
    await state.set_state(Registration.first_name)
    await safe_edit(
        callback,
        "🎉 <b>You're in!</b>\n\n"
        "First things first: what should people call you?\n"
        "Send your first name (2–32 characters).",
    )


@router.message(StateFilter(Registration.first_name), F.text)
async def msg_first_name(message: Message, state: FSMContext) -> None:
    try:
        name = validate_first_name(message.text or "")
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.update_data(first_name=name)
    await state.set_state(Registration.dob)
    await message.answer(
        f"Nice to meet you, <b>{html.escape(name)}</b>! 🍻\n\n"
        "🎂 What's your date of birth?\n"
        "Send it as <code>DD/MM/YYYY</code> (for example <code>14/02/1996</code>).\n\n"
        "<i>You must be 18 or older. Your exact birth date is never shown to others — only your age.</i>"
    )


@router.message(StateFilter(Registration.dob), F.text)
async def msg_dob(message: Message, state: FSMContext) -> None:
    try:
        birth_date = parse_birth_date(message.text or "")
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}\n\nTry again using DD/MM/YYYY.")
        return
    await state.update_data(birth_date=birth_date.isoformat())
    await state.set_state(Registration.gender)
    await message.answer("How do you identify?", reply_markup=gender_keyboard())


@router.callback_query(StateFilter(Registration.gender), F.data.startswith("reg:gender:"))
async def cb_gender(callback: CallbackQuery, state: FSMContext) -> None:
    raw = (callback.data or "").split(":")[-1]
    try:
        gender = Gender(raw)
    except ValueError:
        await answer_callback(callback, "Please choose one of the options.", alert=True)
        return
    await state.update_data(gender=gender.value)
    await state.set_state(Registration.city)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📍 Which city are you based in?\n\nPick one below, or choose <b>Other city</b> to type it.",
        city_keyboard(),
    )


@router.callback_query(StateFilter(Registration.city), F.data.startswith("reg:city:"))
async def cb_city(callback: CallbackQuery, state: FSMContext) -> None:
    raw = (callback.data or "").split(":", 2)[-1]
    if raw == "other":
        await state.set_state(Registration.custom_city)
        await answer_callback(callback)
        await safe_edit(callback, "🌍 Type the name of your city.")
        return
    try:
        city = CITIES[int(raw)]
    except (ValueError, IndexError):
        await answer_callback(callback, "Please choose a city from the list.", alert=True)
        return
    await state.update_data(city=city)
    await answer_callback(callback)
    await safe_edit(callback, f"📍 City: <b>{html.escape(city)}</b>")
    await _after_location(callback.message, state)


@router.message(StateFilter(Registration.custom_city), F.text)
async def msg_custom_city(message: Message, state: FSMContext) -> None:
    try:
        city = validate_city(message.text or "")
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.update_data(city=city)
    await _after_location(message, state)


async def _after_location(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.bio)
    await message.answer(
        "📝 <b>Tell people a little about yourself</b>\n\n"
        "What makes you you? What are you looking for? (10–500 characters)\n\n"
        "Keep it friendly — no phone numbers, usernames or links.",
        reply_markup=remove_reply_keyboard(),
    )
    await message.answer(
        "Or skip this step for now.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏭ Skip bio", callback_data="reg:skip_bio")]
            ]
        ),
    )


@router.message(StateFilter(Registration.bio), F.text)
async def msg_bio(message: Message, state: FSMContext) -> None:
    try:
        bio = validate_bio(message.text or "")
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await state.update_data(bio=bio)
    await state.set_state(Registration.interests)
    await message.answer(
        "✨ <b>What are you into?</b>\nPick up to 8 interests.",
        reply_markup=interests_keyboard([]),
    )


@router.callback_query(StateFilter(Registration.bio), F.data == "reg:skip_bio")
async def cb_skip_bio(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(bio=None)
    await state.set_state(Registration.interests)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "✨ <b>What are you into?</b>\nPick up to 8 interests.",
        interests_keyboard([]),
    )


@router.callback_query(StateFilter(Registration.interests), F.data.startswith("reg:int:"))
async def cb_interest_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":")[-1]
    if key not in INTERESTS:
        await answer_callback(callback, "Unknown interest.", alert=True)
        return
    data = await state.get_data()
    selected = list(data.get("interests", []))
    if key in selected:
        selected.remove(key)
    else:
        if len(selected) >= 8:
            await answer_callback(callback, "You can choose up to 8 interests.", alert=True)
            return
        selected.append(key)
    await state.update_data(interests=selected)
    await answer_callback(callback)
    await safe_edit(
        callback,
        f"✨ <b>What are you into?</b>\nSelected: {len(selected)}/8",
        interests_keyboard(selected),
    )


@router.callback_query(StateFilter(Registration.interests), F.data == "reg:int_done")
async def cb_interests_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = list(data.get("interests", []))
    if not selected:
        await answer_callback(callback, "Choose at least one interest.", alert=True)
        return
    await state.set_state(Registration.intention)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "💞 <b>What are you looking for?</b>",
        intention_keyboard(),
    )


@router.callback_query(StateFilter(Registration.intention), F.data.startswith("reg:goal:"))
async def cb_intention(callback: CallbackQuery, state: FSMContext) -> None:
    raw = (callback.data or "").split(":")[-1]
    try:
        intention = Intention(raw)
    except ValueError:
        await answer_callback(callback, "Please choose an option.", alert=True)
        return
    await state.update_data(intention=intention.value)
    await state.set_state(Registration.photos)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📸 <b>Add your photos</b>\n\n"
        f"Send up to {MAX_PHOTOS} photos, one at a time. Your first photo is your main photo.\n"
        "Clear face photos work best. No nudity or other people's photos, please.",
        photos_keyboard(False),
    )


@router.message(StateFilter(Registration.photos), F.photo)
async def msg_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    data = await state.get_data()
    photos = list(data.get("photos", []))
    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"📸 You already have {MAX_PHOTOS} photos. Tap <b>Continue</b>.")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    remaining = MAX_PHOTOS - len(photos)
    await message.answer(
        f"✅ Photo {len(photos)}/{MAX_PHOTOS} added."
        + (f"\nSend another ({remaining} slot(s) left) or tap Continue." if remaining else "\nThat's the maximum — tap Continue."),
        reply_markup=photos_keyboard(True),
    )


@router.callback_query(StateFilter(Registration.photos), F.data == "reg:photo_remove")
async def cb_photo_remove(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    photos = list(data.get("photos", []))
    if not photos:
        await answer_callback(callback, "No photos to remove.", alert=True)
        return
    photos.pop()
    await state.update_data(photos=photos)
    await answer_callback(callback, "Removed the last photo.")
    await safe_edit(
        callback,
        f"📸 {len(photos)}/{MAX_PHOTOS} photos added. Send another or tap Continue.",
        photos_keyboard(bool(photos)),
    )


@router.callback_query(StateFilter(Registration.photos), F.data == "reg:photo_done")
async def cb_photo_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    photos = list(data.get("photos", []))
    try:
        validate_photo_count(len(photos))
    except ValidationError as exc:
        await answer_callback(callback, str(exc), alert=True)
        return
    await state.set_state(Registration.confirm)
    await answer_callback(callback)
    await safe_edit(callback, _preview(data), confirm_keyboard())


@router.callback_query(StateFilter(Registration.confirm), F.data == "reg:confirm")
async def cb_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    data = await state.get_data()
    try:
        birth_date = date.fromisoformat(data["birth_date"])
        if calculate_age(birth_date) < 18:
            raise ValidationError("You must be 18 or older.")
        consent_raw = data.get("consent_at")
        consent_at = datetime.fromisoformat(consent_raw) if consent_raw else None
        payload = RegistrationData(
            first_name=data["first_name"],
            birth_date=birth_date,
            gender=Gender(data["gender"]),
            interested_in=(
                Preference.WOMEN if Gender(data["gender"]) == Gender.MAN else Preference.MEN
            ),
            city=data["city"],
            intention=Intention(data["intention"]),
            interests=list(data.get("interests", [])),
            bio=data.get("bio"),
            photos=list(data.get("photos", [])),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            consent_at=consent_at,
        )
        user = await UserService.complete_registration(session, user, payload)
    except (KeyError, ValueError, ValidationError, CheersError) as exc:
        await answer_callback(callback, f"Could not save your profile: {exc}", alert=True)
        return

    await state.clear()
    await answer_callback(callback, "Profile created! 🎉")
    await safe_edit(
        callback,
        "🎉 <b>Your Cheers profile is live!</b>\n\n"
        "Here's your card. Start discovering people whenever you're ready.",
        main_menu(),
    )
    await send_profile_card(bot, callback.from_user.id, user, reply_markup=main_menu())


@router.callback_query(F.data == "reg:restart")
async def cb_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback, "Starting over.")
    await safe_edit(
        callback,
        "No problem — let's start fresh.\n\nClick below to confirm you're 18 or older.",
        onboarding_keyboard(),
    )


@router.callback_query(F.data == "reg:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback, "Setup cancelled.")
    await safe_edit(
        callback,
        "✖️ Setup cancelled. No profile was created.\n\nTap /start whenever you're ready.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Start again", callback_data="reg:age_ok")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("reg:back:"))
async def cb_reg_back(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Go back one step in registration so the user can fix a mistake."""
    target = callback.data.split(":", 2)[-1]
    data = await state.get_data()

    if target == "dob":
        await state.update_data(
            gender=None,
            city=None,
            latitude=None,
            longitude=None,
            bio=None,
            interests=[],
            intention=None,
            photos=[],
        )
        await state.set_state(Registration.dob)
        name = data.get("first_name", "You")
        await safe_edit(
            callback,
            f"Nice to meet you, <b>{html.escape(name)}</b>! 🍻\n\n"
            "🎂 What's your date of birth?\n"
            "Send it as <code>DD/MM/YYYY</code> (for example <code>14/02/1996</code>).\n\n"
            "<i>You must be 18 or older. Your exact birth date is never shown to others — "
            "only your age.</i>",
        )

    elif target == "gender":
        await state.update_data(
            city=None,
            latitude=None,
            longitude=None,
            bio=None,
            interests=[],
            intention=None,
            photos=[],
        )
        await state.set_state(Registration.gender)
        await safe_edit(
            callback,
            "How do you identify?",
            reply_markup=gender_keyboard(),
        )

    elif target == "city":
        await state.update_data(
            city=None,
            latitude=None,
            longitude=None,
        )
        await state.set_state(Registration.city)
        await safe_edit(
            callback,
            "📍 Which city are you based in?\n\nPick one below, or choose <b>Other city</b> to type it.",
            reply_markup=city_keyboard(),
        )

    elif target == "bio":
        await state.update_data(
            interests=[],
            intention=None,
            photos=[],
        )
        await state.set_state(Registration.bio)
        await safe_edit(
            callback,
            "📝 <b>Tell people a little about yourself</b>\n\n"
            "What makes you you? What are you looking for? (10–500 characters)\n\n"
            "Keep it friendly — no phone numbers, usernames or links.",
        )
        await callback.message.answer(
            "Or skip this step for now.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⏭ Skip bio", callback_data="reg:skip_bio")]
                ]
            ),
        )

    elif target == "interests":
        await state.update_data(
            intention=None,
            photos=[],
        )
        await state.set_state(Registration.interests)
        selected = list(data.get("interests", []))
        await safe_edit(
            callback,
            f"✨ <b>What are you into?</b>\nSelected: {len(selected)}/8",
            reply_markup=interests_keyboard(selected),
        )

    elif target == "intention":
        await state.update_data(photos=[])
        await state.set_state(Registration.intention)
        await safe_edit(
            callback,
            "💞 <b>What are you looking for?</b>",
            reply_markup=intention_keyboard(),
        )

    elif target == "photos":
        await state.update_data(photos=[])
        await state.set_state(Registration.photos)
        await safe_edit(
            callback,
            "📸 <b>Add your photos</b>\n\n"
            f"Send up to {MAX_PHOTOS} photos, one at a time. Your first photo is your main photo.\n"
            "Clear face photos work best. No nudity or other people's photos, please.",
            reply_markup=photos_keyboard(False),
        )

    await answer_callback(callback, "Going back…")
