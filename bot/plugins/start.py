import asyncio
import logging 
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, ChatInviteLink, ChatPrivileges
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from bot.core.bot_instance import bot, bot_loop, ani_cache
from bot.Script import botmaker
from helper_func import *
from bot.core.database import db
from asyncio import sleep as asleep, gather
from pyrogram.filters import command, private, user
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram import filters
from pyrogram.types import Message
import subprocess
from config import Var
from bot.core.func_utils import decode, editMessage, sendMessage, new_task, convertTime, getfeed
from bot.core.auto_animes import get_animes
from bot.core.reporter import rep
import time
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram.types import Message

Var.BAN_SUPPORT = f"{Var.BAN_SUPPORT}"

chat_data_cache = {}
logger = logging.getLogger(__name__)

@bot.on_message(filters.command('start') & filters.private)
@new_task
async def start_msg(client: Client, message: Message):
    user_id = message.from_user.id
    from_user = message.from_user
    txtargs = message.text.split()

    try:
        temp = await sendMessage(message, "<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")
        # your other logic can go here (processing txtargs, deep links, etc.)
    finally:
        await temp.delete()


    # Check if user is banned
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        await temp.delete()
        return await message.reply_text(
            "<b>⛔️ You are Bᴀɴɴᴇᴅ from using this bot.</b>\n\n"
            "<i>Contact support if you think this is a mistake.</i>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=Var.BAN_SUPPORT)]]
            )
        )

    # Check if user is subscribed to required channels
    try:
        if not await is_subscribed(client, user_id):
            await temp.delete()
            return await not_joined(client, message)
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}")
        await editMessage(temp, "<b>❌ Error checking channel subscription. Please try again or contact @V_Sbotmaker.</b>")
        return

    # Add user to database if not present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except Exception as e:
            logger.error(f"Error adding user {user_id} to database: {e}")

    FILE_AUTO_DELETE = await db.get_del_timer()  # e.g., 3600 seconds

    if len(txtargs) <= 1:
        await temp.delete()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("•⚡️ ᴍᴀɪɴ ʜᴜʙ •", url=Var.MHCHANNEL_URL)],
            [InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"), InlineKeyboardButton('ʜᴇʟᴘ •', callback_data="help")],
            [InlineKeyboardButton("•👨‍💻 Dᴇᴠᴇʟᴏᴘᴇʀ •", url="https://t.me/V_Sbotmaker")]
        ])

        smsg = botmaker.START_MSG.format(
            first=from_user.first_name,
            last=from_user.last_name or from_user.first_name,
            username=None if not from_user.username else '@' + from_user.username,
            mention=from_user.mention,
            id=from_user.id
        )

        await message.reply_photo(
            photo=Var.START_PIC,
            caption=smsg,
            reply_markup=reply_markup,
            message_effect_id=5104841245755180586
        )
        return

    # Deep-link handling
    try:
        base64_string = txtargs[1]
        arg = (await decode(base64_string)).split('-')
        botmaker_msgs = []

        if len(arg) == 2 and arg[0] == 'get':
            try:
                fid = int(int(arg[1]) / abs(int(Var.FILE_STORE)))
                msg = await client.get_messages(Var.FILE_STORE, message_ids=fid)
                if msg.empty:
                    return await editMessage(temp, "<b>File Not Found!</b>")
                nmsg = await msg.copy(message.chat.id, reply_markup=None)
                botmaker_msgs.append(nmsg)
                await rep.report(f"User {user_id} retrieved file {fid}", "info")
            except Exception as e:
                await rep.report(f"User: {user_id} | Error: {str(e)}", "error")
                return await editMessage(temp, "<b>Input Link Code is Invalid!</b>")

        elif len(arg) in [2, 3]:
            try:
                if len(arg) == 2:
                    ids = [int(int(arg[1]) / abs(client.db_channel.id))]
                else:
                    start = int(int(arg[1]) / abs(client.db_channel.id))
                    end = int(int(arg[2]) / abs(client.db_channel.id))
                    ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))
                messages = await client.get_messages(client.db_channel.id, message_ids=ids)
                for msg in messages:
                    caption = (botmaker.CUSTOM_CAPTION.format(previouscaption="" if not msg.caption else msg.caption.html,
                                                        filename=msg.document.file_name) if bool(botmaker.CUSTOM_CAPTION) and bool(msg.document)
                              else ("" if not msg.caption else msg.caption.html))
                    reply_markup = msg.reply_markup if not Var.DISABLE_CHANNEL_BUTTON else None
                    try:
                        copied_msg = await msg.copy(
                            chat_id=message.from_user.id,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            protect_content=Var.PROTECT_CONTENT
                        )
                        botmaker_msgs.append(copied_msg)
                    except FloodWait as e:
                        await asleep(e.x)
                        copied_msg = await msg.copy(
                            chat_id=message.from_user.id,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            protect_content=Var.PROTECT_CONTENT
                        )
                        botmaker_msgs.append(copied_msg)
                    except Exception as e:
                        logger.error(f"Failed to send message: {e}")
            except Exception as e:
                logger.error(f"Error processing IDs: {e}")
                await rep.report(f"User: {user_id} | Error: {str(e)}", "error")
                return await editMessage(temp, "<b>Input Link Code is Invalid!</b>")

        else:
            return await editMessage(temp, "<b>Input Link is Invalid for Usage!</b>")

        # Auto-delete logic
        if FILE_AUTO_DELETE > 0:
            notification_msg = await sendMessage(
                message,
                f"<b>⚠️ Wᴀʀɴɪɴɢ ⚠️\n\nTʜᴇsᴇ Fɪʟᴇ Wɪʟʟ Bᴇ Dᴇʟᴇᴛᴇᴅ Aᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ Iɴ {get_exp_time(FILE_AUTO_DELETE)}. Pʟᴇᴀsᴇ sᴀᴠᴇ ᴏʀ ғᴏʀᴡᴀʀᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ʙᴇғᴏʀᴇ ɪᴛ ɢᴇᴛs Dᴇʟᴇᴛᴇᴅ.</b>"
            )
            await asleep(FILE_AUTO_DELETE)
            for snt_msg in botmaker_msgs:
                try:
                    await snt_msg.delete()
                except Exception as e:
                    logger.error(f"Error deleting message {snt_msg.id}: {e}")
            try:
                # Fetch bot's username
                me = await client.get_me()
                if not me.username:
                    await editMessage(notification_msg, "<b>❌ Error: Bot username is not set.</b>")
                    return
                reload_url = f"https://t.me/{me.username}?start={base64_string}"
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ!", url=reload_url)]]
                )
                await editMessage(
                    notification_msg,
                    "<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!\n\nᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ᴅᴇʟᴇᴛᴇᴅ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ 👇</b>",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error updating notification: {e}")
        await temp.delete()

    except Exception as e:
        await rep.report(f"User: {user_id} | Error: {str(e)}", "error")
        await editMessage(temp, "<b>Input Link Code Decode Failed!</b>")

async def not_joined(client: Client, message: Message):
    user_id = message.from_user.id
    from_user = message.from_user
    try:
        temp = await sendMessage(message, "<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")
        # your other logic can go here (processing txtargs, deep links, etc.)
    finally:
        await temp.delete()
        
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()
        if not all_channels:
            logger.error("No channels found in database for force subscription.")
            await editMessage(temp, "<b>❌ Error: No channels configured for subscription.</b>")
            return

        # Fetch bot's username
        me = await client.get_me()
        if not me.username:
            await editMessage(temp, "<b>❌ Error: Bot username is not set.</b>")
            return

        for chat_id in all_channels:
            mode = await db.get_channel_mode(chat_id)
            await message.reply_chat_action(ChatAction.TYPING)
            if not await is_subscribed(client, user_id, chat_id):
                try:
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data
                    name = data.title
                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=Var.FSUB_LINK_EXPIRY) if Var.FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link
                    else:
                        link = f"https://t.me/{data.username}" if data.username else (
                            await client.create_chat_invite_link(
                                chat_id=chat_id,
                                expire_date=datetime.utcnow() + timedelta(seconds=Var.FSUB_LINK_EXPIRY) if Var.FSUB_LINK_EXPIRY else None
                            )
                        ).invite_link
                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    await editMessage(temp, f"<b>{'! ' * count}</b>")
                except Exception as e:
                    logger.error(f"Error with chat {chat_id}: {e}")
                    return await editMessage(
                        temp,
                        f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @V_Sbotmaker</i></b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )
        if count == 0:
            await temp.delete()
            return  # User is subscribed to all channels, proceed to start message

