#!/usr/bin/env python3
"""
بوت متكامل مع جميع أنظمة الربح والميزات المتقدمة
نسخة كاملة - جاهزة للنسخ واللصق مباشرة
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import random
from datetime import datetime, timedelta
import sqlite3
import string
import json
import os

# ==================== الإعدادات الأساسية ====================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# توكن البوت - غير هذا إلى التوكن الخاص بك
TOKEN = "8621321021:AAEPwkX2VWTA5krSvIJ5pyh7kkfHwm0yK5o" 
 

# ملف قاعدة البيانات
DB_FILE = "bot_database.db"

# ==================== نظام قاعدة البيانات ====================

def init_database():
    """تهيئة جميع جداول قاعدة البيانات"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  coins INTEGER DEFAULT 100,
                  total_withdrawn REAL DEFAULT 0,
                  referral_code TEXT UNIQUE,
                  referred_by INTEGER,
                  level INTEGER DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # جدول طلبات السحب
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount_coins INTEGER,
                  amount_usd REAL,
                  method TEXT,
                  details TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # جدول المكافآت اليومية
    c.execute('''CREATE TABLE IF NOT EXISTS daily_rewards
                 (user_id INTEGER,
                  date TEXT,
                  claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (user_id, date))''')
    
    # جدول التحديات اليومية
    c.execute('''CREATE TABLE IF NOT EXISTS user_challenges
                 (user_id INTEGER, 
                  challenge_id INTEGER, 
                  date TEXT, 
                  progress INTEGER DEFAULT 0, 
                  completed BOOLEAN DEFAULT 0,
                  PRIMARY KEY (user_id, challenge_id, date))''')
    
    # جدول لعبة الحظ اليومي
    c.execute('''CREATE TABLE IF NOT EXISTS daily_luck
                 (user_id INTEGER, 
                  date TEXT, 
                  prize INTEGER,
                  PRIMARY KEY (user_id, date))''')
    
    # جدول الإحصائيات
    c.execute('''CREATE TABLE IF NOT EXISTS user_stats
                 (user_id INTEGER,
                  games_played INTEGER DEFAULT 0,
                  games_won INTEGER DEFAULT 0,
                  total_earned INTEGER DEFAULT 0,
                  last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (user_id))''')
    
    conn.commit()
    conn.close()
    print("✅ قاعدة البيانات جاهزة")

# تهيئة قاعدة البيانات عند بدء التشغيل
init_database()

# ==================== دوال المساعدة ====================

def get_user_coins(user_id):
    """الحصول على رصيد المستخدم"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result:
        c.execute("INSERT INTO users (user_id, coins) VALUES (?, ?)", (user_id, 100))
        conn.commit()
        coins = 100
    else:
        coins = result[0]
    
    conn.close()
    return coins

def update_user_coins(user_id, amount):
    """تحديث رصيد المستخدم"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    
    # تحديث إجمالي الأرباح إذا كان المبلغ موجباً
    if amount > 0:
        c.execute('''INSERT INTO user_stats (user_id, total_earned) 
                     VALUES (?, ?) 
                     ON CONFLICT(user_id) 
                     DO UPDATE SET total_earned = total_earned + ?''',
                  (user_id, amount, amount))
    
    conn.commit()
    conn.close()

