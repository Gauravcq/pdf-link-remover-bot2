import telebot
from telebot import types
import fitz
import os
import tempfile
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("8424270071:AAGrRuewVf0TbGMGsP-GVJKHcXNw0vx1fRE")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

class UserSession:
    def __init__(self):
        self.pdf_path = None
        self.total_pages = 0
        self.choice = None
        self.pages_to_remove = None

def create_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("📤 Upload PDF")
    markup.row("ℹ️ Help", "📊 About")
    return markup

def create_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("🗑 Remove ALL Links")
    markup.row("📄 Remove from Specific Pages")
    markup.row("👁 View Links Only")
    markup.row("🔙 Cancel")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"User {message.chat.id} started")
    user_states[message.chat.id] = UserSession()
    welcome_text = """🤖 **PDF Link Removal Bot**

I can help you remove hyperlinks from PDF files!

**Features:**
✅ Remove all links from PDF
✅ Remove links from specific pages
✅ View existing links

Click "📤 Upload PDF" to start!"""
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=create_main_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """📖 **How to Use**

**Step 1:** Upload PDF (max 20MB)
**Step 2:** Choose action
**Step 3:** Get processed PDF

**Page Examples:**
• Single: `1, 3, 5`
• Range: `1-5`
• Mixed: `1, 3-5, 8-10`"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def send_about(message):
    bot.send_message(message.chat.id, "📊 **PDF Link Remover Bot v1.0**\n\n🔒 Files deleted after processing\n❤️ Made with Python", parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    
    if message.document.mime_type != 'application/pdf':
        bot.send_message(chat_id, "❌ PDF files only!")
        return
    
    if message.document.file_size > 20 * 1024 * 1024:
        bot.send_message(chat_id, "❌ Max 20MB!")
        return
    
    bot.send_message(chat_id, "⏳ Downloading...")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        temp_dir = tempfile.gettempdir()
        pdf_path = os.path.join(temp_dir, f"{chat_id}_{int(time.time())}.pdf")
        
        with open(pdf_path, 'wb') as f:
            f.write(downloaded_file)
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        
        if chat_id not in user_states:
            user_states[chat_id] = UserSession()
        
        user_states[chat_id].pdf_path = pdf_path
        user_states[chat_id].total_pages = total_pages
        
        msg = f"""✅ **PDF Uploaded!**

📄 **File:** {message.document.file_name}
📊 **Pages:** {total_pages}
💾 **Size:** {message.document.file_size / 1024:.1f} KB"""
        bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=create_action_menu())
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.send_message(chat_id, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    text = message.text
    
    if chat_id not in user_states:
        user_states[chat_id] = UserSession()
    
    session = user_states[chat_id]
    
    if text == "📤 Upload PDF":
        bot.send_message(chat_id, "📎 Send me a PDF", reply_markup=types.ReplyKeyboardRemove())
        return
    elif text == "ℹ️ Help":
        send_help(message)
        return
    elif text == "📊 About":
        send_about(message)
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
        process_remove_all(chat_id)
    elif text == "📄 Remove from Specific Pages":
        session.choice = 'specific'
        bot.send_message(chat_id, f"📄 Enter pages (PDF has {session.total_pages} pages)\n\nExamples: `1, 3, 5` or `1-5` or `1, 3-5, 8`", parse_mode="Markdown")
    elif text == "👁 View Links Only":
        process_view_links(chat_id)
    elif session.choice == 'specific':
        try:
            pages = parse_page_numbers(text, session.total_pages)
            if pages:
                process_remove_specific(chat_id, pages)
            else:
                bot.send_message(chat_id, "❌ No valid pages. Try again:")
        except ValueError as e:
            bot.send_message(chat_id, f"❌ {str(e)}\nTry again:")

def parse_page_numbers(input_str, total_pages):
    pages = set()
    parts = input_str.replace(' ', '').split(',')
    
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            start, end = int(start), int(end)
            if start < 1 or end > total_pages:
                raise ValueError(f"Range {start}-{end} invalid (1-{total_pages})")
            pages.update(range(start, end + 1))
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p)
            else:
                raise ValueError(f"Page {p} out of bounds")
    return pages

def process_remove_all(chat_id):
    session = user_states[chat_id]
    bot.send_message(chat_id, "⏳ Removing all links...")
    
    try:
        pdf_path = session.pdf_path
        output_path = pdf_path.replace('.pdf', '_no_links.pdf')
        
        doc = fitz.open(pdf_path)
        removed_count = 0
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            links = page.get_links()
            for link in links:
                page.delete_link(link)
                removed_count += 1
        
        doc.save(output_path)
        doc.close()
        
        bot.send_message(chat_id, f"✅ **Removed {removed_count} links from {session.total_pages} pages!**", parse_mode="Markdown")
        
        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption="✅ Your PDF", reply_markup=create_main_menu())
        
        os.remove(pdf_path)
        os.remove(output_path)
        user_states[chat_id] = UserSession()
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}")

def process_remove_specific(chat_id, pages):
    session = user_states[chat_id]
    bot.send_message(chat_id, f"⏳ Processing {len(pages)} pages...")
    
    try:
        pdf_path = session.pdf_path
        output_path = pdf_path.replace('.pdf', '_removed.pdf')
        
        doc = fitz.open(pdf_path)
        removed_count = 0
        
        for page_num in range(len(doc)):
            if (page_num + 1) in pages:
                page = doc[page_num]
                links = page.get_links()
                for link in links:
                    page.delete_link(link)
                    removed_count += 1
        
        doc.save(output_path)
        doc.close()
        
        bot.send_message(chat_id, f"✅ **Removed {removed_count} links!**\nPages: {sorted(list(pages))}", parse_mode="Markdown")
        
        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption="✅ Your PDF", reply_markup=create_main_menu())
        
        os.remove(pdf_path)
        os.remove(output_path)
        user_states[chat_id] = UserSession()
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}")

def process_view_links(chat_id):
    session = user_states[chat_id]
    bot.send_message(chat_id, "🔍 Scanning...")
    
    try:
        doc = fitz.open(session.pdf_path)
        total_links = 0
        link_info = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            links = page.get_links()
            
            if links:
                link_info.append(f"\n**Page {page_num + 1}:**")
                for i, link in enumerate(links, 1):
                    uri = link.get('uri', 'N/A')
                    link_info.append(f"  [{i}] {uri}")
                    total_links += 1
        
        doc.close()
        
        if total_links == 0:
            msg = "ℹ️ No links found"
        else:
            msg = f"🔗 **Found {total_links} links**\n\n" + "\n".join(link_info[:30])
        
        bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=create_main_menu())
        os.remove(session.pdf_path)
        user_states[chat_id] = UserSession()
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}")

if __name__ == "__main__":
    logger.info("🤖 Bot starting...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)