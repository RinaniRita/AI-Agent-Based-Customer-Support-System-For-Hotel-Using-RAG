import logging
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from .services.llm_client import llm_client
from .services.rag_service import RAGService
from .agent.customer_support_agent import CustomerSupportAgent
from .config import TELEGRAM_BOT_TOKEN, FRONTEND_URL, API_BASE_URL

# Database service
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import (
    init_db, create_booking, update_booking_dates,
    update_booking_guest_info, get_booking, get_room_info,
    check_availability, get_available_room_numbers
)

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
init_db()

# Initialize services
rag_service = RAGService()
support_agent = CustomerSupportAgent("CustomerSupport", llm_client, rag_service)

# In-memory dictionary for state management (For Production: use Redis or Database)
user_states = {}

# Booking session tracking: { chat_id: { "booking_id": int, "room_type": str, "step": str } }
booking_sessions = {}

# Web server base URL (remove hardcoded local if needed, now using config)
# FRONTEND_URL and API_BASE_URL imported from .config above

def get_main_menu_keyboard():
    """Generates the inline keyboard for the Main Menu."""
    keyboard = [
        [InlineKeyboardButton("🏨 Hotel Rooms & Booking", callback_data="view_rooms")],
        [InlineKeyboardButton("🛎️ Front Desk Services", callback_data="front_desk")],
        [InlineKeyboardButton("🍽️ Order Room Service", callback_data="order_food")],
        [InlineKeyboardButton("🤖 Ask AI Concierge", callback_data="ai_mode")],
        [InlineKeyboardButton("☎️ Speak to a Human", callback_data="human_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_rooms_keyboard():
    """Generates the inline keyboard for browsing hotel rooms."""
    keyboard = [
        [InlineKeyboardButton("🛏️ Standard Room (from 127€)", callback_data="room_standard")],
        [InlineKeyboardButton("🛏️ Standard + Extra Bed (from 183€)", callback_data="room_standard_extra")],
        [InlineKeyboardButton("🏙️ Comfort Room (from 142€)", callback_data="room_comfort")],
        [InlineKeyboardButton("🌟 Superior Room (from 168€)", callback_data="room_superior")],
        [InlineKeyboardButton("🌇 Superior Balcony (from 235€)", callback_data="room_sup_balcony")],
        [InlineKeyboardButton("🌅 Superior Panoramic (from 235€)", callback_data="room_sup_panoramic")],
        [InlineKeyboardButton("💎 Junior Suite (from 175€)", callback_data="room_junior_suite")],
        [InlineKeyboardButton("👑 Superior Suite (from 235€)", callback_data="room_sup_suite")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_room_detail_keyboard(room_type):
    """Generates the action buttons for a specific room."""
    keyboard = [
        [InlineKeyboardButton("✅ Book Now", callback_data=f"book_{room_type}")],
        [InlineKeyboardButton("🔙 Back to Rooms", callback_data="view_rooms")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ai_chat_keyboard():
    """Generates the inline keyboard for exiting the AI Chat."""
    keyboard = [
        [InlineKeyboardButton("🔙 Return to Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with a menu when the command /start is issued."""
    chat_id = update.effective_chat.id
    user_states[chat_id] = "MAIN_MENU"
    
    welcome_message = "👋 **Welcome to Luxury Hotel!**\n\nWhat can I help you with today?"
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
    elif data == "view_rooms":
        user_states[chat_id] = "VIEWING_ROOMS"
        await query.edit_message_text(
            text="🏨 **Our Luxury Rooms**\n\nPlease select a room type below to see more details and pricing:",
            reply_markup=get_rooms_keyboard(),
            parse_mode="Markdown"
        )
    elif data == "room_standard":
        text = (
            "🛏️ **Standard Double/Twin Room**\n\n"
            "*Tastefully decorated in light natural colours, offering a quiet environment thanks to double glazed windows.*\n\n"
            "💰 **Starting from:** 127 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** 1 Double or 2 Twins\n"
            "✨ **Highlights:** Heated bathroom floors, Fast Wi-Fi, A/C"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("standard"), parse_mode="Markdown")
    elif data == "room_standard_extra":
        text = (
            "🛏️ **Standard Room + Extra Bed**\n\n"
            "*Extended Standard room with more space, comfortably sleeping up to 3 adults with a full-sized extra bed.*\n\n"
            "💰 **Starting from:** 183 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** 1 Double or 2 Twins + Extra Bed\n"
            "👥 **Max Occupancy:** 3 adults\n"
            "✨ **Highlights:** Extra space, Heated floors, Fast Wi-Fi, A/C"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("standard_extra"), parse_mode="Markdown")
    elif data == "room_comfort":
        text = (
            "🏙️ **Comfort Double/Twin Room**\n\n"
            "*Offers more space than our Standard rooms with beautiful city or street views.*\n\n"
            "💰 **Starting from:** 142 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** 1 Double or 2 Twins\n"
            "✨ **Highlights:** Extra Space, City Views, Heated floors, Fast Wi-Fi"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("comfort"), parse_mode="Markdown")
    elif data == "room_superior":
        text = (
            "🌟 **Superior Room**\n\n"
            "*Full of sun and light on the 7th and 8th floor. Features stunning rooftop or river views.*\n\n"
            "💰 **Starting from:** 168 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** 1 Large Double (Max 2 people, No kids)\n"
            "✨ **Highlights:** Nespresso, Bathrobes, Free Water & Pralines"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("superior"), parse_mode="Markdown")
    elif data == "room_sup_balcony":
        text = (
            "🌇 **Superior Room with Balcony**\n\n"
            "*Top-floor room with a private balcony offering magnificent views over Prague's rooftops.*\n\n"
            "💰 **Starting from:** 235 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** Double or Twin (Max 2 people)\n"
            "🏙️ **View:** City rooftops + Private Balcony\n"
            "✨ **Highlights:** Nespresso, Bathrobes, Welcome treats"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("sup_balcony"), parse_mode="Markdown")
    elif data == "room_sup_panoramic":
        text = (
            "🌅 **Superior Panoramic Window + Balcony**\n\n"
            "*Our most romantic room! Top floor with curved panoramic windows and stunning river & city views.*\n\n"
            "💰 **Starting from:** 235 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** Double Bed (Max 2 people)\n"
            "🏙️ **View:** River + City Panorama + Balcony\n"
            "✨ **Highlights:** Nespresso, Bathrobes, Welcome treats"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("sup_panoramic"), parse_mode="Markdown")
    elif data == "room_junior_suite":
        text = (
            "💎 **Junior Suite**\n\n"
            "*Extra space, beautifully furnished. One of our quietest rooms, located at the end of the corridor. Perfect for families!*\n\n"
            "💰 **Starting from:** 175 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** 1 Double + Sofa Bed (sleeps 3 adults or 2+2 kids)\n"
            "👶 **Children:** Allowed (baby cot available)\n"
            "✨ **Highlights:** Nespresso, Bathrobes, Smart TV, Bathtub"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("junior_suite"), parse_mode="Markdown")
    elif data == "room_sup_suite":
        text = (
            "👑 **Superior Suite**\n\n"
            "*Luxurious 2-room suite with separate bedroom and living room. Ideal for business travelers and families.*\n\n"
            "💰 **Starting from:** 235 EUR / night (Breakfast included)\n"
            "🛏️ **Beds:** King Bed + Sofa Bed (up to 4 people)\n"
            "🛁 **Bathrooms:** 2 full bathrooms\n"
            "👶 **Children:** Welcome (baby cot available)\n"
            "✨ **Highlights:** 2 Smart TVs, Microwave, Nespresso, Bathrobes, Early check-in/late check-out"
        )
        await query.edit_message_text(text=text, reply_markup=get_room_detail_keyboard("sup_suite"), parse_mode="Markdown")
    elif data.startswith("book_"):
        # Extract room_type from callback (e.g., "book_standard" -> "standard")
        room_type = data.replace("book_", "")
        room_info = get_room_info(room_type)
        room_name = room_info["display_name"] if room_info else "Selected Room"

        # Create a pending booking in the database
        booking_id = create_booking(chat_id, room_type)

        # Track the booking session
        booking_sessions[chat_id] = {
            "booking_id": booking_id,
            "room_type": room_type,
            "room_name": room_name,
            "step": "WAITING_DATES"
        }
        user_states[chat_id] = "BOOKING_FLOW"

        booking_prompt = (
            f"✅ *Excellent choice! Let's book the {room_name}.*\n\n"
            "📅 Please type your *Check-in* and *Check-out* dates below.\n\n"
            "Example: `April 5 to April 8`\n\n"
            "_I'll check availability for you right away!_ 👇"
        )
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Booking", callback_data="main_menu")]])
        await query.edit_message_text(text=booking_prompt, reply_markup=cancel_kb, parse_mode="Markdown")
        
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

def parse_dates(text: str):
    """Try to extract check-in and check-out dates from user text."""
    # Common patterns: "April 5 to April 8", "2026-04-05 to 2026-04-08", "5/4 to 8/4"
    text = text.strip()
    patterns = [
        # "April 5 to April 8" or "April 5 - April 8"
        r'(\w+ \d{1,2})\s*(?:to|-)\s*(\w+ \d{1,2})',
        # "2026-04-05 to 2026-04-08"
        r'(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                d1_str, d2_str = match.group(1), match.group(2)
                # Try parsing with year
                for fmt in ["%Y-%m-%d", "%B %d", "%b %d"]:
                    try:
                        d1 = datetime.strptime(d1_str, fmt)
                        d2 = datetime.strptime(d2_str, fmt)
                        # If no year was parsed, assume current/next year
                        if d1.year == 1900:
                            now = datetime.now()
                            d1 = d1.replace(year=now.year)
                            d2 = d2.replace(year=now.year)
                            if d1 < now:
                                d1 = d1.replace(year=now.year + 1)
                                d2 = d2.replace(year=now.year + 1)
                        return d1, d2
                    except ValueError:
                        continue
            except Exception:
                continue
    return None, None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages. Routes to booking flow or AI concierge."""
    chat_id = update.effective_chat.id
    user_message = update.message.text
    state = user_states.get(chat_id, "MAIN_MENU")

    # ─── BOOKING FLOW STATE MACHINE ───
    if state == "BOOKING_FLOW" and chat_id in booking_sessions:
        session = booking_sessions[chat_id]
        step = session.get("step")

        # Step 1: Waiting for dates
        if step == "WAITING_DATES":
            check_in, check_out = parse_dates(user_message)
            if not check_in or not check_out:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ I couldn't understand those dates. Please try again.\n\nExample: `April 5 to April 8`",
                    parse_mode="Markdown"
                )
                return

            # ── Real-time past-date rejection ──
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if check_in < today:
                today_str = today.strftime("%B %d, %Y")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ You cannot book a date in the past!\n\n"
                        f"📆 Today is *{today_str}*.\n"
                        "Please enter a *future* check-in date."
                    ),
                    parse_mode="Markdown"
                )
                return

            if check_out <= check_in:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Check-out date must be after check-in date. Please try again.",
                    parse_mode="Markdown"
                )
                return

            nights = (check_out - check_in).days
            ci_str = check_in.strftime("%Y-%m-%d")
            co_str = check_out.strftime("%Y-%m-%d")

            # ── Check physical room availability ──
            available_rooms = get_available_room_numbers(session["room_type"], ci_str, co_str)
            if not available_rooms:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"😞 Sorry, all 5 rooms of *{session['room_name']}* are fully booked "
                        f"from {ci_str} to {co_str}.\n\n"
                        "Please try different dates or choose another room type."
                    ),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Rooms", callback_data="view_rooms")]]),
                    parse_mode="Markdown"
                )
                del booking_sessions[chat_id]
                user_states[chat_id] = "MAIN_MENU"
                return

            # Save dates to DB and assign a physical room
            assigned_room = update_booking_dates(session["booking_id"], ci_str, co_str, nights)
            session["step"] = "WAITING_NAME"
            session["room_number"] = assigned_room

            room_info = get_room_info(session["room_type"])
            total = room_info["price_per_night"] * nights
            rooms_left = len(available_rooms) - 1  # minus the one just assigned

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ *{session['room_name']}* is available!\n\n"
                    f"🚪 *Assigned Room:* #{assigned_room}\n"
                    f"📅 *Check-in:* {ci_str}\n"
                    f"📅 *Check-out:* {co_str}\n"
                    f"🌙 *Nights:* {nights}\n"
                    f"💰 *Total:* €{total:.0f}\n"
                    f"🏨 *Rooms still available:* {rooms_left} of 5\n\n"
                    "Now, please type your *Full Name* to continue."
                ),
                parse_mode="Markdown"
            )
            return

        # Step 2: Waiting for name
        elif step == "WAITING_NAME":
            session["guest_name"] = user_message.strip()
            session["step"] = "WAITING_EMAIL"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👤 Thank you, *{session['guest_name']}*!\n\nPlease type your *Email Address*.",
                parse_mode="Markdown"
            )
            return

        # Step 3: Waiting for email
        elif step == "WAITING_EMAIL":
            session["guest_email"] = user_message.strip()
            session["step"] = "WAITING_PHONE"
            await context.bot.send_message(
                chat_id=chat_id,
                text="📧 Got it! Now please type your *Phone Number*.",
                parse_mode="Markdown"
            )
            return

        # Step 4: Waiting for phone → Save info & generate checkout link
        elif step == "WAITING_PHONE":
            session["guest_phone"] = user_message.strip()

            # Save guest info to DB
            update_booking_guest_info(
                session["booking_id"],
                session["guest_name"],
                session["guest_email"],
                session["guest_phone"]
            )

            # Generate GitHub Pages checkout URL with dynamic API bridge
            checkout_url = f"{FRONTEND_URL}/review.html?id={session['booking_id']}&api={API_BASE_URL}"
            room_num = session.get('room_number', '')

            # Send booking summary (with Markdown)
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "🎉 *Your booking is almost complete!*\n\n"
                    f"🏨 *Room:* {session['room_name']} (#{room_num})\n"
                    f"👤 *Name:* {session['guest_name']}\n"
                    f"📧 *Email:* {session['guest_email']}\n"
                    f"📞 *Phone:* {session['guest_phone']}\n\n"
                    "Please click the link below to review and complete payment:\n"
                ),
                parse_mode="Markdown"
            )
            # Send checkout URL as a SEPARATE plain-text message so Telegram auto-links it
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👉 {checkout_url}",
                reply_markup=get_main_menu_keyboard()
            )

            # Clean up session
            del booking_sessions[chat_id]
            user_states[chat_id] = "MAIN_MENU"
            return

    # ─── DEFAULT: AI CONCIERGE MODE ───
    user_states[chat_id] = "AI_MODE"
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
            reply_markup=get_ai_chat_keyboard(),
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