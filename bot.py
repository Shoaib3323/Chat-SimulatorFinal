#!/usr/bin/env python3
"""
Telegram Human-like Chat Simulator Bot with Multiple Script Support
"""

import asyncio
import os
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, Message, User
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

# ===== CONFIGURATION =====
API_ID = 26519036
API_HASH = "a5375914a2ab92449b6970bf6d26665d"
BOT_TOKEN = "8192774962:AAGYfF3nSUvUil3DT3qKfXpB7O6H5FGqNSo"
OWNER_ID = 6084292028

# ===== GLOBAL STATE =====
accounts: Dict[str, Tuple[str, TelegramClient]] = {}
message_history: List[Dict] = []
last_message_times: Dict[str, float] = {}
destination_group_identifier = None
destination_topic_id = None
destination_topic = "General chat"
min_interval = 15
max_interval = 60
simulation_running = False
simulation_task = None

# Script conversation system
conversation_scripts = {}
script_characters = {}
script_execution_order = []
current_script_position = 0
current_script_num = 0
script_completed = False

# Reply-only mode settings
force_reply_mode = True
min_reply_chance = 80
max_reply_chance = 100

def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID

async def send_message_as_user(client: TelegramClient, group_identifier: str, message: str, reply_to: int = None):
    """Send a message - with enhanced topic support"""
    try:
        entity = await client.get_entity(group_identifier)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        send_params = {
            'entity': entity,
            'message': message
        }
        
        if destination_topic_id:
            if reply_to:
                send_params['reply_to'] = reply_to
            else:
                send_params['reply_to'] = destination_topic_id
        elif reply_to:
            send_params['reply_to'] = reply_to
            
        result = await client.send_message(**send_params)
        return result
            
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        raise

def parse_script_execution_order():
    """Parse the script and create execution order"""
    global script_execution_order, current_script_position
    
    script_execution_order = []
    current_script = conversation_scripts.get(current_script_num, [])
    
    for line in current_script:
        if ':' in line:
            character_name, message = line.split(':', 1)
            character_name = character_name.strip()
            message = message.strip()
            script_execution_order.append((character_name, message))
    
    current_script_position = 0
    print(f"📜 Parsed script execution order: {len(script_execution_order)} messages")

def get_next_script_message():
    """Get the next message from script in proper order"""
    global current_script_position, current_script_num, script_completed
    
    if not script_execution_order or current_script_position >= len(script_execution_order):
        next_script_num = find_next_script(current_script_num)
        if next_script_num:
            current_script_num = next_script_num
            parse_script_execution_order()
            return get_next_script_message()
        else:
            script_completed = True
            return None, None
    
    character_name, message = script_execution_order[current_script_position]
    current_script_position += 1
    
    return character_name, message

def find_next_script(current_num: int) -> Optional[int]:
    """Find the next available script number"""
    available_scripts = sorted([num for num in conversation_scripts.keys() if conversation_scripts[num]])
    for script_num in available_scripts:
        if script_num > current_num:
            return script_num
    return None

def get_account_for_character(character_name):
    """Find which account is assigned to this character"""
    for phone, char_name in script_characters.items():
        if char_name == character_name:
            return phone
    return None

