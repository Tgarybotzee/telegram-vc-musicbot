import io
import os
import zipfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters
)
from config import ADMIN_ID
from database import (
    register_user, get_user_profile, save_telethon_session, 
    get_all_accounts, assign_account_to_user, get_user_accounts, 
    get_account_session, get_all_sessions_export, get_all_account_sessions
)
from telethon_client import auth_manager
from telethon.sessions import StringSession, SQLiteSession

# Conversation States
ASK_PHONE, ASK_OTP, ASK_2FA = range(3)
ASK_OTP_PHONE = 10
ASK_DOWNLOAD_PHONE = 11

def get_main_menu_keyboard(is_admin: bool):
    buttons = [
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("📜 My Accounts", callback_data="menu_my_accounts")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(buttons)

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Account", callback_data="admin_add_acc")],
        [InlineKeyboardButton("📋 View Accounts", callback_data="admin_list_acc")],
        [InlineKeyboardButton("🔑 Fetch Login OTP", callback_data="admin_get_otp")],
        [InlineKeyboardButton("⬇️ Download .session File", callback_data="admin_dl_session")],
        [InlineKeyboardButton("📥 Export All (Text)", callback_data="admin_export_sessions")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    await register_user(user.id, user.username, 'admin' if is_admin else 'user')
    
    welcome_text = f"Welcome, {user.first_name}!\n\nThis is the internal inventory management system."
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(is_admin))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    is_admin = (user_id == ADMIN_ID)

    if query.data == "menu_main":
        await query.edit_message_text("Main Menu:", reply_markup=get_main_menu_keyboard(is_admin))
        
    elif query.data == "menu_profile":
        profile = await get_user_profile(user_id)
        text = (
            "👤 **User Profile**\n"
            f"ID: `{profile['user_id']}`\n"
            f"Role: {profile['role'].title()}\n"
            f"Credits: **{profile['credits']}**"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]]))

    elif query.data == "menu_my_accounts":
        accounts = await get_user_accounts(user_id)
        if not accounts:
            text = "You do not have any assigned accounts."
        else:
            text = "📜 **Your Assigned Accounts:**\n\n"
            for acc in accounts:
                text += f"📱 `{acc['phone']}` | Status: {acc['status'].title()}\n"
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]]))

    elif query.data == "menu_admin" and is_admin:
        await query.edit_message_text("⚙️ **Admin Control Panel**\nSelect an action:", parse_mode="Markdown", reply_markup=get_admin_keyboard())

    elif query.data == "admin_list_acc" and is_admin:
        accounts = await get_all_accounts()
        if not accounts:
            text = "No accounts in inventory."
        else:
            text = "📋 **Account Inventory:**\n\n"
            for acc in accounts:
                assigned = f"Assigned to {acc['assigned_to']}" if acc['assigned_to'] else "Available"
                text += f"📱 `{acc['phone']}` | {acc['status'].title()} | {assigned}\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_admin")]]))

    elif query.data == "admin_export_sessions" and is_admin:
        await query.edit_message_text("Exporting sessions... please wait.")
        data = await get_all_sessions_export()
        
        if data == "No accounts found.":
            await query.edit_message_text(data, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_admin")]]))
            return

        file_data = io.BytesIO(data.encode('utf-8'))
        file_data.name = "sessions_export.txt"
        
        await context.bot.send_document(
            chat_id=user_id,
            document=file_data,
            caption="📥 **Sessions Export**\nFormat: `Phone,SessionString`",
            parse_mode="Markdown"
        )
        await query.edit_message_text("✅ Sessions exported successfully.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_admin")]]))


# --- Telethon ADD ACCOUNT Handlers ---

async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter the phone number in international format:\nType /cancel to abort.")
    return ASK_PHONE

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['auth_phone'] = phone
    msg = await update.message.reply_text(f"Requesting code for {phone}...")
    success, response = await auth_manager.start_auth(update.effective_user.id, phone)
    
    if success:
        await msg.edit_text(f"{response}\nType /cancel to abort.")
        return ASK_OTP
    else:
        await msg.edit_text(f"Error: {response}")
        return ConversationHandler.END

async def handle_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    msg = await update.message.reply_text("Verifying OTP...")
    status, result = await auth_manager.submit_otp(update.effective_user.id, code)
    
    if status == "success":
        await save_telethon_session(context.user_data['auth_phone'], result)
        await msg.edit_text("✅ Account successfully added and session stored securely!")
        return ConversationHandler.END
    elif status == "2fa_required":
        await msg.edit_text("🔒 2FA is enabled. Please enter the cloud password:\nType /cancel to abort.")
        return ASK_2FA
    else:
        await msg.edit_text(f"❌ Failed: {result}")
        return ConversationHandler.END

