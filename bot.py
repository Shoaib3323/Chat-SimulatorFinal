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
API_ID = 20583673
API_HASH = "4874dc139573317c2eebdb7b5936e72c"
BOT_TOKEN = "8406407573:AAG_EYa5dVTELpV6SWLYNkss95uf9YMxxBY"
OWNER_ID = 5876736850

# ===== GLOBAL STATE =====
accounts: Dict[str, Tuple[str, TelegramClient]] = {}
message_history: List[Dict] = []
last_message_times: Dict[str, float] = {}
destination_group_identifier = None
destination_topic_id = None  # New: Store topic ID
destination_topic = "General chat"
min_interval = 15
max_interval = 60
simulation_running = False
simulation_task = None

# Script conversation system
conversation_scripts = {}  # Changed to dict: {script_num: script_lines}
current_script_index = 0
current_script_num = 0  # 0 = no script
script_characters = {}  # {phone: character_name}
script_completed = False  # Track if script has been completed

# Reply-only mode settings
force_reply_mode = True  # Always reply to previous messages
min_reply_chance = 80    # Minimum 80% chance to reply
max_reply_chance = 100   # Maximum 100% chance to reply

def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID

async def send_message_as_user(client: TelegramClient, group_identifier: str, message: str, reply_to: int = None):
    """Send a message - with enhanced topic support"""
    try:
        entity = await client.get_entity(group_identifier)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # Prepare send message parameters
        send_params = {
            'entity': entity,
            'message': message
        }
        
        # Handle topic replies
        if destination_topic_id:
            # For topics, we need to use the topic ID as reply_to
            if reply_to:
                # If replying to a specific message within the topic
                send_params['reply_to'] = reply_to
            else:
                # If sending a new message to the topic
                send_params['reply_to'] = destination_topic_id
        elif reply_to:
            # Regular reply (no topic)
            send_params['reply_to'] = reply_to
            
        result = await client.send_message(**send_params)
        return result
            
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        
        # Specific error handling for topics
        if "TOPIC_CLOSED" in str(e) or "TOPIC_DELETED" in str(e):
            print("❌ Topic is closed or deleted. Try with a different topic ID.")
        elif "CHAT_WRITE_FORBIDDEN" in str(e):
            print("❌ No permission to write in this chat/topic.")
        elif "PEER_ID_INVALID" in str(e):
            print("❌ Invalid group or topic ID.")
            
        raise

def get_next_script_message(phone: str):
    """Get the next message from script for this character"""
    global current_script_index, current_script_num, script_completed
    
    if not conversation_scripts or current_script_num == 0:
        return None
        
    character_name = script_characters.get(phone)
    if not character_name:
        return None
        
    # Get current script
    current_script = conversation_scripts.get(current_script_num, [])
    if not current_script:
        return None
    
    # Find next message for this character in current script
    for i in range(current_script_index, len(current_script)):
        line = current_script[i]
        if line.startswith(f"{character_name}:"):
            current_script_index = i + 1
            # If we reached the end of current script, try to move to next script
            if current_script_index >= len(current_script):
                # Find next available script
                next_script_num = find_next_script(current_script_num)
                if next_script_num:
                    current_script_num = next_script_num
                    current_script_index = 0
                    script_completed = False
                    print(f"📜 Moving to script {current_script_num}")
                else:
                    # No more scripts, mark as completed and stop simulation
                    script_completed = True
                    print("📜 All scripts completed, stopping simulation")
                    return None
            return line.split(":", 1)[1].strip()
    
    # If we didn't find the character in the rest of current script,
    # try from the beginning of current script
    for i in range(0, current_script_index):
        line = current_script[i]
        if line.startswith(f"{character_name}:"):
            current_script_index = i + 1
            return line.split(":", 1)[1].strip()
    
    # Character not found in current script, try next script if available
    next_script_num = find_next_script(current_script_num)
    if next_script_num:
        current_script_num = next_script_num
        current_script_index = 0
        script_completed = False
        print(f"📜 Moving to script {current_script_num}")
        return get_next_script_message(phone)
    
    # No more scripts and character not found
    script_completed = True
    return None

def find_next_script(current_num: int) -> Optional[int]:
    """Find the next available script number"""
    available_scripts = sorted([num for num in conversation_scripts.keys() if conversation_scripts[num]])
    for script_num in available_scripts:
        if script_num > current_num:
            return script_num
    return None

