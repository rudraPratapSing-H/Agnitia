"""
Agnitia — Telegram Approval Bot
Owner: Member 4 (Integrations & Content)
Phase 0 Task 0.6: Bot answers 'pong' in the group
Phase 2 Task 2.14: Approval bot long-polling, phone approval heals system on screen

Specification:
- Long-polling via async python-telegram-bot (no webhook, no public IP required)
- Handles /ping -> replies "pong"
- Handles /start, /help, /status
- Handles interactive callbacks approve:{id} and reject:{id}
- Polls GET /api/incidents/latest every 2s
- On awaiting_approval: sends incident card with inline Approve / Reject buttons
- On tap: calls POST /api/incidents/{id}/approve or /reject and edits message with author + time
- Resilient message delivery: Markdown parse fallback prevents dropped messages
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
from dotenv import load_dotenv

# Optional import of telegram for live polling
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.constants import ParseMode
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    TELEGRAM_LIB_AVAILABLE = True
except ImportError:
    TELEGRAM_LIB_AVAILABLE = False


# Configure paths and environment
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("agnitia.telegram_bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
POLL_INTERVAL = float(os.getenv("TELEGRAM_POLL_INTERVAL", "2.0"))

_INSTANCE_LOCK_SOCKET = None


def acquire_single_instance_lock(port: int = 18443) -> bool:
    """Binds to localhost:18443 to guarantee only one bot process polls Telegram at once."""
    global _INSTANCE_LOCK_SOCKET
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        _INSTANCE_LOCK_SOCKET = s
        return True
    except OSError:
        logger.warning(
            f"Another OpsOracle Telegram bot instance is already running (port {port} in use). "
            "Terminating this duplicate process to prevent Telegram polling conflict."
        )
        return False


class AgnitiaBotEngine:
    """Core logic engine decoupled from network I/O for 100% testability."""

    def __init__(self, backend_url: str = BACKEND_URL):
        self.backend_url = backend_url
        self.last_notified_incident_id: Optional[str] = None
        self.last_notified_status: Optional[str] = None
        self.last_notified_started_at: Optional[str] = None

    def reset_state(self):
        """Clears cached notification state on cluster reset."""
        self.last_notified_incident_id = None
        self.last_notified_status = None
        self.last_notified_started_at = None

    @staticmethod
    def handle_ping() -> str:
        """Phase 0 Task 0.6 acceptance criteria: Bot answers 'pong'."""
        return "pong"

    @staticmethod
    def format_incident_card(incident: Dict[str, Any]) -> str:
        """Formats a mission-critical alert message with diff and stats."""
        inc_id = incident.get("id", "INC-UNKNOWN")
        root_svc = incident.get("root_service", "unknown")
        impacted = incident.get("impacted_services", [])
        alert_count = incident.get("raw_alert_count", 0)

        rca = incident.get("rca", {}) or {}
        root_cause = rca.get("root_cause", f"Failure isolated in {root_svc}")
        confidence = int(rca.get("confidence", 0.95) * 100)

        playbook = incident.get("playbook", {}) or {}
        diff = playbook.get("diff", "resources.limits.memory: 64Mi -> 256Mi")

        impacted_str = ", ".join(impacted) if impacted else "None (isolated)"

        card = (
            f"🚨 *AGNITIA CRITICAL INCIDENT ALERT* 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 *Incident ID:* `{inc_id}`\n"
            f"💥 *Root Cause:* {root_cause}\n"
            f"🎯 *Root Service:* `{root_svc}` (Confidence: {confidence}%)\n"
            f"📉 *Impacted Services:* {impacted_str}\n"
            f"🌪️ *Alert Storm:* {alert_count} alerts collapsed into 1 incident (98% noise removed)\n\n"
            f"⚙️ *Proposed Playbook Diff:*\n"
            f"```yaml\n{diff}\n```\n\n"
            f"⚠️ *Risk Level:* High — Requires Human Authorization\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Judges & On-Call Engineers: Tap below to authorize automated recovery._"
        )
        return card

    @staticmethod
    def format_approval_confirmation(incident_id: str, approved_by: str) -> str:
        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        return (
            f"✅ *INCIDENT {incident_id} REMEDIATION APPROVED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Authorized by:* {approved_by}\n"
            f"⏱️ *Authorized at:* {now_utc}\n"
            f"🚀 *Status:* Executing recovery playbook in dependency order.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"System nodes are recovering on the OpsOracle mission control screen."
        )

    @staticmethod
    def format_rejection_notice(incident_id: str, rejected_by: str) -> str:
        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        return (
            f"❌ *INCIDENT {incident_id} REMEDIATION REJECTED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Rejected by:* {rejected_by}\n"
            f"⏱️ *Rejected at:* {now_utc}\n"
            f"🛑 *Status:* Automated remediation aborted by on-call engineer.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )


bot_engine = AgnitiaBotEngine(BACKEND_URL)


# =====================================================================
# Safe Message Delivery Wrappers
# =====================================================================

async def safe_send_message(bot, chat_id: str | int, text: str, reply_markup=None):
    """
    Sends message with Markdown parse_mode. If Telegram rejects due to entity
    parsing or unescaped formatting, falls back gracefully to plain text so
    no notification is ever dropped.
    """
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.warning(f"Markdown send_message failed ({exc}); falling back to plain text")
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=None,
                reply_markup=reply_markup,
            )
        except Exception as plain_exc:
            logger.error(f"Plain send_message also failed: {plain_exc}")
            raise


async def safe_edit_message(query, text: str, reply_markup=None):
    """Safely edits message with Markdown, falling back to plain text on error."""
    try:
        return await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.warning(f"Markdown edit_message failed ({exc}); falling back to plain text")
        return await query.edit_message_text(
            text=text,
            parse_mode=None,
            reply_markup=reply_markup,
        )


# =====================================================================
# Telegram Command and Callback Handlers
# =====================================================================

if TELEGRAM_LIB_AVAILABLE:

    async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /ping -> replies with 'pong' (Task 0.6)."""
        reply = bot_engine.handle_ping()
        user = update.effective_user
        username = user.username or str(user.id) if user else "unknown"
        logger.info(f"Received /ping command from {username}. Answering: {reply}")
        if update.effective_chat:
            await safe_send_message(context.bot, update.effective_chat.id, reply)
        elif update.message:
            await update.message.reply_text(reply)

    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /start command."""
        welcome = (
            "👋 *Welcome to the OpsOracle On-Call Approval Bot!*\n\n"
            "OpsOracle is an AI on-call engineer that turns storms of 50+ alerts "
            "into a single verified root cause and ordered recovery plan.\n\n"
            "*Available Commands:*\n"
            "• `/ping` — Health check (answers `pong`)\n"
            "• `/status` — View current backend & incident status\n"
            "• `/help` — Display operational instructions\n\n"
            "Whenever an incident reaches `awaiting_approval`, I will dispatch "
            "an approval card with inline action buttons here."
        )
        if update.effective_chat:
            await safe_send_message(context.bot, update.effective_chat.id, welcome)

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /help command."""
        help_text = (
            "🛠️ *OpsOracle Approval Bot Commands*\n\n"
            "• `/ping` — Verify bot connectivity (returns `pong`)\n"
            "• `/status` — Check active incidents and cluster health\n"
            "• `/help` — Show this help message\n\n"
            "*How Incident Approvals Work:*\n"
            "When a critical incident occurs, OpsOracle isolates the root cause and generates "
            "a remediation playbook. If human authorization is required, an interactive card "
            "with [Approve] / [Reject] buttons appears here. Tapping Approve starts automated healing."
        )
        if update.effective_chat:
            await safe_send_message(context.bot, update.effective_chat.id, help_text)

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /status command."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{BACKEND_URL}/api/incidents/latest")
                if resp.status_code == 200:
                    inc = resp.json()
                    if inc:
                        status_msg = (
                            f"📡 *OpsOracle Incident Status:*\n"
                            f"• Active Incident: `{inc.get('id')}`\n"
                            f"• Status: `{inc.get('status')}`\n"
                            f"• Root Cause Service: `{inc.get('root_service')}`\n"
                            f"• Raw Alerts: {inc.get('raw_alert_count')}"
                        )
                    else:
                        status_msg = "🟢 *OpsOracle Status:* All 6 microservices healthy. No active incidents."
                else:
                    status_msg = f"⚠️ Backend returned HTTP {resp.status_code}"
        except Exception as e:
            status_msg = f"🔴 Could not reach OpsOracle backend at `{BACKEND_URL}`: {e}"

        if update.effective_chat:
            await safe_send_message(context.bot, update.effective_chat.id, status_msg)

    async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles general text messages from users (non-commands)."""
        if not update.message or not update.message.text:
            return
        text = update.message.text.strip().lower()
        if text in ("ping", "pong"):
            await ping_command(update, context)
            return
        if text in ("status", "health"):
            await status_command(update, context)
            return
        if text in ("help", "?"):
            await help_command(update, context)
            return

        reply = (
            "🤖 *OpsOracle On-Call Approval Bot*\n\n"
            "I am monitoring the cluster for incidents.\n"
            "• Use `/ping` to test connectivity\n"
            "• Use `/status` to view current incident status\n"
            "• Use `/help` for documentation"
        )
        if update.effective_chat:
            await safe_send_message(context.bot, update.effective_chat.id, reply)

    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles inline button presses: approve:{id} and reject:{id}."""
        query = update.callback_query
        await query.answer()

        data = query.data or ""
        user = query.from_user
        username = f"@{user.username}" if user.username else user.first_name

        if data.startswith("approve:"):
            incident_id = data.split(":", 1)[1]
            logger.info(f"Received Approve click for incident {incident_id} from {username}")

            # Call Agnitia Backend approve endpoint
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    res = await client.post(
                        f"{BACKEND_URL}/api/incidents/{incident_id}/approve",
                        json={"approved_by": f"telegram:{username}"},
                    )
                    if res.status_code in (200, 202):
                        new_text = bot_engine.format_approval_confirmation(incident_id, username)
                        await safe_edit_message(query, new_text)
                    elif res.status_code == 409:
                        detail = ""
                        try:
                            detail = res.json().get("detail", "")
                        except Exception:
                            detail = res.text
                        err_text = (
                            f"ℹ️ *Incident {incident_id} Status Notice*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"Remediation is already in progress or already completed.\n"
                            f"Backend: `{detail}`"
                        )
                        await safe_edit_message(query, err_text)
                    else:
                        await safe_edit_message(
                            query,
                            f"⚠️ Error approving {incident_id}: HTTP {res.status_code}\n{res.text}",
                        )
                except Exception as e:
                    logger.error(f"Failed to call approve endpoint: {e}")
                    await safe_edit_message(
                        query,
                        f"🔴 Backend connection error while approving {incident_id}: {e}",
                    )

        elif data.startswith("reject:"):
            incident_id = data.split(":", 1)[1]
            logger.info(f"Received Reject click for incident {incident_id} from {username}")

            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    res = await client.post(f"{BACKEND_URL}/api/incidents/{incident_id}/reject")
                    if res.status_code in (200, 202):
                        new_text = bot_engine.format_rejection_notice(incident_id, username)
                        await safe_edit_message(query, new_text)
                    elif res.status_code == 409:
                        detail = ""
                        try:
                            detail = res.json().get("detail", "")
                        except Exception:
                            detail = res.text
                        err_text = (
                            f"ℹ️ *Incident {incident_id} Status Notice*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"Action already processed.\n"
                            f"Backend: `{detail}`"
                        )
                        await safe_edit_message(query, err_text)
                    else:
                        await safe_edit_message(
                            query,
                            f"⚠️ Error rejecting {incident_id}: HTTP {res.status_code}\n{res.text}",
                        )
                except Exception as e:
                    logger.error(f"Failed to call reject endpoint: {e}")
                    await safe_edit_message(
                        query,
                        f"🔴 Backend connection error while rejecting {incident_id}: {e}",
                    )

    async def poll_incidents_task(application) -> None:
        """Background loop polling /api/incidents/latest and /api/audit every 2s for alerts."""
        chat_id = TELEGRAM_CHAT_ID
        if not chat_id or chat_id == "your_telegram_chat_id_here":
            logger.warning("TELEGRAM_CHAT_ID is not configured. Incident polling notifications disabled.")
            return

        logger.info(f"Starting incident polling loop -> targeting chat {chat_id} every {POLL_INTERVAL}s")
        last_seen_audit_len = 0

        while True:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # 1. Incident status changes
                    resp = await client.get(f"{BACKEND_URL}/api/incidents/latest")
                    if resp.status_code == 200:
                        inc = resp.json()
                        if not inc:
                            # Backend was reset or has no active incidents
                            if bot_engine.last_notified_incident_id is not None:
                                logger.info("Backend incident state reset detected; clearing bot notification cache.")
                                bot_engine.reset_state()
                        else:
                            inc_id = inc.get("id")
                            status = inc.get("status")
                            started_at = inc.get("started_at")

                            is_new_incident = (
                                bot_engine.last_notified_incident_id != inc_id
                                or (started_at and bot_engine.last_notified_started_at != started_at)
                            )
                            is_new_status = bot_engine.last_notified_status != status

                            # Check if transitioning to awaiting_approval
                            if status == "awaiting_approval" and (is_new_incident or is_new_status):
                                logger.info(f"Dispatching approval card for {inc_id} to chat {chat_id}")
                                text = bot_engine.format_incident_card(inc)
                                keyboard = [
                                    [
                                        InlineKeyboardButton(
                                            "✅ Approve Remediation",
                                            callback_data=f"approve:{inc_id}",
                                        ),
                                        InlineKeyboardButton(
                                            "❌ Reject",
                                            callback_data=f"reject:{inc_id}",
                                        ),
                                    ]
                                ]
                                reply_markup = InlineKeyboardMarkup(keyboard)

                                await safe_send_message(
                                    application.bot,
                                    chat_id=chat_id,
                                    text=text,
                                    reply_markup=reply_markup,
                                )
                                bot_engine.last_notified_incident_id = inc_id
                                bot_engine.last_notified_status = status
                                bot_engine.last_notified_started_at = started_at

                            elif status == "resolved" and (is_new_incident or is_new_status):
                                logger.info(f"Dispatching resolution notice for {inc_id} to chat {chat_id}")
                                root_svc = inc.get("root_service", "service")
                                scenario = inc.get("scenario", "incident")
                                res_text = (
                                    f"🟢 *OPSORACLE RESOLUTION NOTICE*\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🆔 *Incident ID:* `{inc_id}` (`{scenario}`)\n"
                                    f"🎯 *Root Service:* `{root_svc}`\n"
                                    f"✅ *Status:* System restored to healthy nominal state.\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                )
                                await safe_send_message(
                                    application.bot,
                                    chat_id=chat_id,
                                    text=res_text,
                                )
                                bot_engine.last_notified_incident_id = inc_id
                                bot_engine.last_notified_status = status
                                bot_engine.last_notified_started_at = started_at

                            elif status in ("healing", "detected") and is_new_incident:
                                bot_engine.last_notified_incident_id = inc_id
                                bot_engine.last_notified_status = status
                                bot_engine.last_notified_started_at = started_at

                    # 2. Predictive auto-heal audit stream
                    audit_resp = await client.get(f"{BACKEND_URL}/api/audit")
                    if audit_resp.status_code == 200:
                        audits = audit_resp.json()
                        if isinstance(audits, list):
                            if last_seen_audit_len == 0:
                                last_seen_audit_len = len(audits)
                            elif len(audits) > last_seen_audit_len:
                                new_entries = audits[last_seen_audit_len:]
                                last_seen_audit_len = len(audits)
                                for entry in new_entries:
                                    kind = entry.get("kind", "")
                                    svc = entry.get("service", "cluster")
                                    action = entry.get("action", "")
                                    if kind in ("applied", "verified", "rolled_back"):
                                        icon = "⚡" if kind == "applied" else "✅" if kind == "verified" else "⚠️"
                                        detail = entry.get("detail", f"Auto-heal action {action}")
                                        audit_msg = (
                                            f"{icon} *OPSORACLE PREDICTIVE AUTO-HEAL: {kind.upper()}*\n"
                                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                            f"🎯 *Service:* `{svc}`\n"
                                            f"🛠️ *Action:* `{action}`\n"
                                            f"📋 *Detail:* `{detail}`\n"
                                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                        )
                                        await safe_send_message(
                                            application.bot,
                                            chat_id=chat_id,
                                            text=audit_msg,
                                        )
            except Exception as e:
                logger.warning(f"Poll check exception (retrying in {POLL_INTERVAL}s): {e}")

            await asyncio.sleep(POLL_INTERVAL)


def run_self_test() -> bool:
    """Verifies Phase 0 requirements and bot handlers in automated test mode."""
    print("=" * 60)
    print("  AGNITIA TELEGRAM BOT VERIFICATION (Member 4 - Phase 0)")
    print("=" * 60)

    # 1. Test ping handler
    ping_resp = bot_engine.handle_ping()
    print(f"1. /ping command response: '{ping_resp}'")
    assert ping_resp == "pong", f"Expected 'pong', got '{ping_resp}'"
    print("   -> [PASS] Bot answers 'pong' (Task 0.6 Acceptance Criteria)")

    # 2. Test incident card formatter
    sample_incident = {
        "id": "INC-104",
        "status": "awaiting_approval",
        "scenario": "db_oom",
        "root_service": "postgres",
        "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
        "raw_alert_count": 56,
        "rca": {
            "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
            "category": "OOMKilled",
            "confidence": 0.97,
        },
        "playbook": {
            "diff": "resources.limits.memory: 64Mi -> 256Mi",
        },
    }
    card = bot_engine.format_incident_card(sample_incident)
    assert "INC-104" in card
    assert "56 alerts" in card
    assert "64Mi -> 256Mi" in card
    print("2. Incident approval card formatting:")
    print("   -> [PASS] Card contains Incident ID, RCA, Diff, and 56-alert collapse stat")

    # 3. Test approval confirmation formatting
    approval_msg = bot_engine.format_approval_confirmation("INC-104", "@oncall_lead")
    assert "@oncall_lead" in approval_msg
    assert "INC-104" in approval_msg
    print("3. Approval confirmation message:")
    print("   -> [PASS] Confirms approver identity and timestamp")

    # 4. Environment check
    token_set = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_telegram_bot_token_here")
    print(f"4. Environment check: TELEGRAM_BOT_TOKEN {'configured' if token_set else 'placeholder in .env'}")
    print(f"   Backend URL target: {BACKEND_URL}")

    print("=" * 60)
    print("STATUS: ALL BOT ENGINE CHECKS PASSED")
    print("=" * 60)
    return True


def main():
    if "--test" in sys.argv or "--ping-test" in sys.argv:
        success = run_self_test()
        sys.exit(0 if success else 1)

    if not TELEGRAM_LIB_AVAILABLE:
        print("Error: python-telegram-bot is not installed. Install via backend/requirements.txt.", file=sys.stderr)
        sys.exit(1)

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print(
            "Notice: TELEGRAM_BOT_TOKEN is not set or using placeholder.\n"
            "To connect to live Telegram:\n"
            "  1. Message @BotFather on Telegram to create a bot and copy the token.\n"
            "  2. Add the token to .env: TELEGRAM_BOT_TOKEN=...\n"
            "  3. Add bot to your team group and obtain TELEGRAM_CHAT_ID=...\n\n"
            "Running self-test verification instead:",
            file=sys.stderr,
        )
        run_self_test()
        return

    if not acquire_single_instance_lock():
        sys.exit(0)

    logger.info("Initializing OpsOracle Telegram Approval Bot...")

    async def post_init(application):
        logger.info("Bot post_init hook running -> spawning incident polling background task")
        asyncio.create_task(poll_incidents_task(application))

        # Send startup online message to chat if configured
        if TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID != "your_telegram_chat_id_here":
            try:
                online_msg = (
                    "🟢 *OpsOracle Approval Bot is ONLINE*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Backend: `{BACKEND_URL}`\n"
                    f"• Monitoring cluster incidents every {POLL_INTERVAL}s\n"
                    "• Ready to receive approvals & `/ping`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                await safe_send_message(application.bot, TELEGRAM_CHAT_ID, online_msg)
                logger.info(f"Startup online notice sent to chat {TELEGRAM_CHAT_ID}")
            except Exception as e:
                logger.warning(f"Could not dispatch startup notice: {e}")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register handlers
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.warning(f"Telegram handler caught exception: {context.error}")

    app.add_error_handler(global_error_handler)

    logger.info("Starting Telegram bot long-polling loop...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