async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    await update.message.delete()
    msg = await update.message.reply_text("Verifying 2FA...")
    success, result = await auth_manager.submit_2fa(update.effective_user.id, password)
    
    if success:
        await save_telethon_session(context.user_data['auth_phone'], result)
        await msg.edit_text("✅ Account successfully added and session stored securely!")
    else:
        await msg.edit_text(f"❌ Failed: {result}")
    return ConversationHandler.END

# --- Telethon FETCH OTP Handlers ---

async def fetch_otp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter the phone number to fetch the Telegram OTP for:\nType /cancel to abort.")
    return ASK_OTP_PHONE

async def handle_fetch_otp_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    session_string = await get_account_session(phone)
    
    if not session_string:
        await update.message.reply_text("❌ Account not found in database.\nType /cancel to abort.")
        return ASK_OTP_PHONE
        
    msg = await update.message.reply_text(f"Connecting to {phone} to fetch latest code...")
    success, result = await auth_manager.get_latest_telegram_code(session_string)
    
    if success:
        await msg.edit_text(f"✅ **Latest Message from Telegram:**\n\n`{result}`", parse_mode="Markdown")
    else:
        await msg.edit_text(f"❌ Failed: {result}")
        
    return ConversationHandler.END

# --- DOWNLOAD .SESSION FILE Handlers ---

async def download_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Enter a phone number to download its .session file.\n\n"
        "**Or type /all** to download a ZIP containing every session file.\n\n"
        "Type /cancel to abort.",
        parse_mode="Markdown"
    )
    return ASK_DOWNLOAD_PHONE

async def handle_download_session_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    session_string = await get_account_session(phone)
    
    if not session_string:
        await update.message.reply_text("❌ Account not found in database.\nType /cancel to abort.")
        return ASK_DOWNLOAD_PHONE
        
    msg = await update.message.reply_text("Generating .session file...")
    
    try:
        safe_phone = phone.replace('+', '')
        file_path = f"{safe_phone}.session"
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        ss = StringSession(session_string)
        sq = SQLiteSession(file_path)
        sq.set_dc(ss.dc_id, ss.server_address, ss.port)
        sq.auth_key = ss.auth_key
        sq.close()
        
        with open(file_path, 'rb') as session_file:
            await update.message.reply_document(
                document=session_file,
                filename=f"{phone}.session",
                caption=f"✅ SQLite Session file for {phone}"
            )
            
        os.remove(file_path)
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"❌ Failed to generate file: {str(e)}")
        
    return ConversationHandler.END

async def handle_download_all_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📦 Packaging all .session files into a ZIP... Please wait.")
    accounts = await get_all_account_sessions()
    
    if not accounts:
        await msg.edit_text("❌ No accounts found in the database.")
        return ConversationHandler.END
        
    zip_filename = "all_sessions.zip"
    try:
        # Create a ZIP file and add all the sessions to it
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for phone, session_string in accounts:
                safe_phone = phone.replace('+', '')
                file_path = f"{safe_phone}.session"
                
                # Convert string to SQLite
                ss = StringSession(session_string)
                sq = SQLiteSession(file_path)
                sq.set_dc(ss.dc_id, ss.server_address, ss.port)
                sq.auth_key = ss.auth_key
                sq.close()
                
                # Add to ZIP
                zipf.write(file_path, arcname=f"{safe_phone}.session")
                
                # Clean up the individual temp file
                os.remove(file_path)
                
        # Send the ZIP file
        with open(zip_filename, 'rb') as zip_file:
            await update.message.reply_document(
                document=zip_file,
                filename="telegram_all_sessions.zip",
                caption=f"✅ Successfully packaged {len(accounts)} session files."
            )
            
        # Clean up the ZIP file
        os.remove(zip_filename)
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"❌ Failed to generate ZIP file: {str(e)}")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
            
    return ConversationHandler.END

async def cancel_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# Handlers Registration
auth_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_account_start, pattern="^admin_add_acc$")],
    states={
        ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
        ASK_OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp)],
        ASK_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_2fa)]
    },
    fallbacks=[CommandHandler("cancel", cancel_auth)],
    per_message=False
)

fetch_otp_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(fetch_otp_start, pattern="^admin_get_otp$")],
    states={
        ASK_OTP_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fetch_otp_phone)]
    },
    fallbacks=[CommandHandler("cancel", cancel_auth)],
    per_message=False
)

download_session_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(download_session_start, pattern="^admin_dl_session$")],
    states={
        ASK_DOWNLOAD_PHONE: [
            CommandHandler("all", handle_download_all_sessions),  # Listens for /all
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_download_session_phone)
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_auth)],
    per_message=False
)