async def simulation_loop():
    """Main simulation loop following exact script order"""
    global simulation_running, script_completed
    
    print("🚀 Simulation started with exact script order")
    
    while simulation_running:
        try:
            if not accounts or not destination_group_identifier:
                await asyncio.sleep(3)
                continue
            
            if script_completed:
                print("✅ Script completed, stopping simulation")
                simulation_running = False
                break
            
            active_accounts = []
            for phone, (session_str, client) in accounts.items():
                try:
                    if await client.is_user_authorized():
                        active_accounts.append((phone, client))
                except:
                    continue
            
            if not active_accounts:
                print("❌ No authorized accounts")
                await asyncio.sleep(5)
                continue
            
            current_time = time.time()
            
            character_name, message_text = get_next_script_message()
            
            if script_completed:
                print("✅ Script completed during message processing, stopping simulation")
                simulation_running = False
                break
            
            if not character_name or not message_text:
                await asyncio.sleep(2)
                continue
            
            target_phone = get_account_for_character(character_name)
            if not target_phone:
                print(f"❌ No account assigned to character: {character_name}")
                print(f"❌ Stopping simulation due to character assignment error")
                simulation_running = False
                break
            
            target_client = None
            for phone, client in active_accounts:
                if phone == target_phone:
                    target_client = client
                    break
            
            if not target_client:
                print(f"❌ Account {target_phone} not authorized or not found")
                await asyncio.sleep(2)
                continue
            
            last_time = last_message_times.get(target_phone, 0)
            if current_time - last_time < min_interval:
                print(f"⏰ Waiting for {character_name}'s cooldown")
                await asyncio.sleep(2)
                continue
            
            print(f"🎯 Sending message as {character_name} ({target_phone})")
            
            reply_to_msg_id = None
            if message_history and force_reply_mode:
                reply_to_msg_id = message_history[-1]['message_id']
                print(f"💬 Replying to {message_history[-1]['sender_phone']}")
            
            try:
                result = await send_message_as_user(target_client, destination_group_identifier, message_text, reply_to_msg_id)
                
                if result:
                    last_message_times[target_phone] = current_time
                    
                    message_history.append({
                        'message_id': result.id,
                        'text': message_text,
                        'sender_phone': target_phone,
                        'timestamp': datetime.now()
                    })
                    
                    if len(message_history) > 25:
                        message_history.pop(0)
                    
                    print(f"✅ {character_name} ({target_phone}): {message_text}")
                
            except Exception as e:
                print(f"❌ Failed to send from {character_name} ({target_phone}): {e}")
                last_message_times[target_phone] = current_time - 30
            
            wait_time = random.uniform(min_interval, max_interval)
            await asyncio.sleep(wait_time)
                
        except Exception as e:
            print(f"❌ Simulation error: {e}")
            await asyncio.sleep(5)

# ===== BOT COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    help_text = (
        "Available commands:\n"
        "/add_account <phone>\n"
        "/remove_account <phone>\n"
        "/login <phone> <code>\n" 
        "/set_group <group> [topic_id]\n"
        "/set_script <script_number> <script_text>\n"
        "/clear_script [script_number]\n"
        "/assign_character <phone> <character>\n"
        "/set_interval <min> <max>\n"
        "/reply_mode <on/off>\n"
        "/start_sim\n"
        "/stop_sim\n"
        "/list_accounts\n"
        "/show_script\n"
        "/status\n"
        "/clear_topic\n"
        "/check_topics\n"
        "/test_topic\n"
    )
    await update.message.reply_text(help_text)

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or not context.args:
        await update.message.reply_text("❌ Usage: /add_account +1234567890")
        return
    
    phone = context.args[0].strip()
    if phone in accounts:
        await update.message.reply_text("❌ Account already exists")
        return
    
    session = StringSession()
    client = TelegramClient(session, API_ID, API_HASH)
    
    try:
        await client.connect()
        await client.send_code_request(phone)
        accounts[phone] = (session.save(), client)
        await update.message.reply_text(f"✅ Code sent to {phone}. Use /login {phone} <code>")
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        await update.message.reply_text(f"❌ Error: {e}")

async def remove_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or not context.args:
        await update.message.reply_text("❌ Usage: /remove_account +1234567890")
        return
    
    phone = context.args[0].strip()
    if phone not in accounts:
        await update.message.reply_text("❌ Account not found")
        return
    
    session_str, client = accounts[phone]
    try:
        await client.disconnect()
    except:
        pass
    
    del accounts[phone]
    if phone in script_characters:
        del script_characters[phone]
    
    await update.message.reply_text(f"✅ Account {phone} removed successfully")

