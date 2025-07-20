import motor, asyncio
import motor.motor_asyncio
import pymongo, os
import logging
from config import Var
import time
from bot.core.bot_instance import bot
from datetime import datetime, timedelta



logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Database:
    def __init__(self, uri=Var.DB_URI, database_name=Var.DB_NAME):
        """Initialize MongoDB connection with a single URI and database name."""
        self.__client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.__db = self.__client[database_name]
        
        # Collections for user, admin, ban, channel, and force-sub management
        self.channel_data = self.__db['channels']
        self.admins_data = self.__db['admins']
        self.user_data = self.__db['users']
        self.banned_user_data = self.__db['banned_user']
        self.autho_user_data = self.__db['autho_user']
        self.del_timer_data = self.__db['del_timer']
        self.fsub_data = self.__db['fsub']
        self.rqst_fsub_data = self.__db['request_forcesub']
        self.rqst_fsub_channel_data = self.__db['request_forcesub_channel']
        
        # Anime collection (named using BOT_TOKEN)
        self.__animes = self.__db[f"animes_{Var.BOT_TOKEN.split(':')[0]}"]


    # USER DATA
    async def present_user(self, user_id: int):
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_user(self, user_id: int):
        await self.user_data.insert_one({'_id': user_id})
        return

    async def full_userbase(self):
        user_docs = await self.user_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in user_docs]
        return user_ids

    async def del_user(self, user_id: int):
        await self.user_data.delete_one({'_id': user_id})
        return


    # ADMIN DATA
    async def admin_exist(self, admin_id: int):
        found = await self.admins_data.find_one({'_id': admin_id})
        return bool(found)

    async def add_admin(self, admin_id: int):
        if not await self.admin_exist(admin_id):
            await self.admins_data.insert_one({'_id': admin_id})
            return

    async def del_admin(self, admin_id: int):
        if await self.admin_exist(admin_id):
            await self.admins_data.delete_one({'_id': admin_id})
            return

    async def get_all_admins(self):
        users_docs = await self.admins_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in users_docs]
        return user_ids


    # BAN USER DATA
    async def ban_user_exist(self, user_id: int):
        found = await self.banned_user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_ban_user(self, user_id: int):
        if not await self.ban_user_exist(user_id):
            await self.banned_user_data.insert_one({'_id': user_id})
            return

    async def del_ban_user(self, user_id: int):
        if await self.ban_user_exist(user_id):
            await self.banned_user_data.delete_one({'_id': user_id})
            return

    async def get_ban_users(self):
        users_docs = await self.banned_user_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in users_docs]
        return user_ids



    # AUTO DELETE TIMER SETTINGS
    async def set_del_timer(self, value: int):        
        existing = await self.del_timer_data.find_one({})
        if existing:
            await self.del_timer_data.update_one({}, {'$set': {'value': value}})
        else:
            await self.del_timer_data.insert_one({'value': value})

    async def get_del_timer(self):
        data = await self.del_timer_data.find_one({})
        if data:
            return data.get('value', 600)
        return 0


    # CHANNEL MANAGEMENT
    async def channel_exist(self, channel_id: int):
        found = await self.fsub_data.find_one({'_id': channel_id})
        return bool(found)

    async def add_channel(self, channel_id: int):
        if not await self.channel_exist(channel_id):
            await self.fsub_data.insert_one({'_id': channel_id})
            return

    async def rem_channel(self, channel_id: int):
        if await self.channel_exist(channel_id):
            await self.fsub_data.delete_one({'_id': channel_id})
            return

    async def show_channels(self):
        channel_docs = await self.fsub_data.find().to_list(length=None)
        channel_ids = [doc['_id'] for doc in channel_docs]
        return channel_ids

    
# Get current mode of a channel
    async def get_channel_mode(self, channel_id: int):
        data = await self.fsub_data.find_one({'_id': channel_id})
        return data.get("mode", "off") if data else "off"

    # Set mode of a channel
    async def set_channel_mode(self, channel_id: int, mode: str):
        await self.fsub_data.update_one(
            {'_id': channel_id},
            {'$set': {'mode': mode}},
            upsert=True
        )

    # REQUEST FORCE-SUB MANAGEMENT

    # Add the user to the set of users for a   specific channel
    async def req_user(self, channel_id: int, user_id: int):
        try:
            await self.rqst_fsub_channel_data.update_one(
                {'_id': int(channel_id)},
                {'$addToSet': {'user_ids': int(user_id)}},
                upsert=True
            )
        except Exception as e:
            print(f"[DB ERROR] Failed to add user to request list: {e}")


    # Method 2: Remove a user from the channel set
    async def del_req_user(self, channel_id: int, user_id: int):
        # Remove the user from the set of users for the channel
        await self.rqst_fsub_channel_data.update_one(
            {'_id': channel_id}, 
            {'$pull': {'user_ids': user_id}}
        )

    # Check if the user exists in the set of the channel's users
    async def req_user_exist(self, channel_id: int, user_id: int):
        try:
            found = await self.rqst_fsub_channel_data.find_one({
                '_id': int(channel_id),
                'user_ids': int(user_id)
            })
            return bool(found)
        except Exception as e:
            print(f"[DB ERROR] Failed to check request list: {e}")
            return False  


    # Method to check if a channel exists using show_channels
    async def reqChannel_exist(self, channel_id: int):
    # Get the list of all channel IDs from the database
        channel_ids = await self.show_channels()
        #print(f"All channel IDs in the database: {channel_ids}")

    # Check if the given channel_id is in the list of channel IDs
        if channel_id in channel_ids:
            #print(f"Channel {channel_id} found in the database.")
            return True
        else:
            #print(f"Channel {channel_id} NOT found in the database.")
            return False


    # ANIME DATA MANAGEMENT
    async def get_anime(self, ani_id):
        """Get anime data by ID."""
        try:
            botset = await self.__animes.find_one({'_id': ani_id})
            return botset or {}
        except Exception as e:
            logging.error(f"Error in get_anime: {e}")
            return {}

    async def save_anime(self, ani_id, ep, qual, post_id=None):
        """Save anime episode data with quality and optional post ID."""
        try:
            quals = (await self.get_anime(ani_id)).get(ep, {qual: False for qual in Var.QUALS})
            quals[qual] = True
            await self.__animes.update_one(
                {'_id': ani_id},
                {'$set': {ep: quals}},
                upsert=True
            )
            if post_id:
                await self.__animes.update_one(
                    {'_id': ani_id},
                    {'$set': {"msg_id": post_id}},
                    upsert=True
                )
        except Exception as e:
            logging.error(f"Error in save_anime: {e}")

    async def reboot(self):
        """Drop the anime collection (use with caution)."""
        try:
            await self.__animes.drop()
        except Exception as e:
            logging.error(f"Error in reboot: {e}")

# Initialize the database
db = Database(Var.DB_URI, Var.DB_NAME)
