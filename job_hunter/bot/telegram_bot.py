import logging
import asyncio
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from job_hunter.config import settings
from job_hunter.db.database import Database
from job_hunter.ai.scorer import JobScorer
from job_hunter.models import JobStatus, Job, UserProfile
from job_hunter.scrapers import get_all_scrapers

logger = logging.getLogger(__name__)

class JobHunterBot:
    def __init__(self, db: Database, scorer: JobScorer, profile: UserProfile):
        self.db = db
        self.scorer = scorer
        self.profile = profile
        self.app = Application.builder().token(settings.telegram_bot_token).build()
        self.chat_id = settings.telegram_chat_id
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("top", self.cmd_top))
        self.app.add_handler(CommandHandler("search", self.cmd_search))
        self.app.add_handler(CommandHandler("profile", self.cmd_profile))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start(self):
        """Starts the bot. Blocks until interrupted."""
        logger.info("Starting Telegram Bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        # Wait forever
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def notify_job(self, job: Job):
        if not self.chat_id:
            logger.warning("No Telegram chat ID configured for notifications")
            return
            
        score = job.match_score
        score_val = score.overall_score if score else 0
        
        emoji = "🟢" if score_val >= 85 else "🟡" if score_val >= 70 else "🔴"
        
        text = f"{emoji} <b>New Match: {job.company}</b>\n\n"
        text += f"<b>Title:</b> {job.title}\n"
        if job.salary_min:
            text += f"<b>Salary:</b> {job.salary_min} - {job.salary_max} {job.salary_currency}\n"
        text += f"<b>Match Score:</b> {score_val}/100\n\n"
        
        if score:
            if score.pros:
                text += f"<b>Pros:</b>\n" + "\n".join([f"• {p}" for p in score.pros[:3]]) + "\n\n"
            if score.cons:
                text += f"<b>Cons:</b>\n" + "\n".join([f"• {c}" for c in score.cons[:3]]) + "\n\n"
        
        text += f"<a href='{job.url}'>Link to Job</a>"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Apply", callback_data=f"apply_{job.id}"),
                InlineKeyboardButton("❌ Skip", callback_data=f"skip_{job.id}")
            ],
            [
                InlineKeyboardButton("📋 Details", callback_data=f"details_{job.id}"),
                InlineKeyboardButton("📝 Cover Letter", callback_data=f"cl_{job.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    # --- Handlers ---
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👋 Welcome to Job Hunter Bot! I will notify you of great matches.\nType /help for commands.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🤖 <b>Available Commands:</b>\n"
            "/start - Welcome message\n"
            "/stats - Show discovery stats\n"
            "/top - Show top 10 matching jobs\n"
            "/search &lt;keyword&gt; - Immediate scrape\n"
            "/profile - Show profile\n"
            "/help - Show commands"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = await self.db.get_stats()
        text = "📊 <b>Job Statistics:</b>\n\n"
        for k, v in stats.items():
            text += f"<b>{k.replace('_', ' ').title()}:</b> {v}\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        jobs = await self.db.get_top_matches(min_score=0, limit=10)
        if not jobs:
            await update.message.reply_text("No jobs scored yet.")
            return
            
        for job in jobs:
            await self.notify_job(job)

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Please provide a keyword: /search <keyword>")
            return
            
        keyword = " ".join(context.args)
        await update.message.reply_text(f"🔍 Starting background scrape for: '{keyword}'")
        
        asyncio.create_task(self._run_bg_scrape([keyword]))

    async def _run_bg_scrape(self, keywords: list[str]):
        scrapers = get_all_scrapers()
        all_jobs = []
        tasks = [scraper.safe_scrape(keywords) for scraper in scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
                
        new_count = 0
        for job in all_jobs:
            if await self.db.insert_job(job):
                new_count += 1
                
        if self.chat_id:
            await self.app.bot.send_message(self.chat_id, f"✅ Scrape finished! Found {new_count} new jobs. They will be scored soon.")

    async def cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        p = self.profile
        text = (
            f"👤 <b>{p.name}</b>\n"
            f"<b>Target:</b> {', '.join(p.target_titles)}\n"
            f"<b>Skills:</b> {', '.join(p.skills)}\n"
            f"<b>Exp:</b> {p.experience_years} years\n"
            f"<b>Remote Only:</b> {p.remote_only}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        
        parts = data.split("_")
        if len(parts) < 2:
            return
            
        action, job_id_str = parts[0], parts[1]
        try:
            job_id = int(job_id_str)
        except ValueError:
            return

        if action == "apply":
            await self.db.update_job_status(job_id, JobStatus.APPROVED)
            await query.edit_message_text(f"{query.message.text}\n\n✅ <b>APPROVED</b> — Ready for application!", parse_mode=ParseMode.HTML)
        elif action == "skip":
            await self.db.update_job_status(job_id, JobStatus.SKIPPED)
            await query.edit_message_text(f"{query.message.text}\n\n❌ <b>SKIPPED</b>", parse_mode=ParseMode.HTML)
        elif action == "details":
            await self._send_details(query, job_id)
        elif action == "cl":
            await self._send_cover_letter(query, job_id)

    async def _send_details(self, query, job_id: int):
        """Send full job description."""
        job = await self.db.get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("⚠️ Job not found in database.")
            return

        text = f"📋 <b>{job.title}</b> @ {job.company}\n\n"
        desc = job.description[:3800]  # Telegram 4096 char limit
        text += f"<pre>{desc}</pre>"
        if len(job.description) > 3800:
            text += f"\n\n... <i>(truncated, {len(job.description)} chars total)</i>"
        text += f"\n\n🔗 <a href='{job.url}'>View Original</a>"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    async def _send_cover_letter(self, query, job_id: int):
        """Generate and send a tailored cover letter."""
        job = await self.db.get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("⚠️ Job not found in database.")
            return

        await query.message.reply_text("📝 Generating tailored cover letter...")
        cover_letter = await self.scorer.generate_cover_letter(job)
        text = f"📝 <b>Cover Letter for {job.title} @ {job.company}</b>\n\n{cover_letter[:3900]}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)