async def login_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update) or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /login <phone> <code>")
        return
    
    phone = context.args[0].strip()
    code = context.args[1].strip()
    
    if phone not in accounts:
        await update.message.reply_text("❌ Account not found")
        return
    
    session_str, client = accounts[phone]
    
    try:
        await client.sign_in(phone=phone, code=code)
        
        if await client.is_user_authorized():
            new_session_str = client.session.save()
            accounts[phone] = (new_session_str, client)
            await update.message.reply_text(f"✅ Successfully logged in to {phone}")
        else:
            await update.message.reply_text("❌ Login failed - not authorized")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")

async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global destination_group_identifier, destination_topic_id
    if not is_owner(update) or not context.args:
        await update.message.reply_text("❌ Usage: /set_group <group_username_or_id> [topic_id]")
        return
    
    group_identifier = context.args[0].strip()
    topic_id = None
    
    if len(context.args) > 1:
        try:
            topic_id = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Topic ID must be a number")
            return
    
    destination_group_identifier = group_identifier
    destination_topic_id = topic_id
    
    success = False
    group_name = "Unknown Group"
    
    for phone, (session_str, client) in accounts.items():
        try:
            if await client.is_user_authorized():
                entity = await client.get_entity(destination_group_identifier)
                group_name = getattr(entity, 'title', 'Unknown Group')
                success = True
                break
        except Exception as e:
            continue
    
    if success:
        if destination_topic_id:
            await update.message.reply_text(f"✅ Group set to: {group_name} with topic ID: {destination_topic_id}")
        else:
            await update.message.reply_text(f"✅ Group set to: {group_name} (no topic)")
    else:
        await update.message.reply_text("❌ Could not connect to group.")