def update_user_stats(user_id, stat_type):
    """تحديث إحصائيات المستخدم"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if stat_type == "game_played":
        c.execute('''INSERT INTO user_stats (user_id, games_played) 
                     VALUES (?, 1) 
                     ON CONFLICT(user_id) 
                     DO UPDATE SET games_played = games_played + 1''',
                  (user_id,))
    elif stat_type == "game_won":
        c.execute('''INSERT INTO user_stats (user_id, games_won) 
                     VALUES (?, 1) 
                     ON CONFLICT(user_id) 
                     DO UPDATE SET games_won = games_won + 1''',
                  (user_id,))
    
    conn.commit()
    conn.close()

# ==================== نظام المستويات ====================

LEVELS = [
    {"level": 1, "min_coins": 0, "name": "🟢 مبتدئ", "emoji": "🌱"},
    {"level": 2, "min_coins": 500, "name": "🔵 متقدم", "emoji": "📘"},
    {"level": 3, "min_coins": 2000, "name": "🟣 محترف", "emoji": "💜"},
    {"level": 4, "min_coins": 5000, "name": "🟠 خبير", "emoji": "🔥"},
    {"level": 5, "min_coins": 10000, "name": "🔴 أسطوري", "emoji": "👑"},
    {"level": 6, "min_coins": 25000, "name": "💎 خرافي", "emoji": "💎"},
]

def get_user_level(coins):
    """تحديد مستوى المستخدم بناءً على العملات"""
    for level in reversed(LEVELS):
        if coins >= level["min_coins"]:
            return level
    return LEVELS[0]

def get_level_progress(coins):
    """حساب نسبة التقدم للمستوى التالي"""
    current_level = get_user_level(coins)
    
    # البحث عن المستوى التالي
    next_level = None
    for level in LEVELS:
        if level["level"] == current_level["level"] + 1:
            next_level = level
            break
    
    if next_level:
        progress = (coins - current_level["min_coins"]) / (next_level["min_coins"] - current_level["min_coins"]) * 100
        progress = min(100, max(0, progress))
        return progress, next_level
    else:
        return 100, None  # أقصى مستوى

# ==================== نظام الإحالة ====================

async def generate_referral_code(user_id):
    """إنشاء كود إحالة للمستخدم"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result or not result[0]:
        # إنشاء كود جديد
        letters = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        ref_code = f"REF{user_id}{letters}"
        
        c.execute("UPDATE users SET referral_code = ? WHERE user_id = ?", (ref_code, user_id))
        conn.commit()
    else:
        ref_code = result[0]
    
    conn.close()
    return ref_code

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رابط الإحالة"""
    user_id = update.effective_user.id
    ref_code = await generate_referral_code(user_id)
    
    # رابط الإحالة
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    
    # إحصائيات الإحالات
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("📤 مشاركة الرابط", switch_inline_query=f"انضم إلي في هذا البوت الرائع! {referral_link}")],
        [InlineKeyboardButton("👥 أصدقائي المدعوين", callback_data="my_referrals")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]
    
    await update.message.reply_text(
        f"👥 **نظام الإحالة**\n\n"
        f"ادع أصدقاءك واربح 50 قطعة عن كل صديق!\n\n"
        f"📊 **إحصائياتك:**\n"
        f"• عدد المدعوين: {referrals_count}\n"
        f"• الأرباح من الدعوات: {referrals_count * 50} قطعة\n\n"
        f"🔗 **رابط الدعوة الخاص بك:**\n"
        f"`{referral_link}`\n\n"
        f"🎁 كل من يدخل عبر رابطك تحصل على 50 قطعة فوراً!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def my_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المدعوين"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT username, created_at FROM users 
                 WHERE referred_by = ? ORDER BY created_at DESC LIMIT 10''', (user_id,))
    referrals = c.fetchall()
    conn.close()
    
    if not referrals:
        await query.edit_message_text(
            "📭 لم تدع أي شخص بعد.\n"
            "شارك رابط الدعوة مع أصدقائك وابدأ الربح!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="referral")
            ]])
        )
        return
    
    text = "👥 **قائمة المدعوين:**\n\n"
    for i, (username, date) in enumerate(referrals, 1):
        name = username or "مستخدم"
        text += f"{i}. {name} - 📅 {date[:10]}\n"
    
    text += f"\n💰 إجمالي الأرباح: {len(referrals) * 50} قطعة"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="referral")]]
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== نظام التحديات اليومية ====================

DAILY_CHALLENGES = [
    {"id": 1, "name": "🎲 العب 3 ألعاب", "reward": 30, "target": 3, "type": "games", "emoji": "🎮"},
    {"id": 2, "name": "💰 اربح 100 قطعة", "reward": 20, "target": 100, "type": "earn", "emoji": "💵"},
    {"id": 3, "name": "🤝 ادع صديقاً", "reward": 50, "target": 1, "type": "referral", "emoji": "👥"},
    {"id": 4, "name": "🎯 اربح 5 ألعاب", "reward": 40, "target": 5, "type": "wins", "emoji": "🏆"},
    {"id": 5, "name": "⭐ سحب 50 قطعة", "reward": 25, "target": 50, "type": "withdraw", "emoji": "💸"},
    {"id": 6, "name": "📆 دوام 7 أيام", "reward": 100, "target": 7, "type": "streak", "emoji": "🔥"},
]

async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض التحديات اليومية"""
    user_id = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # اختيار 3 تحديات عشوائية لليوم
    import random
    today_challenges = random.sample(DAILY_CHALLENGES, min(3, len(DAILY_CHALLENGES)))
    
    text = "📋 **تحديات اليوم**\n\n"
    keyboard = []
    
    for challenge in today_challenges:
        # التحقق من التقدم
        c.execute('''SELECT progress, completed FROM user_challenges 
                     WHERE user_id = ? AND challenge_id = ? AND date = ?''',
                  (user_id, challenge['id'], today))
        result = c.fetchone()
        
        if result:
            progress, completed = result
        else:
            progress, completed = 0, False
            c.execute('''INSERT INTO user_challenges (user_id, challenge_id, date, progress, completed)
                         VALUES (?, ?, ?, ?, ?)''', (user_id, challenge['id'], today, 0, False))
        
        # شريط التقدم
        if not completed:
            percent = (progress / challenge['target']) * 100
            bar = "🟩" * int(percent/10) + "⬜" * (10 - int(percent/10))
            status = f"{bar} {progress}/{challenge['target']}"
        else:
            status = "✅ **مكتمل!**"
        
        text += f"{challenge['emoji']} **{challenge['name']}**\n"
        text += f"{status} - مكافأة: {challenge['reward']} قطعة\n\n"
    
    conn.commit()
    conn.close()
    
    keyboard.append([InlineKeyboardButton("🔄 تحديث", callback_data="refresh_challenges")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def update_challenge_progress(user_id, challenge_type, amount=1):
    """تحديث تقدم التحدي"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    for challenge in DAILY_CHALLENGES:
        if challenge['type'] == challenge_type:
            c.execute('''SELECT progress, completed FROM user_challenges 
                         WHERE user_id = ? AND challenge_id = ? AND date = ?''',
                      (user_id, challenge['id'], today))
            result = c.fetchone()
            
            if result and not result[1]:
                new_progress = result[0] + amount
                completed = new_progress >= challenge['target']
                
                c.execute('''UPDATE user_challenges 
                             SET progress = ?, completed = ?
                             WHERE user_id = ? AND challenge_id = ? AND date = ?''',
                          (new_progress, completed, user_id, challenge['id'], today))
                
                if completed:
                    update_user_coins(user_id, challenge['reward'])
                    # يمكن إضافة إشعار هنا
    
    conn.commit()
    conn.close()

# ==================== لعبة الحظ اليومي ====================

DAILY_LUCK_REWARDS = [10, 20, 30, 50, 100, 200, 500, 1000]

async def daily_luck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لعبة الحظ اليومي"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM daily_luck WHERE user_id = ? AND date = ?", (user_id, today))
    if c.fetchone():
        await query.edit_message_text(
            "❌ لعبت حظك اليوم بالفعل!\nعد غداً لحظ جديد 🍀",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
            ]])
        )
        conn.close()
        return
    
    # اختيار جائزة عشوائية (مع فرص متفاوتة)
    weights = [30, 25, 20, 10, 7, 4, 3, 1]  # فرص الحصول على كل جائزة
    prize = random.choices(DAILY_LUCK_REWARDS, weights=weights)[0]
    
    # إضافة الجائزة
    update_user_coins(user_id, prize)
    c.execute("INSERT INTO daily_luck (user_id, date, prize) VALUES (?, ?, ?)", 
              (user_id, today, prize))
    conn.commit()
    conn.close()
    
    # تأثير السحب
    slots = ["🍒", "🍊", "🍋", "7️⃣", "💎", "⭐"]
    result = [random.choice(slots) for _ in range(3)]
    
    # تحديث التحدي
    await update_challenge_progress(user_id, "earn", prize)
    
    await query.edit_message_text(
        f"🎰 **لعبة الحظ اليومي**\n\n"
        f"{' | '.join(result)}\n\n"
        f"🎉 **فزت بـ {prize} قطعة!**\n"
        f"💰 رصيدك الجديد: {get_user_coins(user_id)}\n\n"
        f"🍀 عد غداً لمحاولة جديدة!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
        ]])
    )

# ==================== نظام السحب ====================

WITHDRAWAL_METHODS = {
    "paypal": {"name": "PayPal 💰", "min": 500, "fee": 0.05},
    "crypto": {"name": "عملات رقمية ₿", "min": 500, "fee": 0.02},
    "vodafone": {"name": "فودافون كاش 📱", "min": 500, "fee": 0.03},
}

async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة السحب"""
    query = update.callback_query
    user_id = query.from_user.id
    coins = get_user_coins(user_id)
    
    keyboard = []
    for method_id, method in WITHDRAWAL_METHODS.items():
        keyboard.append([InlineKeyboardButton(
            f"{method['name']} (من {method['min']} قطعة)",
            callback_data=f"withdraw_{method_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("📜 طلباتي", callback_data="my_withdrawals")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    
    await query.edit_message_text(
        f"💸 **سحب الأرباح**\n\n"
        f"💰 رصيدك: {coins} قطعة (${coins/100:.2f})\n"
        f"📊 سعر الصرف: 100 قطعة = 1 دولار\n"
        f"⚡ الحد الأدنى: 500 قطعة (5$)\n\n"
        f"اختر طريقة السحب:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def process_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلب السحب"""
    query = update.callback_query
    await query.answer()
    
    method_id = query.data.replace('withdraw_', '')
    method = WITHDRAWAL_METHODS.get(method_id)
    context.user_data['withdraw_method'] = method_id
    
    await query.edit_message_text(
        f"💰 أدخل المبلغ بالقطع (الحد الأدنى {method['min']}):\n"
        f"مثال: 500 = 5 دولار\n\n"
        f"الطريقة: {method['name']}\n"
        f"الرسوم: {method['fee']*100}%",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="withdraw_menu")
        ]])
    )
    context.user_data['awaiting_amount'] = True

async def my_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض طلبات السحب السابقة"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT amount_coins, amount_usd, method, status, created_at 
                 FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC LIMIT 5''', 
              (user_id,))
    withdrawals = c.fetchall()
    conn.close()
    
    if not withdrawals:
        await query.edit_message_text(
            "📭 لا توجد طلبات سحب سابقة",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="withdraw_menu")
            ]])
        )
        return
    
    text = "📜 **طلبات السحب السابقة:**\n\n"
    for w in withdrawals:
        coins, usd, method, status, date = w
        status_emoji = {
            'pending': '⏳',
            'completed': '✅',
            'rejected': '❌'
        }.get(status, '❓')
        
        method_name = WITHDRAWAL_METHODS.get(method, {}).get('name', method)
        text += f"{status_emoji} {method_name}\n"
        text += f"   {coins} قطعة = ${usd:.2f} - {date[:10]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="withdraw_menu")]]
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== نظام المكافآت اليومية ====================

async def claim_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المطالبة بالمكافأة اليومية"""
    query = update.callback_query
    user_id = query.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # التحقق من أخذ المكافأة اليوم
    c.execute("SELECT * FROM daily_rewards WHERE user_id = ? AND date = ?", (user_id, today))
    
    if c.fetchone():
        await query.edit_message_text(
            "❌ لقد حصلت على مكافأتك اليومية بالفعل!\nعد غداً للمزيد 🌟",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
            ]])
        )
        conn.close()
        return
    
    # حساب الأيام المتتالية
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    c.execute("SELECT * FROM daily_rewards WHERE user_id = ? AND date = ?", (user_id, yesterday))
    had_yesterday = c.fetchone() is not None
    
    if had_yesterday:
        # حساب عدد الأيام المتتالية
        c.execute("SELECT COUNT(*) FROM daily_rewards WHERE user_id = ? ORDER BY date DESC", (user_id,))
        streak = c.fetchone()[0] + 1
    else:
        streak = 1
    
    # مكافأة أساسية + مكافأة إضافية حسب الأيام المتتالية
    base_reward = 50
    streak_bonus = min(streak * 5, 100)  # 5 قطع إضافية لكل يوم، حد أقصى 100
    total_reward = base_reward + streak_bonus
    
    # إضافة المكافأة
    update_user_coins(user_id, total_reward)
    c.execute("INSERT INTO daily_rewards (user_id, date) VALUES (?, ?)", (user_id, today))
    
    conn.commit()
    conn.close()
    
    # تحديث التحدي
    await update_challenge_progress(user_id, "streak", 1)
    
    # تأثيرات بصرية
    fire_emojis = ["🔥", "⚡", "✨", "🌟", "💫"]
    fire = random.choice(fire_emojis)
    
    await query.edit_message_text(
        f"{fire} **المكافأة اليومية** {fire}\n\n"
        f"✅ تم إضافة {total_reward} قطعة!\n"
        f"📦 الأساسي: {base_reward}\n"
        f"➕ مكافأة الاستمرار: +{streak_bonus}\n"
        f"🔥 أيام متتالية: {streak}\n\n"
        f"💰 رصيدك الجديد: {get_user_coins(user_id)}",
        parse_mode='Markdown'
    )

# ==================== الألعاب ====================

async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة الألعاب"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("🎲 تخمين الرقم", callback_data="game_guess")],
        [InlineKeyboardButton("🎰 حجر ورقة مقص", callback_data="game_rps_menu")],
        [InlineKeyboardButton("🎯 لعبة الحظ", callback_data="daily_luck")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🎮 **اختر لعبة:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def game_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لعبة تخمين الرقم"""
    query = update.callback_query
    await query.answer()
    
    # تخزين الرقم السري
    secret = random.randint(1, 10)
    context.user_data['secret_number'] = secret
    context.user_data['game_active'] = True
    
    keyboard = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"guess_{i}"))
        if i % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="games_menu")])
    
    await query.edit_message_text(
        "🔢 اختر رقماً من 1 إلى 10:\n"
        "🎁 الجائزة: 30 قطعة عند الفوز\n"
        "💸 العقوبة: -5 قطع عند الخسارة",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def game_rps_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة حجر ورقة مقص"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("🪨 حجر", callback_data="rps_rock")],
        [InlineKeyboardButton("📄 ورقة", callback_data="rps_paper")],
        [InlineKeyboardButton("✂️ مقص", callback_data="rps_scissors")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="games_menu")]
    ]
    
    await query.edit_message_text(
        "🎰 اختر:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== الإحصائيات المتقدمة ====================

async def advanced_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات متقدمة مع رسوم بيانية نصية"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # إحصائيات المستخدم
    c.execute('''SELECT games_played, games_won, total_earned FROM user_stats WHERE user_id = ?''', (user_id,))
    stats = c.fetchone()
    games_played = stats[0] if stats else 0
    games_won = stats[1] if stats else 0
    total_earned = stats[2] if stats else 0
    
    # إحصائيات السحوبات
    c.execute('''SELECT COUNT(*), SUM(amount_usd) FROM withdrawals WHERE user_id = ? AND status='completed' ''',
              (user_id,))
    withdraw_count, withdraw_total = c.fetchone()
    withdraw_count = withdraw_count or 0
    withdraw_total = withdraw_total or 0
    
    # الأيام المتتالية
    c.execute("SELECT COUNT(*) FROM daily_rewards WHERE user_id = ? ORDER BY date DESC", (user_id,))
    streak = c.fetchone()[0] or 0
    
    # الرصيد الحالي
    coins = get_user_coins(user_id)
    
    # الإحالات
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    referrals = c.fetchone()[0]
    
    conn.close()
    
    # المستوى
    level = get_user_level(coins)
    progress, next_level = get_level_progress(coins)
    
    # شريط التقدم
    progress_bar = "🟩" * int(progress/10) + "⬜" * (10 - int(progress/10))
    
    # حساب نسبة الفوز
    win_rate = (games_won / games_played * 100) if games_played > 0 else 0
    
    # رسم بياني للنشاط (آخر 7 أيام)
    activity_chart = ""
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%a")
        activity_chart += f"{day} "
    
    stats_text = f"""
📊 **إحصائيات متقدمة**

👤 **المستوى:** {level['emoji']} {level['name']}
📈 **التقدم:**
{progress_bar} {progress:.1f}%

💰 **الرصيد:** {coins} قطعة
💵 **إجمالي الأرباح:** {total_earned} قطعة
💸 **السحوبات:** {withdraw_count} (${withdraw_total:.2f})

🎮 **الألعاب:**
   • لعبت: {games_played}
   • فزت: {games_won}
   • نسبة فوز: {win_rate:.1f}%

👥 **الإحالات:** {referrals}
🔥 **أيام متتالية:** {streak}

{activity_chart}
✅ ✅ ✅ ✅ ✅ ⬜ ⬜
    """
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
    
    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== القوائم الرئيسية ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start ودخول الإحالات"""
    user = update.effective_user
    user_id = user.id
    
    # التحقق من وجود إحالة
    if context.args and context.args[0].startswith('ref_'):
        ref_code = context.args[0].replace('ref_', '')
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute("SELECT user_id FROM users WHERE referral_code = ?", (ref_code,))
        referrer = c.fetchone()
        
        if referrer and referrer[0] != user_id:
            # إضافة 50 قطعة للداعي
            update_user_coins(referrer[0], 50)
            c.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer[0], user_id))
            conn.commit()
            
            # إشعار الداعي
            try:
                await context.bot.send_message(
                    chat_id=referrer[0],
                    text=f"🎉 {user.first_name} انضم عبر رابطك!\nحصلت على 50 قطعة مكافأة!"
                )
            except:
                pass
        
        conn.close()
    
    # التأكد من وجود المستخدم
    coins = get_user_coins(user_id)
    level = get_user_level(coins)
    
    # رسالة ترحيب متحركة
    welcome_arts = ["🚀", "🤖", "🎮", "💰", "🌟", "✨"]
    welcome_art = random.choice(welcome_arts)
    
    keyboard = [
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
         InlineKeyboardButton("🎮 ألعاب", callback_data="games_menu")],
        [InlineKeyboardButton("💸 سحب أرباح", callback_data="withdraw_menu"),
         InlineKeyboardButton("🌟 مكافأة يومية", callback_data="daily")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
         InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="referral")],
        [InlineKeyboardButton("📋 تحديات", callback_data="challenges"),
         InlineKeyboardButton("🎰 لعبة الحظ", callback_data="daily_luck")],
        [InlineKeyboardButton("📤 مشاركة البوت", switch_inline_query="جرب هذا البوت الرائع! 🚀")]
    ]
    
    await update.message.reply_text(
        f"{welcome_art} **مرحباً {user.first_name}!**\n\n"
        f"🏆 **المستوى:** {level['emoji']} {level['name']}\n"
        f"💰 **رصيدك:** {coins} قطعة\n\n"
        f"📌 **ماذا تريد أن تفعل؟**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع الأزرار"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "balance":
        coins = get_user_coins(user_id)
        level = get_user_level(coins)
        await query.edit_message_text(
            f"💰 **رصيدك الحالي:** {coins} قطعة\n"
            f"🏆 **مستواك:** {level['emoji']} {level['name']}\n"
            f"💵 **يعادل:** ${coins/100:.2f}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
            ]])
        )
    
    elif data == "games_menu":
        await games_menu(update, context)
    
    elif data == "game_guess":
        await game_guess(update, context)
    
    elif data.startswith("guess_"):
        guess = int(data.replace("guess_", ""))
        secret = context.user_data.get('secret_number', 0)
        
        update_user_stats(user_id, "game_played")
        
        if guess == secret:
            update_user_coins(user_id, 30)
            update_user_stats(user_id, "game_won")
            await update_challenge_progress(user_id, "wins", 1)
            result = f"🎉 **أصبت!** الرقم كان {secret}\nكسبت 30 قطعة!"
        else:
            update_user_coins(user_id, -5)
            result = f"😢 **خطأ!** الرقم كان {secret}\nخسرت 5 قطع!"
        
        await update_challenge_progress(user_id, "games", 1)
        await update_challenge_progress(user_id, "earn", 30 if guess == secret else -5)
        
        context.user_data['game_active'] = False
        coins = get_user_coins(user_id)
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="games_menu")]]
        await query.edit_message_text(
            f"{result}\n💰 رصيدك الآن: {coins}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == "game_rps_menu":
        await game_rps_menu(update, context)
    
    elif data.startswith("rps_"):
        user_choice = data.replace("rps_", "")
        bot_choice = random.choice(["rock", "paper", "scissors"])
        
        choices = {
            "rock": "🪨 حجر",
            "paper": "📄 ورقة", 
            "scissors": "✂️ مقص"
        }
        
        update_user_stats(user_id, "game_played")
        await update_challenge_progress(user_id, "games", 1)
        
        if user_choice == bot_choice:
            result = "🤝 **تعادل!**"
            coins_change = 5  # تعويض بسيط
        elif ((user_choice == "rock" and bot_choice == "scissors") or
              (user_choice == "paper" and bot_choice == "rock") or
              (user_choice == "scissors" and bot_choice == "paper")):
            result = "🎉 **فوز!**"
            coins_change = 20
            update_user_stats(user_id, "game_won")
            await update_challenge_progress(user_id, "wins", 1)
        else:
            result = "😢 **خسارة!**"
            coins_change = -10
        
        update_user_coins(user_id, coins_change)
        await update_challenge_progress(user_id, "earn", coins_change)
        
        coins = get_user_coins(user_id)
        
        await query.edit_message_text(
            f"🎮 **حجر - ورقة - مقص**\n\n"
            f"اخترت: {choices[user_choice]}\n"
            f"البوت اختار: {choices[bot_choice]}\n\n"
            f"{result}\n"
            f"{'+' if coins_change > 0 else ''}{coins_change} قطعة\n"
            f"💰 رصيدك: {coins}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 العب مرة أخرى", callback_data="game_rps_menu"),
                InlineKeyboardButton("🔙 رجوع", callback_data="games_menu")
            ]])
        )
    
    elif data == "daily_luck":
        await daily_luck(update, context)
    
    elif data == "withdraw_menu":
        await withdraw_menu(update, context)
    
    elif data.startswith("withdraw_"):
        await process_withdrawal(update, context)
    
    elif data == "my_withdrawals":
        await my_withdrawals(update, context)
    
    elif data == "daily":
        await claim_daily(update, context)
    
    elif data == "stats":
        await advanced_stats(update, context)
    
    elif data == "referral":
        await referral_command(query, context)
    
    elif data == "my_referrals":
        await my_referrals(update, context)
    
    elif data == "challenges":
        await challenges_command(query, context)
    
    elif data == "refresh_challenges":
        await challenges_command(query, context)
    
    elif data == "back_main":
        await start(update, context)

# ==================== معالجة الرسائل النصية ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_id = update.effective_user.id
    
    # معالجة إدخال مبلغ السحب
    if context.user_data.get('awaiting_amount'):
        try:
            amount = int(update.message.text)
            coins = get_user_coins(user_id)
            method_id = context.user_data.get('withdraw_method', 'paypal')
            method = WITHDRAWAL_METHODS.get(method_id, {})
            
            if amount < method.get('min', 500):
                await update.message.reply_text(f"❌ الحد الأدنى {method.get('min', 500)} قطعة")
            elif amount > coins:
                await update.message.reply_text(f"❌ رصيدك غير كافٍ! لديك {coins} قطعة")
            else:
                context.user_data['withdraw_amount'] = amount
                context.user_data['awaiting_details'] = True
                context.user_data['awaiting_amount'] = False
                
                if method_id == 'paypal':
                    await update.message.reply_text("📧 أرسل بريد PayPal الإلكتروني:")
                elif method_id == 'crypto':
                    await update.message.reply_text("🔑 أرسل عنوان محفظتك الرقمية (USDT):")
                elif method_id == 'vodafone':
                    await update.message.reply_text("📱 أرسل رقم فودافون كاش:")
                    
        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال رقم صحيح")
    
    # معالجة تفاصيل السحب
    elif context.user_data.get('awaiting_details'):
        details = update.message.text
        user_id = update.effective_user.id
        amount = context.user_data.get('withdraw_amount', 0)
        method_id = context.user_data.get('withdraw_method', 'paypal')
        method = WITHDRAWAL_METHODS.get(method_id, {})
        
        # حساب المبلغ بالدولار
        amount_usd = amount / 100
        fee = amount_usd * method.get('fee', 0.05)
        net_amount = amount_usd - fee
        
        # حفظ في قاعدة البيانات
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT INTO withdrawals 
                     (user_id, amount_coins, amount_usd, method, details, status)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, amount, amount_usd, method_id, details, 'pending'))
        
        # خصم الرصيد
        c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
        
        conn.commit()
        withdrawal_id = c.lastrowid
        conn.close()
        
        # تحديث التحدي
        await update_challenge_progress(user_id, "withdraw", amount)
        
        await update.message.reply_text(
            f"✅ **تم تقديم طلب السحب بنجاح!**\n\n"
            f"📋 رقم الطلب: `{withdrawal_id}`\n"
            f"💰 المبلغ: {amount} قطعة (${amount_usd:.2f})\n"
            f"📊 الرسوم: ${fee:.2f}\n"
            f"💵 الصافي: ${net_amount:.2f}\n"
            f"⏳ الحالة: قيد المراجعة\n\n"
            f"سيتم معالجة الطلب خلال 24 ساعة.",
            parse_mode='Markdown'
        )
        
        # تنظيف البيانات
        context.user_data.pop('awaiting_details', None)
        context.user_data.pop('withdraw_amount', None)
        context.user_data.pop('withdraw_method', None)
    
    else:
        # رسالة افتراضية
        await update.message.reply_text(
            "استخدم /start للبدء",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 ابدأ", callback_data="back_main")
            ]])
        )

# ==================== التشغيل الرئيسي ====================

def main():
    """تشغيل البوت"""
    print("🤖 بدء تشغيل البوت المتكامل...")
    print(f"📱 توكن البوت: {TOKEN[:10]}...")
    print("⏳ جاري الاتصال بتليجرام...")
    
    app = Application.builder().token(TOKEN).build()
    
    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("daily", lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("challenges", lambda u,c: challenges_command(u,c)))
    
    # الأزرار
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت يعمل بنجاح!")
    print("📱 اضغط Ctrl+C للإيقاف")
    
    app.run_polling()

if __name__ == '__main__':
    main()
