"""FSM state groups."""

from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    first_name = State()
    dob = State()
    gender = State()
    preference = State()
    city = State()
    custom_city = State()
    location = State()
    bio = State()
    interests = State()
    intention = State()
    photos = State()
    confirm = State()


class EditProfile(StatesGroup):
    first_name = State()
    birth_date = State()
    city = State()
    bio = State()
    interests = State()
    intention = State()
    photos = State()


class ChatStates(StatesGroup):
    active = State()


class ReportFlow(StatesGroup):
    reason = State()
    details = State()


class DeleteAccount(StatesGroup):
    confirm = State()


class AdminFlow(StatesGroup):
    search = State()
    broadcast = State()
    delete_confirm = State()