async def set_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set script for any number (1-10) - FIXED multi-line parsing"""
    global conversation_scripts, current_script_num, script_completed
    if not is_owner(update) or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /set_script <script_number(1-10)> <script_text>")
        return
    
    try:
        script_num = int(context.args[0])
        if script_num < 1 or script_num > 10:
            await update.message.reply_text("❌ Script number must be between 1 and 10")
            return
    except ValueError:
        await update.message.reply_text("❌ Script number must be a number between 1 and 10")
        return
    
    # Get the FULL message text including multi-line content
    script_text = update.message.text
    
    # Extract just the script part (remove the command)
    command_pattern = f"/set_script {script_num}"
    if script_text.startswith(command_pattern):
        script_text = script_text[len(command_pattern):].strip()
    
    print(f"🔧 Debug: Full script text received ({len(script_text)} chars)")
    print(f"Sample: {script_text[:200]}...")
    
    # Parse script lines - SIMPLE AND RELIABLE
    script_lines = []
    
    # Split by lines and look for character: message patterns
    lines = script_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for character: message pattern
        if ':' in line:
            # Find the first colon (character separator)
            colon_pos = line.find(':')
            character = line[:colon_pos].strip()
            message = line[colon_pos + 1:].strip()
            
            # Basic validation - character should be a single word
            if (character and message and 
                len(character) <= 20 and 
                ' ' not in character and
                character.isalpha()):
                script_lines.append(f"{character}: {message}")
                print(f"✅ Parsed: {character}: {message[:50]}...")
    
    # If we didn't find any valid lines, try alternative parsing
    if not script_lines:
        await update.message.reply_text("⚠️ Using alternative parsing...")
        # Try splitting by common character names
        characters = ['Halim', 'Kamal', 'Rajjaq']  # Add more character names as needed
        for char in characters:
            pattern = f"{char}:\\s*([^:]*)(?=\\s*(?:{'|'.join(characters)}):|$)"
            matches = re.findall(pattern, script_text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if match.strip():
                    script_lines.append(f"{char}: {match.strip()}")
    
    conversation_scripts[script_num] = script_lines
    script_completed = False
    
    if current_script_num == script_num or (current_script_num == 0 and script_num == 1):
        parse_script_execution_order()
    
    await update.message.reply_text(f"✅ Script {script_num} loaded with {len(script_lines)} lines")
    
    # Show preview
    if script_lines:
        preview = "\n".join([f"{i+1}. {line}" for i, line in enumerate(script_lines[:5])])
        if len(script_lines) > 5:
            preview += f"\n... and {len(script_lines) - 5} more lines"
        await update.message.reply_text(f"📋 Preview:\n{preview}")
        
        # Check character assignments
        characters_in_script = set()
        for line in script_lines:
            if ':' in line:
                character = line.split(':', 1)[0].strip()
                characters_in_script.add(character)
        
        assigned_characters = set(script_characters.values())
        missing_assignments = characters_in_script - assigned_characters
        
        if missing_assignments:
            await update.message.reply_text(f"⚠️ Missing character assignments: {', '.join(missing_assignments)}")
            await update.message.reply_text("❌ Simulation will stop if these characters are encountered!")

async def clear_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global conversation_scripts, current_script_num, current_script_position, script_completed
    
    if not is_owner(update):
        return
    
    if not context.args:
        conversation_scripts.clear()
        current_script_num = 0
        current_script_position = 0
        script_completed = False
        await update.message.reply_text("✅ All scripts cleared")
        return
    
    try:
        script_num = int(context.args[0])
        if script_num in conversation_scripts:
            del conversation_scripts[script_num]
            
            if current_script_num == script_num:
                current_script_num = 0
                current_script_position = 0
                script_completed = False
            
            await update.message.reply_text(f"✅ Script {script_num} cleared")
        else:
            await update.message.reply_text(f"❌ Script {script_num} not found")
    except ValueError:
        await update.message.reply_text("❌ Script number must be a number between 1 and 10")

async def assign_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global script_characters
    if not is_owner(update) or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /assign_character <phone> <character_name>")
        return
    
    phone = context.args[0].strip()
    character = " ".join(context.args[1:]).strip()
    
    if phone not in accounts:
        await update.message.reply_text("❌ Account not found")
        return
    
    script_characters[phone] = character
    await update.message.reply_text(f"✅ Account {phone} assigned to character: {character}")

async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global min_interval, max_interval
    if not is_owner(update) or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /set_interval <min> <max>")
        return
    
    try:
        min_val = max(5, float(context.args[0]))
        max_val = max(min_val + 5, float(context.args[1]))
        min_interval, max_interval = min_val, max_val
        await update.message.reply_text(f"✅ Interval: {min_interval}-{max_interval}s")
    except:
        await update.message.reply_text("❌ Invalid numbers")

async def reply_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global force_reply_mode
    if not is_owner(update) or not context.args:
        await update.message.reply_text("❌ Usage: /reply_mode <on/off>")
        return
    
    mode = context.args[0].lower()
    if mode in ['on', 'yes', 'true', '1']:
        force_reply_mode = True
        await update.message.reply_text("✅ Reply mode: ON")
    elif mode in ['off', 'no', 'false', '0']:
        force_reply_mode = False
        await update.message.reply_text("✅ Reply mode: OFF")
    else:
        await update.message.reply_text("❌ Use: /reply_mode <on/off>")

async def show_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    
    if not conversation_scripts:
        await update.message.reply_text("❌ No scripts loaded")
        return
    
    response = "📜 Loaded Scripts:\n\n"
    for script_num in sorted(conversation_scripts.keys()):
        script = conversation_scripts[script_num]
        if script:
            script_preview = "\n".join(script[:3])
            if len(script) > 3:
                script_preview += "\n..."
            response += f"Script {script_num} ({len(script)} lines):\n{script_preview}\n\n"
    
    character_assignments = "\n".join([f"{phone} -> {char}" for phone, char in script_characters.items()])
    
    response += f"🎭 Character Assignments:\n{character_assignments if character_assignments else 'None'}\n\n"
    response += f"📖 Current Script: {current_script_num}\n"
    response += f"📝 Script Status: {'Completed' if script_completed else 'In progress' if current_script_num > 0 else 'Not started'}"
    
    await update.message.reply_text(response)

async def start_sim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global simulation_running, simulation_task, current_script_num, script_completed
    if not is_owner(update):
        return
    
    if simulation_running:
        await update.message.reply_text("❌ Already running")
        return
    
    if not accounts or not destination_group_identifier:
        await update.message.reply_text("❌ Add accounts and set group first")
        return
    
    authorized_count = 0
    for phone, (session_str, client) in accounts.items():
        try:
            if await client.is_user_authorized():
                authorized_count += 1
        except:
            pass
    
    if authorized_count == 0:
        await update.message.reply_text("❌ No authorized accounts")
        return
    
    current_script_num = 0
    script_completed = False
    available_scripts = sorted([num for num in conversation_scripts.keys() if conversation_scripts[num]])
    if available_scripts:
        current_script_num = available_scripts[0]
        parse_script_execution_order()
    
    simulation_running = True
    simulation_task = asyncio.create_task(simulation_loop())
    
    await update.message.reply_text(f"✅ Simulation started with {authorized_count} accounts!")

async def stop_sim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global simulation_running, simulation_task
    if not is_owner(update):
        return
    
    simulation_running = False
    if simulation_task:
        simulation_task.cancel()
    await update.message.reply_text("✅ Simulation stopped")

async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    
    if not accounts:
        await update.message.reply_text("❌ No accounts")
        return
    
    account_list = []
    for phone, (session_str, client) in accounts.items():
        try:
            status = "✅ Authorized" if await client.is_user_authorized() else "❌ Not authorized"
            character = script_characters.get(phone, "Not assigned")
        except:
            status = "❌ Error"
            character = "Error"
        account_list.append(f"• {phone} - {status} - Character: {character}")
    
    response = "📱 Accounts:\n" + "\n".join(account_list)
    await update.message.reply_text(response)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    
    authorized_count = 0
    for phone, (session_str, client) in accounts.items():
        try:
            if await client.is_user_authorized():
                authorized_count += 1
        except:
            pass
    
    script_counts = {num: len(script) for num, script in conversation_scripts.items() if script}
    script_info = ", ".join([f"Script{num}: {count} lines" for num, count in script_counts.items()])
    
    status_text = (
        f"Accounts: {len(accounts)} (Authorized: {authorized_count})\n"
        f"Group: {destination_group_identifier or 'Not set'}\n"
        f"Scripts: {script_info or 'No scripts'}\n"
        f"Current Script: {current_script_num}\n"
        f"Characters: {len(script_characters)} assigned\n"
        f"Running: {simulation_running}"
    )
    await update.message.reply_text(status_text)

# ===== MAIN =====
async def main():
    print("🤖 Starting Telegram Chat Simulator Bot...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_account", add_account))
    application.add_handler(CommandHandler("remove_account", remove_account))
    application.add_handler(CommandHandler("login", login_account))
    application.add_handler(CommandHandler("set_group", set_group))
    application.add_handler(CommandHandler("set_script", set_script))
    application.add_handler(CommandHandler("clear_script", clear_script))
    application.add_handler(CommandHandler("assign_character", assign_character))
    application.add_handler(CommandHandler("set_interval", set_interval))
    application.add_handler(CommandHandler("reply_mode", reply_mode))
    application.add_handler(CommandHandler("show_script", show_script))
    application.add_handler(CommandHandler("start_sim", start_sim))
    application.add_handler(CommandHandler("stop_sim", stop_sim))
    application.add_handler(CommandHandler("list_accounts", list_accounts))
    application.add_handler(CommandHandler("status", status))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot is running. Use /start to see commands.")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n🛑 Stopping bot...")
        simulation_running = False 
        for phone, (_, client) in accounts.items():
            try:
                await client.disconnect()
            except:
                pass
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
