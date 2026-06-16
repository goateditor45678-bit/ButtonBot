import os, math
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 7037415424

user_photos = {}
collage_mode = set()
post_data = {}

def owner_only(update: Update):
    return update.effective_user and update.effective_user.id == OWNER_ID

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 Create Image Buttons Post", callback_data="create_post")],
        [InlineKeyboardButton("📸 Collage", callback_data="collage")],
        [InlineKeyboardButton("✅ Finish", callback_data="finish"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])

def yes_no_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Button", callback_data="add_btn")],
        [InlineKeyboardButton("✅ Finish Post", callback_data="finish_post")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update):
        await update.message.reply_text("⛔ Access denied.")
        return
    await update.message.reply_text("🔥 Button Bot Menu", reply_markup=menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update): return
    await update.message.reply_text(
        "🖼 Create Post: image + caption + many link buttons\n"
        "📸 Collage: send photos then Finish\n"
        "❌ Cancel: stop current work",
        reply_markup=menu()
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        await query.message.reply_text("⛔ Access denied.")
        return

    uid = query.from_user.id
    data = query.data

    if data == "create_post":
        post_data[uid] = {"step": "image", "image": None, "caption": None, "buttons": []}
        await query.message.reply_text("🖼 Send image for post.")

    elif data == "add_btn":
        if uid not in post_data:
            await query.message.reply_text("Start post first.", reply_markup=menu())
            return
        post_data[uid]["step"] = "button_text"
        await query.message.reply_text("Button name anupu da.")

    elif data == "finish_post":
        await finish_post(query.message, uid)

    elif data == "collage":
        collage_mode.add(uid)
        user_photos[uid] = []
        await query.message.reply_text("📸 Collage mode started. Send photos.", reply_markup=menu())

    elif data == "finish":
        await create_collage(query.message, context, uid)

    elif data == "cancel":
        collage_mode.discard(uid)
        user_photos.pop(uid, None)
        post_data.pop(uid, None)
        await query.message.reply_text("❌ Cancelled.", reply_markup=menu())

    elif data == "help":
        await query.message.reply_text("Use menu buttons da.", reply_markup=menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update): return
    uid = update.effective_user.id
    text = update.message.text

    if uid not in post_data:
        await update.message.reply_text("Use /start menu.", reply_markup=menu())
        return

    data = post_data[uid]

    if data["step"] == "caption":
        data["caption"] = text
        data["step"] = "button_text"
        await update.message.reply_text("Button name anupu da.")

    elif data["step"] == "button_text":
        data["temp_button_text"] = text
        data["step"] = "button_url"
        await update.message.reply_text("Ippo button link anupu da.")

    elif data["step"] == "button_url":
        btn_text = data.pop("temp_button_text")
        data["buttons"].append((btn_text, text))
        data["step"] = "more_buttons"
        await update.message.reply_text("Button added ✅", reply_markup=yes_no_menu())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update): return
    uid = update.effective_user.id

    if uid in post_data and post_data[uid]["step"] == "image":
        post_data[uid]["image"] = update.message.photo[-1].file_id
        post_data[uid]["step"] = "caption"
        await update.message.reply_text("Image saved ✅ Caption anupu da.")
        return

    if uid in collage_mode:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        data = await file.download_as_bytearray()
        img = Image.open(BytesIO(data)).convert("RGB")
        user_photos.setdefault(uid, []).append(img)
        await update.message.reply_text(f"✅ Photo added: {len(user_photos[uid])}", reply_markup=menu())
        return

    await update.message.reply_text("Use menu first da.", reply_markup=menu())

async def finish_post(message, uid):
    data = post_data.get(uid)
    if not data or not data["image"] or not data["caption"]:
        await message.reply_text("Post incomplete da.", reply_markup=menu())
        return

    buttons = [[InlineKeyboardButton(t, url=u)] for t, u in data["buttons"]]
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    await message.reply_photo(
        photo=data["image"],
        caption=data["caption"],
        reply_markup=markup
    )

    post_data.pop(uid, None)
    await message.reply_text("✅ Post ready!", reply_markup=menu())

async def create_collage(message, context, uid):
    photos = user_photos.get(uid, [])
    if not photos:
        await message.reply_text("No photos added da.", reply_markup=menu())
        return

    count = len(photos)
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    size = 500

    collage = Image.new("RGB", (cols * size, rows * size), "white")

    for i, img in enumerate(photos):
        img.thumbnail((size, size))
        x = (i % cols) * size + (size - img.width) // 2
        y = (i // cols) * size + (size - img.height) // 2
        collage.paste(img, (x, y))

    output = BytesIO()
    output.name = "collage.jpg"
    collage.save(output, "JPEG", quality=95)
    output.seek(0)

    await message.reply_photo(photo=output, caption=f"✅ Collage ready! Total photos: {count}")
    collage_mode.discard(uid)
    user_photos.pop(uid, None)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Button Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()