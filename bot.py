import telebot
from telebot import types
import fitz
import os
import tempfile
import time

BOT_TOKEN = os.environ.get("8424270071:AAGrRuewVf0TbGMGsP-GVJKHcXNw0vx1fRE")
bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

class UserSession:
    def __init__(self):
        self.pdf_path = None
        self.total_pages = 0
        self.choice = None

def create_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📤 Upload PDF")
    markup.row("ℹ️ Help")
    return markup

def create_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🗑 Remove ALL Links")
    markup.row("📄 Remove from Specific Pages")
    markup.row("👁 View Links Only")
    markup.row("🔙 Cancel")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = UserSession()
    bot.send_message(message.chat.id, 
        "🤖 *PDF Link Removal Bot*\n\n"
        "Send me a PDF and I'll remove links!\n\n"
        "Click 📤 Upload PDF to start",
        parse_mode="Markdown",
        reply_markup=create_main_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_message(message.chat.id,
        "📖 *How to use:*\n\n"
        "1. Upload PDF file\n"
        "2. Choose action\n"
        "3. Get processed PDF\n\n"
        "*Page format:*\n"
        "Single: 1, 3, 5\n"
        "Range: 1-5\n"
        "Mixed: 1, 3-5, 8",
        parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    
    if message.document.mime_type != 'application/pdf':
        bot.send_message(chat_id, "❌ PDF files only!")
        return
    
    if message.document.file_size > 20 * 1024 * 1024:
        bot.send_message(chat_id, "❌ Max 20MB")
        return
    
    bot.send_message(chat_id, "⏳ Downloading...")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        pdf_path = os.path.join(tempfile.gettempdir(), f"{chat_id}_{int(time.time())}.pdf")
        
        with open(pdf_path, 'wb') as f:
            f.write(downloaded_file)
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        
        if chat_id not in user_states:
            user_states[chat_id] = UserSession()
        
        user_states[chat_id].pdf_path = pdf_path
        user_states[chat_id].total_pages = total_pages
        
        bot.send_message(chat_id,
            f"✅ *PDF Uploaded!*\n\n"
            f"📄 {message.document.file_name}\n"
            f"📊 Pages: {total_pages}",
            parse_mode="Markdown",
            reply_markup=create_action_menu())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    chat_id = message.chat.id
    text = message.text
    
    if chat_id not in user_states:
        user_states[chat_id] = UserSession()
    
    session = user_states[chat_id]
    
    if text == "📤 Upload PDF":
        bot.send_message(chat_id, "📎 Send me a PDF file")
        return
    elif text == "ℹ️ Help":
        send_help(message)
        return
    elif text == "🔙 Cancel":
        if session.pdf_path and os.path.exists(session.pdf_path):
            os.remove(session.pdf_path)
        user_states[chat_id] = UserSession()
        bot.send_message(chat_id, "❌ Cancelled", reply_markup=create_main_menu())
        return
    
    if not session.pdf_path:
        bot.send_message(chat_id, "⚠️ Upload PDF first!", reply_markup=create_main_menu())
        return
    
    if text == "🗑 Remove ALL Links":
        remove_all_links(chat_id)
    elif text == "📄 Remove from Specific Pages":
        session.choice = 'specific'
        bot.send_message(chat_id, f"Enter pages (1-{session.total_pages})\nExample: 1,3,5 or 1-5")
    elif text == "👁 View Links Only":
        view_links(chat_id)
    elif session.choice == 'specific':
        try:
            pages = parse_pages(text, session.total_pages)
            remove_specific_links(chat_id, pages)
        except:
            bot.send_message(chat_id, "❌ Invalid format. Try: 1,3,5")

def parse_pages(text, total):
    pages = set()
    for part in text.replace(' ', '').split(','):
        if '-' in part:
            s, e = map(int, part.split('-'))
            pages.update(range(s, e + 1))
        else:
            pages.add(int(part))
    return pages

def remove_all_links(chat_id):
    session = user_states[chat_id]
    bot.send_message(chat_id, "⏳ Removing all links...")
    
    try:
        doc = fitz.open(session.pdf_path)
        removed = 0
        
        for page in doc:
            links = page.get_links()
            for link in links:
                page.delete_link(link)
                removed += 1
        
        output = session.pdf_path.replace('.pdf', '_no_links.pdf')
        doc.save(output)
        doc.close()
        
        bot.send_message(chat_id, f"✅ Removed {removed} links!")
        
        with open(output, 'rb') as f:
            bot.send_document(chat_id, f, caption="✅ Done", reply_markup=create_main_menu())
        
        os.remove(session.pdf_path)
        os.remove(output)
        user_states[chat_id] = UserSession()
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

def remove_specific_links(chat_id, pages):
    session = user_states[chat_id]
    bot.send_message(chat_id, f"⏳ Processing {len(pages)} pages...")
    
    try:
        doc = fitz.open(session.pdf_path)
        removed = 0
        
        for i, page in enumerate(doc):
            if (i + 1) in pages:
                for link in page.get_links():
                    page.delete_link(link)
                    removed += 1
        
        output = session.pdf_path.replace('.pdf', '_removed.pdf')
        doc.save(output)
        doc.close()
        
        bot.send_message(chat_id, f"✅ Removed {removed} links from pages {sorted(pages)}")
        
        with open(output, 'rb') as f:
            bot.send_document(chat_id, f, caption="✅ Done", reply_markup=create_main_menu())
        
        os.remove(session.pdf_path)
        os.remove(output)
        user_states[chat_id] = UserSession()
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

def view_links(chat_id):
    session = user_states[chat_id]
    bot.send_message(chat_id, "🔍 Scanning...")
    
    try:
        doc = fitz.open(session.pdf_path)
        total = 0
        info = []
        
        for i, page in enumerate(doc):
            links = page.get_links()
            if links:
                info.append(f"\nPage {i+1}: {len(links)} links")
                total += len(links)
        
        doc.close()
        
        if total == 0:
            msg = "ℹ️ No links found"
        else:
            msg = f"🔗 Found {total} links\n" + "\n".join(info[:20])
        
        bot.send_message(chat_id, msg, reply_markup=create_main_menu())
        os.remove(session.pdf_path)
        user_states[chat_id] = UserSession()
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

print("🤖 Bot starting...")
bot.infinity_polling()