def get_contextual_reply(phone: str, last_message: Dict):
    """Generate a contextual reply based on the last message"""
    character_name = script_characters.get(phone, "User")
    last_text = last_message['text'].lower()
    last_sender = last_message['sender_phone']
    
    # Character-specific response styles
    character_styles = {
        "Alice": ["I agree with that", "That makes sense", "Good point!", "I think so too"],
        "Bob": ["Interesting perspective", "I see what you mean", "That's a good way to look at it"],
        "Charlie": ["I have a different thought", "What if we consider", "Another angle could be"],
        "User": ["That's interesting", "I understand", "Thanks for sharing", "Good point"]
    }
    
    # Response based on message content
    if any(word in last_text for word in ['?', 'what', 'how', 'why', 'when', 'where']):
        responses = [
            "That's a good question",
            "I've been wondering about that too",
            "Let me think about that",
            "Interesting point you raised"
        ]
    elif any(word in last_text for word in ['think', 'believe', 'opinion', 'feel']):
        responses = [
            "I agree with that perspective",
            "That's a different way to look at it",
            "I see what you mean",
            "That makes sense"
        ]
    elif any(word in last_text for word in ['hi', 'hello', 'hey', 'greetings']):
        responses = [
            "Hey there!",
            "Hello! How's it going?",
            "Hi! Good to see you",
            "Hey! What's up?"
        ]
    else:
        responses = character_styles.get(character_name, character_styles["User"])
    
    return random.choice(responses)

def should_reply(phone: str):
    """Determine if this account should reply based on number of accounts"""
    if not message_history:
        return False, None
    
    # If script is completed, don't send any more messages
    if script_completed:
        return False, None
    
    # Get number of active accounts
    active_accounts = [acc for acc in accounts.keys() if acc in [msg['sender_phone'] for msg in message_history[-10:]]]
    num_active = len(active_accounts) if active_accounts else len(accounts)
    
    # Calculate reply chance based on number of accounts
    # More accounts = higher chance to reply to keep conversation flowing
    base_chance = min(max_reply_chance, max(min_reply_chance, 60 + (num_active * 10)))
    reply_chance = random.randint(min_reply_chance, max_reply_chance)
    
    # Always reply if we have a script and it's our turn (and script is not completed)
    if current_script_num > 0 and script_characters.get(phone) and not script_completed:
        return True, message_history[-1] if message_history else None
    
    # Force reply mode or high chance
    if force_reply_mode or reply_chance <= base_chance:
        if message_history:
            # Don't reply to ourselves
            other_messages = [msg for msg in message_history if msg['sender_phone'] != phone]
            if other_messages:
                return True, other_messages[-1]
    
    return False, None