# Your proposed button logic
        if len(message.command) > 1:
            buttons.append([InlineKeyboardButton("♻️ Try Again ♻️", url=f"https://t.me/{me.username}?start={message.command[1]}")])
        else:
            buttons.append([InlineKeyboardButton("♻️ Try Again ♻️", url=f"https://t.me/{me.username}?start=true")])
                           
        await message.reply_photo(
            photo=Var.FORCE_PIC,
            caption=botmaker.FORCE_MSG.format(
                first=from_user.first_name,
                last=from_user.last_name or from_user.first_name,
                username=None if not from_user.username else '@' + from_user.username,
                mention=from_user.mention,
                id=from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Error in not_joined: {e}")
        await editMessage(
            temp,
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @V_Sbotmaker</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )
    finally:
        await temp.delete()

@bot.on_message(filters.command('commands') & filters.private)
async def bcmd(bot: Client, message: Message):
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]])
    await message.reply(text=botmaker.CMD_TXT, reply_markup=reply_markup, quote=True)

@bot.on_message(command('pause') & private & user(Var.ADMINS))
async def pause_fetch(client, message):
    ani_cache['fetch_animes'] = False
    await sendMessage(message, "Successfully Paused Fetching Anime...")

@bot.on_message(command('resume') & private & user(Var.ADMINS))
async def resume_fetch(client, message):
    ani_cache['fetch_animes'] = True
    await sendMessage(message, "Successfully Resumed Fetching Anime...")

@bot.on_message(command('log') & private & user(Var.ADMINS))
@new_task
async def _log(client, message):
    await message.reply_document("log.txt", quote=True)

@bot.on_message(command('addlink') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    args = message.text.split()
    if len(args) <= 1:
        return await sendMessage(message, "<b>No Link Found to Add</b>")
    
    Var.RSS_ITEMS.append(args[1])  # Fixed: Use args[1] as the link
    await sendMessage(message, f"<code>Global Link Added Successfully!</code>\n\n<b> • All Link(s) :</b> {', '.join(Var.RSS_ITEMS)}")

@bot.on_message(command('addtask') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    args = message.text.split()
    if len(args) <= 1:
        return await sendMessage(message, "<b>No Task Found to Add</b>")
    
    index = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
    if not (taskInfo := await getfeed(args[1], index)):
        return await sendMessage(message, "<b>No Task Found to Add for the Provided Link</b>")
    
    ani_task = bot_loop.create_task(get_animes(taskInfo.title, taskInfo.link, True))
    await sendMessage(message, f"<i><b>Task Added Successfully!</b></i>\n\n    • <b>Task Name :</b> {taskInfo.title}\n    • <b>Task Link :</b> {args[1]}")
