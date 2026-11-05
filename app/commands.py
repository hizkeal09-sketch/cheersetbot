"""Telegram command menu shared by polling and webhook runtimes."""

from __future__ import annotations

from aiogram.types import BotCommand

BOT_COMMANDS = [
    BotCommand(command="start", description="Start or open the main menu"),
    BotCommand(command="discover", description="Meet someone new"),
    BotCommand(command="likes", description="See who liked you"),
    BotCommand(command="matches", description="Your matches and chats"),
    BotCommand(command="profile", description="View your profile"),
    BotCommand(command="editprofile", description="Edit your profile"),
    BotCommand(command="settings", description="Filters, pause and privacy"),
    BotCommand(command="premium", description="Premium features"),
    BotCommand(command="report", description="Report a user"),
    BotCommand(command="block", description="Block a user"),
    BotCommand(command="pause", description="Pause your profile"),
    BotCommand(command="deleteaccount", description="Delete your account"),
    BotCommand(command="help", description="Help and safety"),
    BotCommand(command="admin", description="Admin dashboard (staff only)"),
]