async def simulation_loop():
    """Main simulation loop with forced reply mode"""
    global simulation_running, script_completed
    
    print("🚀 Simulation started with forced reply mode")
    print(f"📊 Force reply mode: {'ON' if force_reply_mode else 'OFF'}")
    if destination_topic_id:
        print(f"💬 Topic ID: {destination_topic_id}")
    
    while simulation_running:
        try:
            if not accounts or not destination_group_identifier:
                await asyncio.sleep(3)
                continue
            
            # Check if script is completed - stop simulation if true
            if script_completed:
                print("✅ Script completed, stopping simulation")
                simulation_running = False
                break
            
            # Get all authorized accounts
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
            
            # Process each account
            for phone, client in active_accounts:
                if not simulation_running:
                    break
                    
                # Check timing
                last_time = last_message_times.get(phone, 0)
                if current_time - last_time < min_interval:
                    continue
                
                print(f"🎯 Processing account: {phone}")
                
                # Decide if we should reply and to what
                should_reply_flag, reply_to_message = should_reply(phone)
                message = None
                reply_to_msg_id = None
                
                if should_reply_flag and reply_to_message:
                    # Get message for reply
                    if current_script_num > 0 and not script_completed:
                        message = get_next_script_message(phone)
                    
                    # If script is completed after getting message, stop
                    if script_completed:
                        print("✅ Script completed during message processing, stopping simulation")
                        simulation_running = False
                        break
                    
                    if not message:
                        message = get_contextual_reply(phone, reply_to_message)
                    
                    reply_to_msg_id = reply_to_message['message_id']
                    print(f"💬 Replying to {reply_to_message['sender_phone']}")
                else:
                    # Only send new message if we have no history or very low chance
                    if not message_history or random.random() < 0.1:
                        if current_script_num > 0 and not script_completed:
                            message = get_next_script_message(phone)
                            
                            # If script is completed after getting message, stop
                            if script_completed:
                                print("✅ Script completed during message processing, stopping simulation")
                                simulation_running = False
                                break
                        
                        if not message:
                            character_name = script_characters.get(phone, "User")
                            greetings = ["Hello everyone!", "Hey there!", "Hi all!", "Good to be here!"]
                            message = random.choice(greetings)
                
                if not message:
                    continue
                
                # Send message
                try:
                    result = await send_message_as_user(client, destination_group_identifier, message, reply_to_msg_id)
                    
                    if result:
                        last_message_times[phone] = current_time
                        
                        message_history.append({
                            'message_id': result.id,
                            'text': message,
                            'sender_phone': phone,
                            'timestamp': datetime.now()
                        })
                        
                        if len(message_history) > 25:
                            message_history.pop(0)
                        
                        character = script_characters.get(phone, "User")
                        if reply_to_msg_id:
                            print(f"✅ {character} ({phone}) → {message}")
                        else:
                            print(f"✅ {character} ({phone}): {message}")
                    
                except Exception as e:
                    print(f"❌ Failed to send from {phone}: {e}")
                    last_message_times[phone] = current_time - 30
                
                # Wait based on number of accounts
                wait_time = random.uniform(min_interval, max_interval) / max(1, len(active_accounts))
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
    """Remove an account from the bot"""
    if not is_owner(update) or not context.args:
        await update.message.reply_text("❌ Usage: /remove_account +1234567890")
        return
    
    phone = context.args[0].strip()
    if phone not in accounts:
        await update.message.reply_text("❌ Account not found")
        return
    
    # Disconnect client if connected
    session_str, client = accounts[phone]
    try:
        await client.disconnect()
    except:
        pass
    
    # Remove from accounts and character assignments
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
    
    # Check if topic ID is provided
    if len(context.args) > 1:
        try:
            topic_id = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Topic ID must be a number")
            return
    
    destination_group_identifier = group_identifier
    destination_topic_id = topic_id
    
    # Test the group connection and check topic support
    success = False
    topic_supported = False
    group_name = "Unknown Group"
    
    for phone, (session_str, client) in accounts.items():
        try:
            if await client.is_user_authorized():
                entity = await client.get_entity(destination_group_identifier)
                group_name = getattr(entity, 'title', 'Unknown Group')
                
                # Check if this is a group that supports topics
                if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                    if entity.megagroup or getattr(entity, 'forum', False):
                        topic_supported = True
                        print(f"✅ Group {group_name} supports topics")
                    else:
                        print(f"⚠️ Group {group_name} may not support topics (not a supergroup/forum)")
                
                # Test sending a message (without actually sending)
                if topic_id:
                    # For topics, we need to verify the topic exists
                    try:
                        # Try to get forum topics
                        if hasattr(entity, 'id'):
                            result = await client(functions.channels.GetForumTopicsRequest(
                                channel=entity,
                                offset_date=None,
                                offset_id=0,
                                offset_topic=0,
                                limit=100
                            ))
                            topic_exists = any(topic.id == topic_id for topic in result.topics)
                            if not topic_exists:
                                await update.message.reply_text(f"❌ Topic ID {topic_id} not found in group {group_name}")
                                return
                    except Exception as e:
                        print(f"⚠️ Could not verify topic existence: {e}")
                        # Continue anyway, as some groups might not allow topic listing
                
                success = True
                break
                
        except Exception as e:
            print(f"❌ Error testing group connection for {phone}: {e}")
            continue
    
    if success:
        if destination_topic_id:
            if topic_supported:
                await update.message.reply_text(f"✅ Group set to: {group_name} with topic ID: {destination_topic_id}")
            else:
                await update.message.reply_text(f"⚠️ Group set to: {group_name} with topic ID: {destination_topic_id} but topic support is limited")
        else:
            await update.message.reply_text(f"✅ Group set to: {group_name} (no topic)")
    else:
        await update.message.reply_text("❌ Could not connect to group. Make sure accounts have access and the group identifier is correct.")

async def clear_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the topic setting"""
    global destination_topic_id
    destination_topic_id = None
    await update.message.reply_text("✅ Topic cleared. Messages will be sent to general chat.")

async def check_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check available topics in the current group"""
    if not is_owner(update):
        return
    
    if not destination_group_identifier:
        await update.message.reply_text("❌ No group set. Use /set_group first.")
        return
    
    try:
        for phone, (session_str, client) in accounts.items():
            if await client.is_user_authorized():
                entity = await client.get_entity(destination_group_identifier)
                
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    try:
                        result = await client(functions.channels.GetForumTopicsRequest(
                            channel=entity,
                            offset_date=None,
                            offset_id=0,
                            offset_topic=0,
                            limit=50
                        ))
                        
                        if result.topics:
                            topic_list = []
                            for topic in result.topics:
                                status = "✅ OPEN" if not topic.closed else "❌ CLOSED"
                                topic_list.append(f"{topic.id}: {getattr(topic, 'title', 'Unknown')} {status}")
                            
                            response = f"📋 Topics in {getattr(entity, 'title', 'Group')}:\n" + "\n".join(topic_list)
                            await update.message.reply_text(response)
                        else:
                            await update.message.reply_text("❌ No topics found or topics not supported in this group.")
                        
                    except Exception as e:
                        await update.message.reply_text(f"❌ Error fetching topics: {e}")
                else:
                    await update.message.reply_text("❌ This group doesn't support topics (not a supergroup/forum).")
                break
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def test_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test sending a message to the current topic"""
    if not is_owner(update):
        return
    
    if not destination_group_identifier or not destination_topic_id:
        await update.message.reply_text("❌ Group and topic must be set first.")
        return
    
    try:
        for phone, (session_str, client) in accounts.items():
            if await client.is_user_authorized():
                entity = await client.get_entity(destination_group_identifier)
                
                test_message = "🧪 Test message to verify topic functionality"
                result = await client.send_message(
                    entity=entity,
                    message=test_message,
                    reply_to=destination_topic_id
                )
                
                if result:
                    await update.message.reply_text(f"✅ Test message sent successfully to topic {destination_topic_id}")
                else:
                    await update.message.reply_text("❌ Failed to send test message")
                break
    except Exception as e:
        await update.message.reply_text(f"❌ Test failed: {e}")

async def set_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set script for any number (1-10)"""
    global conversation_scripts, current_script_index, current_script_num, script_completed
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
    
    script_text = " ".join(context.args[1:])
    
    # Parse script lines
    script_lines = []
    lines = script_text.split('\n') if '\n' in script_text else script_text.split('.')
    for line in lines:
        line = line.strip()
        if line and ':' in line:
            script_lines.append(line)
    
    conversation_scripts[script_num] = script_lines
    script_completed = False  # Reset completion status when new script is set
    
    await update.message.reply_text(f"✅ Script {script_num} loaded with {len(script_lines)} lines")

