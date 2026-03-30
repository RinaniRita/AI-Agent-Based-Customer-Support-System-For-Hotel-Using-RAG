import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from .services.llm_client import llm_client
from .services.rag_service import RAGService
from .agent.customer_support_agent import CustomerSupportAgent
from .config import TELEGRAM_BOT_TOKEN

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize services
rag_service = RAGService()
support_agent = CustomerSupportAgent("CustomerSupport", llm_client, rag_service)

# In-memory dictionary for state management (For Production: use Redis or Database)
user_states = {}

def get_main_menu_keyboard():
    """Generates the inline keyboard for the Main Menu."""
    keyboard = [
        [InlineKeyboardButton("🛎️ Front Desk Services", callback_data="front_desk")],
        [InlineKeyboardButton("🍽️ Order Room Service", callback_data="order_food")],
        [InlineKeyboardButton("🤖 Ask AI Concierge", callback_data="ai_mode")],
        [InlineKeyboardButton("☎️ Speak to a Human", callback_data="human_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ai_chat_keyboard():
    """Generates the inline keyboard for the AI Chat including quick prompts."""
    keyboard = [
        [InlineKeyboardButton("📜 Hotel Policies", callback_data="ai_quick_policies"),
         InlineKeyboardButton("🛎️ Hotel Services", callback_data="ai_quick_services")],
        [InlineKeyboardButton("📞 Contact Info", callback_data="ai_quick_contact"),
         InlineKeyboardButton("🗺️ Local Area Info", callback_data="ai_quick_local")],
        [InlineKeyboardButton("❓ FAQ", callback_data="ai_quick_faq")],
        [InlineKeyboardButton("🔙 Return to Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with a menu when the command /start is issued."""
    chat_id = update.effective_chat.id
    user_states[chat_id] = "MAIN_MENU"
    
    welcome_message = "👋 **Welcome to Apollo Hotel!**\n\nWhat can I help you with today?"
    await context.bot.send_message(
        chat_id=chat_id, 
        text=welcome_message, 
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses the CallbackQuery and updates message text/states."""
    query = update.callback_query
    await query.answer() # Ack the click to stop loading animation
    chat_id = update.effective_chat.id
    data = query.data

    if data == "ai_mode":
        user_states[chat_id] = "AI_MODE"
        await query.edit_message_text(
            text="🤖 **AI Concierge Activated**\n\nAsk me anything about your stay, hotel policies, or local recommendations! 👇",
            reply_markup=get_ai_chat_keyboard(),
            parse_mode="Markdown"
        )
    elif data == "main_menu":
        user_states[chat_id] = "MAIN_MENU"
        await query.edit_message_text(
            text="👋 **Welcome back to the Main Menu!**\n\nWhat can I help you with today?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    elif data == "order_food":
        keyboard = [
            [InlineKeyboardButton("🍔 Burger & Fries", callback_data="coming_soon")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            text="🍽️ **In-Room Dining**\n\nWhat would you like to order?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data.startswith("ai_quick_"):
        user_states[chat_id] = "AI_MODE"

        # --- Scripted Response: Hotel Services Overview ---
        # This bypasses RAG to guarantee a complete, accurate list of ALL services.
        if data == "ai_quick_services":
            scripted_services = (
                "✨ *Here is a complete overview of our services at Apollo Hotel:*\n\n"
                "🏨 *Standard Guest Services*\n"
                "• Check-in & Check-out\n"
                "• Room Types & Reservations\n"
                "• Concierge & Front Desk\n"
                "• Housekeeping\n"
                "• In-Room Dining\n"
                "• Spa & Wellness\n"
                "• Fitness Center\n"
                "• Valet Parking & Transport\n"
                "• Loyalty Programs\n"
                "• In-Room Technology\n"
                "• Payment & Billing\n"
                "• Cancellation\n\n"
                "💼 *Business Traveler Services*\n"
                "• Business Center\n"
                "• Meeting & Conference Rooms\n"
                "• Executive Lounges\n"
                "• Corporate Packages\n"
                "• Printing & Office Services\n"
                "• Secretarial Services\n"
                "• Courier & Delivery\n\n"
                "👨‍👩‍👧‍👦 *Family & Children Services*\n"
                "• Family Suites\n"
                "• Babysitting Services\n"
                "• Child Dining Policies\n"
                "• Child Safety\n\n"
                "🌍 *International Guest Services*\n"
                "• Multilingual Support\n"
                "• Visa Information & Assistance\n"
                "• International Payment Options\n"
                "• Embassy & Consulate Contacts\n\n"
                "🎉 *Promotions & Support*\n"
                "• Current Promotions & Offers\n"
                "• Complaints & Feedback\n"
                "• Refunds & Dispute Resolution\n"
                "• Escalation Handling\n\n"
                "🗺️ *Local Area Information*\n"
                "• Attractions & Sightseeing\n"
                "• Local Transport\n"
                "• Shopping\n"
                "• Medical Services & Pharmacies\n\n"
                "_Tap a suggested question below, or type your own!_ 😊"
            )
            # Suggested follow-up question buttons
            suggested_keyboard = [
                [InlineKeyboardButton("🕐 Check-in & Check-out times?", callback_data="svc_q_checkin")],
                [InlineKeyboardButton("🍽️ What dining options are available?", callback_data="svc_q_dining")],
                [InlineKeyboardButton("💆 Tell me about the Spa", callback_data="svc_q_spa")],
                [InlineKeyboardButton("👶 Do you offer babysitting?", callback_data="svc_q_babysitting")],
                [InlineKeyboardButton("💼 Meeting room options?", callback_data="svc_q_meetings")],
                [InlineKeyboardButton("🚗 Airport transfer services?", callback_data="svc_q_transport")],
                [InlineKeyboardButton("🎁 Any current promotions?", callback_data="svc_q_promos")],
                [InlineKeyboardButton("🏋️ Fitness center details?", callback_data="svc_q_fitness")],
                [InlineKeyboardButton("🔙 Return to Main Menu", callback_data="main_menu")]
            ]
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=chat_id,
                text=scripted_services,
                reply_markup=InlineKeyboardMarkup(suggested_keyboard),
                parse_mode="Markdown"
            )
            return

        # --- Scripted Response: Hotel Policies Overview ---
        # Bypasses RAG to give guests the FULL, accurate policy details.
        if data == "ai_quick_policies":
            scripted_policies = (
                "📜 *Apollo Hotel — Official Policies & House Rules*\n\n"
                "🕐 *1. Arrival & Departure*\n"
                "• *Check-In:* **2:00 PM** (14:00)\n"
                "• *Check-Out:* **11:00 AM**\n"
                "• *Late Check-Out:* Subject to availability; must be arranged with reception in advance (additional fee applies)\n"
                "• *Minors:* Guests with children under 18 must present official documentation confirming their relationship\n\n"
                "🐾 *2. Pet Policy*\n"
                "• ⛔ **STRICTLY NO PETS** — Pets are not allowed under any circumstances\n"
                "• Arriving with a pet may result in refusal of accommodation *without* a refund\n\n"
                "🚭 *3. Smoking & Conduct*\n"
                "• The entire hotel is **100% smoke-free** (including e-cigarettes and vapes)\n"
                "• Violation penalty: **€250** deep-cleaning charge\n"
                "• *Quiet Hours:* **10:00 PM – 6:00 AM** — please respect all guests\n\n"
                "♿ *4. Accessibility*\n"
                "• Wheelchair-accessible rooms and facilities available\n"
                "• Please contact the front desk to arrange accessible accommodations\n\n"
                "🌿 *5. Sustainability*\n"
                "• Strict waste separation & recycling protocols\n"
                "• Towel & bedding reuse program to conserve water\n"
                "• Eco-friendly cleaning products used throughout\n"
                "• Active food waste reduction programs\n\n"
                "🔒 *6. Data Privacy & GDPR*\n"
                "• Guest data is handled in full compliance with GDPR regulations\n"
                "• Personal information is never shared with third parties without consent\n\n"
                "⚖️ *7. Liability*\n"
                "• The hotel is not responsible for valuables left unattended\n"
                "• In-room safes are available for securing personal items\n\n"
                "_Tap a question below for more details, or type your own!_ 😊"
            )
            suggested_keyboard = [
                [InlineKeyboardButton("🕐 Check-in & check-out details?", callback_data="pol_q_checkin")],
                [InlineKeyboardButton("🐾 What is the pet policy?", callback_data="pol_q_pets")],
                [InlineKeyboardButton("🚭 Smoking rules & penalties?", callback_data="pol_q_smoking")],
                [InlineKeyboardButton("♿ Accessibility options?", callback_data="pol_q_accessibility")],
                [InlineKeyboardButton("🔒 Data privacy & GDPR?", callback_data="pol_q_gdpr")],
                [InlineKeyboardButton("⚖️ Liability & lost items?", callback_data="pol_q_liability")],
                [InlineKeyboardButton("🔙 Return to Main Menu", callback_data="main_menu")]
            ]
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=chat_id,
                text=scripted_policies,
                reply_markup=InlineKeyboardMarkup(suggested_keyboard),
                parse_mode="Markdown"
            )
            return

        # --- RAG-Based Response: All other quick buttons ---
        prompt_map = {
            "ai_quick_contact": "Please provide the hotel's contact information and location.",
            "ai_quick_local": "What is some local area information and recommendations?",
            "ai_quick_faq": "What are some frequently asked questions? Please provide a bulleted list of common questions I can ask."
        }
        
        user_message = prompt_map.get(data, "Tell me about the hotel.")
        user_context = {"session_id": str(chat_id), "user_id": update.effective_user.id}
        
        logger.info(f"Processing AI quick button request: {user_message}")
        try:
            # We edit the message to remove the buttons while processing, or just send a typing action
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await query.edit_message_reply_markup(reply_markup=None)
            
            result = await asyncio.to_thread(
                support_agent.process_query,
                user_message,
                user_context
            )
            
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"👉 *{user_message}*\n\n{result['response']}", 
                reply_markup=get_ai_chat_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error processing AI button request: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id, 
                text="Sorry, I encountered an error processing your request.",
                reply_markup=get_ai_chat_keyboard()
            )
    elif data.startswith("svc_q_"):
        # --- Suggested Service Question Routing (RAG-based) ---
        user_states[chat_id] = "AI_MODE"
        svc_question_map = {
            "svc_q_checkin": "What are the check-in and check-out times and procedures?",
            "svc_q_dining": "What dining options and restaurants are available at the hotel?",
            "svc_q_spa": "Tell me about the spa and wellness services available.",
            "svc_q_babysitting": "Do you offer babysitting or childcare services? What are the details?",
            "svc_q_meetings": "What meeting and conference room options do you have?",
            "svc_q_transport": "What airport transfer and transport services do you offer?",
            "svc_q_promos": "Are there any current promotions or special offers available?",
            "svc_q_fitness": "What are the fitness center hours, facilities, and rules?"
        }
        user_message = svc_question_map.get(data, "Tell me more about this hotel service.")
        user_context = {"session_id": str(chat_id), "user_id": update.effective_user.id}
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await query.edit_message_reply_markup(reply_markup=None)
            
            result = await asyncio.to_thread(
                support_agent.process_query,
                user_message,
                user_context
            )
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👉 *{user_message}*\n\n{result['response']}",
                reply_markup=get_ai_chat_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error processing service question: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, I encountered an error. Please try again.",
                reply_markup=get_ai_chat_keyboard()
            )
    elif data.startswith("pol_q_"):
        # --- Suggested Policy Question Routing (RAG-based) ---
        user_states[chat_id] = "AI_MODE"
        pol_question_map = {
            "pol_q_checkin": "What are the detailed check-in and check-out times and late check-out policy?",
            "pol_q_pets": "What is the hotel's pet policy? Are any pets allowed?",
            "pol_q_smoking": "What are the smoking rules and penalties at the hotel?",
            "pol_q_accessibility": "What accessibility options and facilities are available for guests with disabilities?",
            "pol_q_gdpr": "What is the hotel's data privacy and GDPR policy?",
            "pol_q_liability": "What is the hotel's liability policy regarding lost or damaged personal items?"
        }
        user_message = pol_question_map.get(data, "Tell me more about this hotel policy.")
        user_context = {"session_id": str(chat_id), "user_id": update.effective_user.id}
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await query.edit_message_reply_markup(reply_markup=None)
            
            result = await asyncio.to_thread(
                support_agent.process_query,
                user_message,
                user_context
            )
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👉 *{user_message}*\n\n{result['response']}",
                reply_markup=get_ai_chat_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error processing policy question: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, I encountered an error. Please try again.",
                reply_markup=get_ai_chat_keyboard()
            )
    elif data == "coming_soon" or data == "front_desk" or data == "human_support":
        # Placeholder for other static menus
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.edit_message_text(
            text="🚧 *This feature is currently under construction.*\n\nPlease return to the main menu.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages. Auto-routes to AI Concierge."""
    chat_id = update.effective_chat.id
    user_message = update.message.text
    
    # Auto-switch user to AI_MODE when they type any message
    user_states[chat_id] = "AI_MODE"

    # RAG LLM Processing
    logger.info(f"Processing AI chat request: {user_message[:50]}...")
    user_context = {"session_id": str(chat_id), "user_id": update.effective_user.id}
    
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        result = await asyncio.to_thread(
            support_agent.process_query,
            user_message,
            user_context
        )
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=result['response'], 
            reply_markup=get_ai_chat_keyboard(), # Always show the exit button
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="Sorry, I encountered an error processing your request. Please try again.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment or config.py")
        exit(1)
        
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Core handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Starting Telegram UX Bot Polling...")
    application.run_polling()

if __name__ == '__main__':
    main()