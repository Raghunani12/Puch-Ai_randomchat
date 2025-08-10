import asyncio
import re
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from threading import Lock  # TODO: migrate to asyncio.Lock for even better concurrency
from collections import deque
import uuid

from mcp.types import TextContent
from mcp import ErrorData, McpError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class UserState:
    """Represents the state of a user in the random connect system."""
    user_id: str
    nickname: str
    phone_masking_enabled: bool = True
    partner_id: Optional[str] = None
    partner_session_id: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        # Ensure phone numbers are never stored in plaintext
        if self.user_id and re.search(r'\d{10,}', self.user_id):
            logger.warning(f"Potential phone number detected in user_id: {self.user_id[:3]}***")

class RandomConnectManager:
    """Manages the random connect functionality for WhatsApp users."""
    
    def __init__(self):
        self.available_users: deque[str] = deque()  # O(1) queue of users waiting for matches
        self.available_set: Set[str] = set()         # Fast membership check to avoid duplicates
        self.active_pairs: Dict[str, str] = {}  # user_id -> partner_id mapping
        self.user_states: Dict[str, UserState] = {}  # user_id -> UserState
        self.pending_notifications: Dict[str, List[str]] = {}  # user_id -> list of notifications
        self.pending_messages: Dict[str, List[str]] = {}  # user_id -> list of queued incoming messages
        self.lock = Lock()  # Thread safety for concurrent operations
        self.strict_mode: bool = True  # If True, only #R sends and #M checks; non-commands are not delivered

        # Comprehensive phone number regex patterns for masking
        self.phone_patterns = [
            r'\+?\d{1,4}[-.\s]?\d{10,}',  # International format
            r'\d{10,}',  # Simple 10+ digit numbers
            r'\(\d{3}\)\s?\d{3}-?\d{4}',  # US format (123) 456-7890
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # Various formats 123-456-7890
            r'\+91[-.\s]?\d{10}',  # Indian format +91-9876543210
            r'91[-.\s]?\d{10}',  # Indian format without +
            r'\d{5}[-.\s]?\d{5}',  # 5-5 digit format
            r'\d{4}[-.\s]?\d{3}[-.\s]?\d{3}',  # 4-3-3 format
            r'\d{2}[-.\s]?\d{4}[-.\s]?\d{4}',  # 2-4-4 format
        ]
        
        logger.info("RandomConnectManager initialized")
    
    def mask_phone_numbers(self, text: str) -> str:
        """Replace phone numbers in text with [hidden] placeholder."""
        if not text:
            return text

        masked_text = text
        for pattern in self.phone_patterns:
            masked_text = re.sub(pattern, '[hidden]', masked_text)

        # Additional security: mask any sequence that looks like a phone number
        # Even if it doesn't match exact patterns
        masked_text = re.sub(r'\b\d{8,}\b', '[hidden]', masked_text)

        return masked_text

    def sanitize_for_logging(self, text: str) -> str:
        """Sanitize text for safe logging (always mask phone numbers)."""
        if not text:
            return text

        # Always mask phone numbers in logs regardless of user preference
        sanitized = self.mask_phone_numbers(text)

        # Also mask other potentially sensitive patterns
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', sanitized)

        return sanitized
    
    def get_or_create_user_state(self, user_id: str, nickname: str = None) -> UserState:
        """Get existing user state or create new one."""
        with self.lock:
            if user_id not in self.user_states:
                if not nickname:
                    nickname = f"User_{user_id[:8]}"
                self.user_states[user_id] = UserState(
                    user_id=user_id,
                    nickname=nickname
                )
                logger.info(f"Created new user state for {nickname}")
            
            # Update last activity
            self.user_states[user_id].last_activity = datetime.now()
            return self.user_states[user_id]
    
    def _queue_add(self, user_id: str):
        """Add a user to the waiting queue if not already present."""
        if user_id not in self.available_set:
            self.available_users.append(user_id)
            self.available_set.add(user_id)

    def _queue_remove(self, user_id: str):
        """Remove a user from the waiting queue if present."""
        if user_id in self.available_set:
            # Remove from set, then lazily drain from deque if head matches; O(n) worst-case only on contention
            self.available_set.remove(user_id)
            try:
                # Fast path: if at head
                if self.available_users and self.available_users[0] == user_id:
                    self.available_users.popleft()
                else:
                    # Slow path: rebuild deque without user_id
                    self.available_users = deque(u for u in self.available_users if u != user_id)
            except Exception:
                # Fallback safe rebuild
                self.available_users = deque(u for u in self.available_users if u != user_id)

    def find_partner(self, user_id: str) -> Optional[str]:
        """Find a random partner for the user."""
        with self.lock:
            # Ensure user not duplicated in queue
            self._queue_remove(user_id)

            # If queue is empty, add user and wait
            if not self.available_users:
                self._queue_add(user_id)
                logger.info(f"User {user_id[:8]} added to waiting queue")
                return None

            # Match with first available user (drain users that might have been removed)
            partner_id = None
            while self.available_users and partner_id is None:
                candidate = self.available_users.popleft()
                if candidate in self.available_set:
                    self.available_set.remove(candidate)
                    partner_id = candidate
            if partner_id is None:
                # Queue was drained; add self and wait
                self._queue_add(user_id)
                logger.info(f"User {user_id[:8]} added to waiting queue")
                return None

            # Create the pair
            self.active_pairs[user_id] = partner_id
            self.active_pairs[partner_id] = user_id

            # Update user states
            # Create a new session id for this pair
            session_id = str(uuid.uuid4())
            if user_id in self.user_states:
                self.user_states[user_id].partner_id = partner_id
                self.user_states[user_id].partner_session_id = session_id
            if partner_id in self.user_states:
                self.user_states[partner_id].partner_id = user_id
                self.user_states[partner_id].partner_session_id = session_id

            # Queue a connect notification for the waiting partner so they know it's live
            try:
                me_nick = self.user_states.get(user_id).nickname if user_id in self.user_states else "Partner"
                self.pending_notifications.setdefault(partner_id, []).append(
                    f"🎉 Connected! You're now chatting with {me_nick}. Use #R to send and #M to check messages."
                )
            except Exception:
                pass

            logger.info(f"Matched users: {user_id[:8]} <-> {partner_id[:8]}")
            return partner_id
    
    def end_chat(self, user_id: str) -> Optional[str]:
        """End the current chat for a user."""
        with self.lock:
            partner_id = self.active_pairs.get(user_id)

            if partner_id:
                # Remove both users from active pairs
                self.active_pairs.pop(user_id, None)
                self.active_pairs.pop(partner_id, None)

                # Update user states
                if user_id in self.user_states:
                    self.user_states[user_id].partner_id = None
                    self.user_states[user_id].partner_session_id = None
                if partner_id in self.user_states:
                    self.user_states[partner_id].partner_id = None
                    self.user_states[partner_id].partner_session_id = None

                # Queue a notification to partner for graceful disconnect
                self.pending_notifications.setdefault(partner_id, []).append(
                    "Your partner left the chat. Use #meet to find a new one."
                )

                logger.info(f"Ended chat between {user_id[:8]} and {partner_id[:8]}")
                return partner_id

            # Also remove from waiting queue if present
            # Remove from waiting queue if present
            self._queue_remove(user_id)
            logger.info(f"Removed {user_id[:8]} from waiting queue")

            return None
    
    def get_partner(self, user_id: str) -> Optional[str]:
        """Get the current partner of a user."""
        return self.active_pairs.get(user_id)
    
    def toggle_phone_masking(self, user_id: str) -> bool:
        """Toggle phone number masking for a user."""
        user_state = self.get_or_create_user_state(user_id)
        user_state.phone_masking_enabled = not user_state.phone_masking_enabled
        logger.info(f"Phone masking for {user_id[:8]}: {user_state.phone_masking_enabled}")
        return user_state.phone_masking_enabled
    
    def get_partner_nickname(self, user_id: str) -> Optional[str]:
        """Get the nickname of the user's current partner."""
        partner_id = self.get_partner(user_id)
        if partner_id and partner_id in self.user_states:
            return self.user_states[partner_id].nickname
        return None
    
    def is_command(self, message: str) -> bool:
        """Check if a message is a command."""
        message = message.strip().lower()
        commands = ['#meet', '#bye', '#again', '#hide', '#who', '#m', '#r']
        return any(message.startswith(cmd) for cmd in commands)
    
    def process_message(self, user_id: str, message: str, nickname: str = None) -> str:
        """Process an incoming message and return the response."""
        # Ensure user state exists
        user_state = self.get_or_create_user_state(user_id, nickname)
        
        # Apply phone number masking if enabled
        if user_state.phone_masking_enabled:
            message = self.mask_phone_numbers(message)
        
        message_lower = message.strip().lower()
        
        # Handle commands
        if message_lower.startswith('#meet'):
            return self._handle_meet_command(user_id)
        
        elif message_lower.startswith('#bye'):
            return self._handle_bye_command(user_id)
        
        elif message_lower.startswith('#again'):
            return self._handle_again_command(user_id)
        
        elif message_lower.startswith('#hide'):
            return self._handle_hide_command(user_id)
        
        elif message_lower.startswith('#who'):
            return self._handle_who_command(user_id)

        elif message_lower.startswith('#m'):
            # Manual pull of queued partner messages
            return self._handle_inbox_command(user_id)

        elif message_lower.startswith('#r'):
            # Explicit relay command: '#R your message here' (case-insensitive)
            content = message.strip()[2:].strip() if len(message.strip()) > 2 else ""
            if not content:
                return "Usage: #R your message here"
            return self._handle_message_routing(user_id, content)

        # Handle regular message routing (only if not in strict mode)
        if not self.strict_mode:
            outbound = self._handle_message_routing(user_id, message)
            queued = self.pending_messages.pop(user_id, [])
            if queued:
                delivered = "\n".join([f"💬 Partner: {m}" for m in queued[-10:]])
                logger.info(f"Delivered queued batch to {user_id[:8]}: {self.sanitize_for_logging(delivered)}")
                return f"{outbound}\n\n{delivered}"
            return outbound

        # In strict mode, non-commands do not send; show tip
        return "Use #R to send a message to your partner, and #M to check messages."
    
    def _handle_meet_command(self, user_id: str) -> str:
        """Handle the #meet command."""
        logger.info(f"MEET command from user {user_id[:8]}")

        # End current chat if exists
        current_partner = self.get_partner(user_id)
        if current_partner:
            logger.info(f"User {user_id[:8]} already in chat with {current_partner[:8]}")
            return "You're already in a chat! Use #bye to end it first, or #again to find a new partner."

        partner_id = self.find_partner(user_id)
        if partner_id:
            partner_nickname = self.get_partner_nickname(user_id)
            logger.info(f"MATCH SUCCESS: {user_id[:8]} matched with {partner_id[:8]} ({partner_nickname})")
            return f"🎉 Connected! You're now chatting with {partner_nickname}. Say hello!"
        else:
            logger.info(f"User {user_id[:8]} added to waiting queue")
            return "🔍 Looking for someone to chat with... Please wait while we find you a partner!"
    
    def _handle_bye_command(self, user_id: str) -> str:
        """Handle the #bye command."""
        logger.info(f"BYE command from user {user_id[:8]}")

        partner_id = self.end_chat(user_id)
        if partner_id:
            logger.info(f"CHAT ENDED: {user_id[:8]} disconnected from {partner_id[:8]}")
            return "👋 Chat ended. Use #meet to connect with someone new!"
        else:
            logger.info(f"User {user_id[:8]} tried to end chat but wasn't in one")
            return "You're not currently in a chat."
    
    def _handle_again_command(self, user_id: str) -> str:
        """Handle the #again command."""
        logger.info(f"AGAIN command from user {user_id[:8]}")

        # End current chat
        partner_id = self.end_chat(user_id)
        if partner_id:
            logger.info(f"AGAIN: {user_id[:8]} ended chat with {partner_id[:8]}")

        # Immediately look for new partner
        new_partner_id = self.find_partner(user_id)
        if new_partner_id:
            partner_nickname = self.get_partner_nickname(user_id)
            logger.info(f"AGAIN SUCCESS: {user_id[:8]} matched with new partner {new_partner_id[:8]} ({partner_nickname})")
            return f"🔄 New connection! You're now chatting with {partner_nickname}. Say hello!"
        else:
            logger.info(f"AGAIN: {user_id[:8]} added to waiting queue for new partner")
            return "🔍 Looking for a new chat partner... Please wait!"
    
    def _handle_hide_command(self, user_id: str) -> str:
        """Handle the #hide command."""
        masking_enabled = self.toggle_phone_masking(user_id)
        status = "ON" if masking_enabled else "OFF"
        return f"🔒 Phone number masking is now {status}."
    
    def _handle_who_command(self, user_id: str) -> str:
        """Handle the #who command."""
        partner_nickname = self.get_partner_nickname(user_id)
        if partner_nickname:
            return f"👤 You're chatting with: {partner_nickname}"
        else:
            return "You're not currently in a chat. Use #meet to connect!"

    def _handle_inbox_command(self, user_id: str) -> str:
        """Handle the #inbox command: manually pull queued partner messages."""
        notifications = self.pending_notifications.pop(user_id, [])
        messages = self.pending_messages.pop(user_id, [])
        if not notifications and not messages:
            return "📭 Inbox empty."
        parts = []
        for n in notifications[-3:]:  # last 3 notifications
            parts.append(f"ℹ️ {n}")
        for m in messages[-5:]:  # last 5 messages
            parts.append(f"💬 Partner: {m}")
        combined = "\n".join(parts)
        logger.info(f"Delivered inbox to {user_id[:8]}: {self.sanitize_for_logging(combined)}")
        return combined
    
    def _handle_message_routing(self, user_id: str, message: str) -> str:
        """Route a regular message to the user's partner."""
        with self.lock:
            # If the partner left earlier, deliver the pending notification first
            notifications = self.pending_notifications.pop(user_id, [])
            if notifications:
                note = notifications[-1]
                logger.info(f"Delivered pending notification to {user_id[:8]}: {self.sanitize_for_logging(note)}")
                return note

            partner_id = self.get_partner(user_id)
            if not partner_id:
                return "No partner found. Use #meet to connect."

            # Validate session id consistency to avoid cross-talk during re-pair
            me = self.user_states.get(user_id)
            partner = self.user_states.get(partner_id)
            if not me or not partner or me.partner_session_id != partner.partner_session_id:
                logger.warning(f"Session mismatch between {user_id[:8]} and {partner_id[:8]}; dropping message")
                return "No partner found. Use #meet to connect."

            # Queue the message for delivery to partner on their next inbound
            masked_message = self.mask_phone_numbers(message) if me.phone_masking_enabled else message
            queue = self.pending_messages.setdefault(partner_id, [])
            # Cap per-user queue to 100 messages to avoid unbounded growth
            queue.append(masked_message)
            if len(queue) > 100:
                # Drop oldest
                del queue[0]

            user_nickname = me.nickname if me else "Unknown"
            logger.info(f"Message queued from {user_id[:8]} to {partner_id[:8]}: {self.sanitize_for_logging(masked_message)}")
            return f"📤 Message sent to your partner from {user_nickname}: {message}"

    def cleanup_inactive_users(self, timeout_minutes: int = 30):
        """Clean up users who have been inactive for too long."""
        with self.lock:
            current_time = datetime.now()
            inactive_users = []

            for user_id, user_state in self.user_states.items():
                time_diff = current_time - user_state.last_activity
                if time_diff.total_seconds() > (timeout_minutes * 60):
                    inactive_users.append(user_id)

            for user_id in inactive_users:
                # End any active chats
                partner_id = self.end_chat(user_id)
                if partner_id:
                    logger.info(f"Cleaned up inactive user {user_id[:8]}, notified partner {partner_id[:8]}")

                # Remove from user states
                self.user_states.pop(user_id, None)
                logger.info(f"Removed inactive user {user_id[:8]} from system")

    def get_system_stats(self) -> Dict[str, int]:
        """Get current system statistics."""
        with self.lock:
            return {
                "active_users": len(self.user_states),
                "waiting_users": len(self.available_users),
                "active_pairs": len(self.active_pairs) // 2,  # Divide by 2 since each pair is stored twice
                "total_connections": len(self.active_pairs) // 2
            }

# Global instance
random_connect_manager = RandomConnectManager()