async def clear_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear specific script or all scripts"""
    global conversation_scripts, current_script_num, current_script_index, script_completed
    
    if not is_owner(update):
        return
    
    if not context.args:
        # Clear all scripts
        conversation_scripts.clear()
        current_script_num = 0
        current_script_index = 0
        script_completed = False
        await update.message.reply_text("✅ All scripts cleared")
        return
    
    try:
        script_num = int(context.args[0])
        if script_num in conversation_scripts:
            del conversation_scripts[script_num]
            
            # If we're currently using this script, reset to no script
            if current_script_num == script_num:
                current_script_num = 0
                current_script_index = 0
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
        await update.message.reply_text("✅ Reply mode: ON - Accounts will always reply to each other")
    elif mode in ['off', 'no', 'false', '0']:
        force_reply_mode = False
        await update.message.reply_text("✅ Reply mode: OFF - Accounts may send standalone messages")
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
    response += f"🔗 Reply Mode: {'ON' if force_reply_mode else 'OFF'}\n"
    response += f"📖 Current Script: {current_script_num} (0 = no script)\n"
    response += f"📝 Script Status: {'Completed' if script_completed else 'In progress' if current_script_num > 0 else 'Not started'}"
    
    if destination_topic_id:
        response += f"\n💬 Active Topic ID: {destination_topic_id}"
    
    await update.message.reply_text(response)

async def start_sim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global simulation_running, simulation_task, current_script_num, current_script_index, script_completed
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
    
    # Find first available script
    current_script_index = 0
    current_script_num = 0
    script_completed = False
    available_scripts = sorted([num for num in conversation_scripts.keys() if conversation_scripts[num]])
    if available_scripts:
        current_script_num = available_scripts[0]
    
    simulation_running = True
    simulation_task = asyncio.create_task(simulation_loop())
    
    mode_status = "with forced replies" if force_reply_mode else "with natural conversation"
    script_status = f"using script {current_script_num}" if current_script_num > 0 else "without script"
    topic_status = f"in topic {destination_topic_id}" if destination_topic_id else "in general chat"
    
    await update.message.reply_text(
        f"✅ Simulation started with {authorized_count} accounts {mode_status} {script_status} {topic_status}!"
    )

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
    response += f"\n\nUse /remove_account <phone> to remove an account"
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
        f"Topic ID: {destination_topic_id or 'Not set'}\n"
        f"Scripts: {script_info or 'No scripts'}\n"
        f"Current Script: {current_script_num} (Position: {current_script_index})\n"
        f"Script Status: {'Completed' if script_completed else 'In progress' if current_script_num > 0 else 'Not started'}\n"
        f"Characters: {len(script_characters)} assigned\n"
        f"Reply Mode: {'ON' if force_reply_mode else 'OFF'}\n"
        f"Interval: {min_interval}-{max_interval}s\n"
        f"Running: {simulation_running}"
    )
    await update.message.reply_text(status_text)

# ===== MAIN =====
async def main():
    print("🤖 Starting Telegram Chat Bot with Enhanced Features...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_account", add_account))
    application.add_handler(CommandHandler("remove_account", remove_account))
    application.add_handler(CommandHandler("login", login_account))
    application.add_handler(CommandHandler("set_group", set_group))
    application.add_handler(CommandHandler("clear_topic", clear_topic))
    application.add_handler(CommandHandler("check_topics", check_topics))
    application.add_handler(CommandHandler("test_topic", test_topic))
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
