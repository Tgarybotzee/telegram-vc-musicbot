from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from config import API_ID, API_HASH, logger

class TelethonAuthManager:
    def __init__(self):
        self.pending_clients = {} 

    async def start_auth(self, admin_id: int, phone: str) -> tuple[bool, str]:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        try:
            send_code_result = await client.send_code_request(phone)
            self.pending_clients[admin_id] = {
                'client': client,
                'phone': phone,
                'phone_code_hash': send_code_result.phone_code_hash
            }
            return True, "Code sent successfully. Please enter the OTP."
        except Exception as e:
            logger.error(f"Auth error for {phone}: {str(e)}")
            await client.disconnect()
            return False, f"Failed to send code: {str(e)}"

    async def submit_otp(self, admin_id: int, code: str) -> tuple[str, str]:
        if admin_id not in self.pending_clients:
            return "error", "No pending login found. Start over."
        
        auth_data = self.pending_clients[admin_id]
        client: TelegramClient = auth_data['client']
        
        try:
            await client.sign_in(
                phone=auth_data['phone'],
                code=code,
                phone_code_hash=auth_data['phone_code_hash']
            )
            session_string = client.session.save()
            await client.disconnect()
            del self.pending_clients[admin_id]
            return "success", session_string
        except SessionPasswordNeededError:
            return "2fa_required", "2FA enabled. Please enter your password."
        except PhoneCodeInvalidError:
            return "error", "Invalid OTP code."
        except Exception as e:
            await client.disconnect()
            del self.pending_clients[admin_id]
            return "error", str(e)

    async def submit_2fa(self, admin_id: int, password: str) -> tuple[bool, str]:
        if admin_id not in self.pending_clients:
            return False, "No pending login found."
        
        client: TelegramClient = self.pending_clients[admin_id]['client']
        try:
            await client.sign_in(password=password)
            session_string = client.session.save()
            await client.disconnect()
            del self.pending_clients[admin_id]
            return True, session_string
        except Exception as e:
            await client.disconnect()
            del self.pending_clients[admin_id]
            return False, str(e)

    async def get_latest_telegram_code(self, session_string: str) -> tuple[bool, str]:
        """Connects using the stored session and fetches the latest OTP from Telegram (777000)."""
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Session is dead or unauthorized."
            
            # 777000 is the official Telegram service notifications account
            messages = await client.get_messages(777000, limit=1)
            if not messages:
                await client.disconnect()
                return False, "No messages found from Telegram."
            
            msg_text = messages[0].message
            await client.disconnect()
            return True, msg_text
        except Exception as e:
            await client.disconnect()
            return False, f"Error fetching OTP: {str(e)}"

auth_manager = TelethonAuthManager()