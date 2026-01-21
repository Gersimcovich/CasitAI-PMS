"""
CasitAI CS Bot - Intelligent Guest Communication Assistant
Uses local Ollama model + Guesty Saved Replies for intelligent guest responses.

Features:
- Per-listing bot activation toggle
- Answers common guest questions using saved replies as knowledge base
- Web search for weather, events, transportation queries
- Negative sentiment detection with automatic agent assignment
- Escalates complex questions to human agents in Guesty
- Creates draft responses for agent review

Requirements:
- Ollama running locally with a model (llama3, mistral, etc.)
- Guesty API credentials
"""

import os
import json
import requests
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class CasitaAIBot:
    """CasitAI CS Bot - AI-powered guest communication assistant"""

    # Ollama configuration
    OLLAMA_BASE_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    DEFAULT_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')

    # Confidence threshold for auto-response vs escalation
    CONFIDENCE_THRESHOLD = 0.7

    # Keywords that trigger immediate escalation to human agent
    ESCALATION_KEYWORDS = [
        'refund', 'cancel', 'complaint', 'emergency', 'urgent', 'manager',
        'legal', 'lawyer', 'police', 'damage', 'injury', 'safety',
        'discrimination', 'harassment'
    ]

    # Keywords that trigger web search (weather, events, transportation)
    WEB_SEARCH_KEYWORDS = [
        'weather', 'forecast', 'temperature', 'rain', 'sunny',
        'event', 'events', 'concert', 'festival', 'game', 'show',
        'uber', 'lyft', 'taxi', 'bus', 'metro', 'train', 'airport',
        'transportation', 'shuttle', 'rental car', 'parking'
    ]

    # Negative sentiment indicators
    NEGATIVE_SENTIMENT_WORDS = [
        'terrible', 'awful', 'horrible', 'worst', 'disgusting', 'unacceptable',
        'disappointed', 'angry', 'furious', 'outraged', 'upset', 'frustrated',
        'ridiculous', 'scam', 'fraud', 'rip off', 'never again', 'hate',
        'dirty', 'filthy', 'broken', 'dangerous', 'unsafe', 'lied'
    ]

    # Casita brand personality - casual but professional hospitality voice
    BRAND_PERSONALITY = """
You are CasitAI, the friendly guest communication assistant for Casita - a boutique vacation rental company in Miami.

YOUR PERSONALITY:
- Warm and welcoming, like a knowledgeable local friend
- Professional but not stiff - use a conversational tone
- Helpful and proactive - anticipate guest needs
- Confident in hospitality knowledge without being arrogant
- Use natural language, not corporate speak

YOUR HOSPITALITY KNOWLEDGE:
- Standard check-in is 3-4 PM, check-out 10-11 AM (unless property specifies otherwise)
- Early check-in/late check-out depends on cleaning schedule and can often be accommodated
- Guests can store luggage if they arrive early
- Smart locks are common - codes are sent 24 hours before check-in
- Most properties have self check-in with detailed instructions
- Quiet hours typically 10 PM - 8 AM in residential areas
- Pool/amenity access varies by property
- Parking info should be provided in welcome message
- Local tips about restaurants, beaches, nightlife are valuable

HOW TO COMMUNICATE:
- Start with a friendly greeting using guest name if available
- Be direct and clear - guests are often busy or on vacation
- Offer specific help, not vague offers
- End with invitation for more questions
- Keep responses 2-4 sentences for simple questions
- Be thorough but not overwhelming for complex questions

THINGS TO AVOID:
- Overly formal language ("Dear valued guest", "We sincerely apologize")
- Excessive exclamation points or enthusiasm
- Generic responses that don't answer the actual question
- Making promises about things you're not sure about
- Long paragraphs when a short answer works
"""

    def __init__(self, guesty_client=None):
        self.guesty = guesty_client
        self._saved_replies_cache = {}  # Cache per listing
        self._cache_timestamp = None
        self._enabled_listings = set()  # Listings where bot is active
        self._all_listings = []  # All available listings
        self._conversation_history = []  # Training data from past conversations
        self._training_loaded = False

    # ============================================
    # OLLAMA LOCAL MODEL INTEGRATION
    # ============================================

    def _check_ollama_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.OLLAMA_BASE_URL}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _get_available_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            response = requests.get(f"{self.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def _call_ollama(self, prompt: str, system_prompt: str = None,
                     model: str = None, temperature: float = 0.3) -> str:
        """Call Ollama API for inference"""
        model = model or self.DEFAULT_MODEL

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = requests.post(
                f"{self.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('message', {}).get('content', '')

        except Exception as e:
            print(f"Ollama error: {e}")

        return ""

    # ============================================
    # LISTING MANAGEMENT
    # ============================================

    def get_all_listings(self, force_refresh: bool = False) -> List[Dict]:
        """Get all listings from Guesty"""
        if self._all_listings and not force_refresh:
            return self._all_listings

        if self.guesty:
            try:
                self._all_listings = self.guesty.get_all_listings(limit=200)
                return self._all_listings
            except Exception as e:
                print(f"Error fetching listings: {e}")
        return []

    def enable_bot_for_listing(self, listing_id: str):
        """Enable bot auto-response for a listing"""
        self._enabled_listings.add(listing_id)

    def disable_bot_for_listing(self, listing_id: str):
        """Disable bot auto-response for a listing"""
        self._enabled_listings.discard(listing_id)

    def is_bot_enabled(self, listing_id: str) -> bool:
        """Check if bot is enabled for a listing"""
        return listing_id in self._enabled_listings

    def get_enabled_listings(self) -> List[str]:
        """Get list of listing IDs where bot is enabled"""
        return list(self._enabled_listings)

    def set_enabled_listings(self, listing_ids: List[str]):
        """Set enabled listings from a list"""
        self._enabled_listings = set(listing_ids)

    # ============================================
    # CONVERSATION TRAINING
    # ============================================

    def load_all_conversations(self, limit: int = 500, force_refresh: bool = False) -> List[Dict]:
        """
        Load all historical conversations from Guesty for training.
        This teaches the bot how your team handles guest communication.

        Args:
            limit: Maximum number of conversations to fetch
            force_refresh: Force reload even if already loaded

        Returns:
            List of conversation training examples
        """
        if self._training_loaded and not force_refresh:
            return self._conversation_history

        if not self.guesty:
            print("Guesty client not configured")
            return []

        print(f"Loading conversation history from Guesty (limit: {limit})...")

        try:
            # Fetch all conversations
            all_conversations = self.guesty.get_conversations(limit=limit)
            training_examples = []

            print(f"Found {len(all_conversations)} conversations. Processing...")

            for conv in all_conversations:
                conv_id = conv.get('_id', '')

                if not conv_id:
                    continue

                try:
                    # Get messages for this conversation
                    messages = self.guesty.get_conversation_messages(conv_id, limit=50)

                    if not messages:
                        continue

                    # Build conversation thread (guest question -> host response pairs)
                    guest_messages = []
                    host_responses = []

                    for msg in reversed(messages):  # Oldest first
                        sender_type = msg.get('from', msg.get('type', ''))
                        body = msg.get('body', msg.get('text', ''))

                        if not body:
                            continue

                        if 'guest' in sender_type.lower():
                            guest_messages.append(body)
                        elif 'host' in sender_type.lower() or sender_type in ['sent', 'outgoing']:
                            host_responses.append(body)

                    # Create training examples from guest/host pairs
                    # Each host response after a guest message is a training example
                    for i, (guest_msg, host_resp) in enumerate(zip(guest_messages, host_responses)):
                        if len(guest_msg) > 10 and len(host_resp) > 10:  # Skip very short messages
                            training_examples.append({
                                'guest_message': guest_msg,
                                'host_response': host_resp,
                                'conversation_id': conv_id,
                                'listing_id': conv.get('listingId', ''),
                                'guest_name': conv.get('guest', {}).get('firstName', 'Guest')
                            })

                except Exception as e:
                    # Skip problematic conversations
                    continue

            self._conversation_history = training_examples
            self._training_loaded = True

            print(f"Loaded {len(training_examples)} training examples from conversations")
            return training_examples

        except Exception as e:
            print(f"Error loading conversations: {e}")
            return []

    def get_training_stats(self) -> Dict:
        """Get statistics about loaded training data"""
        if not self._conversation_history:
            return {
                'loaded': False,
                'total_examples': 0,
                'unique_conversations': 0
            }

        unique_convs = set(ex['conversation_id'] for ex in self._conversation_history)

        return {
            'loaded': True,
            'total_examples': len(self._conversation_history),
            'unique_conversations': len(unique_convs),
            'sample_topics': self._extract_sample_topics()
        }

    def _extract_sample_topics(self) -> List[str]:
        """Extract common topics from training data"""
        topics = []
        topic_keywords = {
            'check-in': ['check in', 'checkin', 'arrival', 'arrive', 'access'],
            'check-out': ['check out', 'checkout', 'departure', 'leave', 'leaving'],
            'parking': ['parking', 'car', 'garage', 'street parking'],
            'wifi': ['wifi', 'password', 'internet', 'connection'],
            'amenities': ['pool', 'gym', 'beach', 'kitchen', 'washer', 'dryer'],
            'location': ['location', 'address', 'directions', 'nearby', 'restaurant'],
            'issues': ['broken', 'not working', 'problem', 'issue', 'help']
        }

        topic_counts = {topic: 0 for topic in topic_keywords}

        for example in self._conversation_history[:100]:  # Sample first 100
            msg = example['guest_message'].lower()
            for topic, keywords in topic_keywords.items():
                if any(kw in msg for kw in keywords):
                    topic_counts[topic] += 1

        # Return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, count in sorted_topics[:5] if count > 0]

    def _build_training_context(self, guest_message: str, limit: int = 5) -> str:
        """
        Build context from similar past conversations for the AI.
        Finds relevant examples to help the AI learn your team's style.
        """
        if not self._conversation_history:
            return ""

        message_lower = guest_message.lower()

        # Find relevant examples based on keyword matching
        relevant_examples = []

        for example in self._conversation_history:
            score = 0
            ex_msg = example['guest_message'].lower()

            # Simple keyword matching for relevance
            msg_words = set(message_lower.split())
            ex_words = set(ex_msg.split())

            # Common words (excluding very common ones)
            common_words = msg_words & ex_words
            stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'i', 'we', 'you', 'to', 'for', 'of', 'in', 'on', 'at'}
            meaningful_common = common_words - stopwords

            score = len(meaningful_common)

            if score > 0:
                relevant_examples.append((score, example))

        # Sort by relevance and take top examples
        relevant_examples.sort(key=lambda x: x[0], reverse=True)
        top_examples = relevant_examples[:limit]

        if not top_examples:
            return ""

        # Format as training context
        context_parts = ["EXAMPLES FROM YOUR TEAM'S PAST CONVERSATIONS:"]

        for score, example in top_examples:
            context_parts.append(f"""
---
Guest: "{example['guest_message'][:200]}"
Your Team's Response: "{example['host_response'][:300]}"
---""")

        context_parts.append("\nUse a similar tone and style as these examples when responding.")

        return "\n".join(context_parts)

    # ============================================
    # SAVED REPLIES KNOWLEDGE BASE
    # ============================================

    def _load_saved_replies(self, listing_id: str = None, force_refresh: bool = False) -> List[Dict]:
        """Load saved replies from Guesty as knowledge base (per listing or global)"""
        cache_key = listing_id or 'global'

        # Cache for 10 minutes
        cache_valid = (
            cache_key in self._saved_replies_cache and
            self._cache_timestamp is not None and
            (datetime.now() - self._cache_timestamp).seconds < 600 and
            not force_refresh
        )

        if cache_valid:
            return self._saved_replies_cache.get(cache_key, [])

        if self.guesty:
            try:
                if listing_id:
                    # Get listing-specific saved replies
                    replies = self.guesty.get_saved_replies_by_listing(listing_id)
                else:
                    # Get all saved replies
                    replies = self.guesty.get_saved_replies(limit=200)

                self._saved_replies_cache[cache_key] = replies
                self._cache_timestamp = datetime.now()
                return replies
            except Exception as e:
                print(f"Error loading saved replies: {e}")

        return []

    def _build_knowledge_base(self, listing_id: str = None) -> str:
        """Build knowledge base string from saved replies"""
        # Get listing-specific replies first, then global
        replies = self._load_saved_replies(listing_id)

        if not replies:
            # Fall back to global replies
            replies = self._load_saved_replies(None)

        if not replies:
            return "No saved replies available."

        kb_parts = []
        for reply in replies:
            title = reply.get('title', reply.get('name', 'Untitled'))
            body = reply.get('body', reply.get('text', ''))
            category = reply.get('category', 'General')

            if body:
                kb_parts.append(f"### {title} ({category})\n{body}\n")

        return "\n".join(kb_parts)

    # ============================================
    # SENTIMENT & INTENT DETECTION
    # ============================================

    def _detect_negative_sentiment(self, message: str) -> Tuple[bool, float, str]:
        """
        Detect negative sentiment in guest message.
        Returns (is_negative, severity_score, reason)
        """
        message_lower = message.lower()
        found_words = []

        for word in self.NEGATIVE_SENTIMENT_WORDS:
            if word in message_lower:
                found_words.append(word)

        if not found_words:
            return False, 0.0, ""

        # Calculate severity based on number and type of negative words
        severity = min(1.0, len(found_words) * 0.3)

        # High severity words
        high_severity = ['scam', 'fraud', 'dangerous', 'unsafe', 'disgusting', 'lied']
        if any(word in found_words for word in high_severity):
            severity = min(1.0, severity + 0.4)

        return True, severity, f"Negative sentiment detected: {', '.join(found_words)}"

    def _needs_web_search(self, message: str) -> Tuple[bool, str]:
        """Check if message needs web search for weather/events/transportation"""
        message_lower = message.lower()

        for keyword in self.WEB_SEARCH_KEYWORDS:
            if keyword in message_lower:
                # Determine search type
                if keyword in ['weather', 'forecast', 'temperature', 'rain', 'sunny']:
                    return True, 'weather'
                elif keyword in ['event', 'events', 'concert', 'festival', 'game', 'show']:
                    return True, 'events'
                else:
                    return True, 'transportation'

        return False, ""

    # ============================================
    # AGENT ASSIGNMENT
    # ============================================

    def assign_to_agent(self, conversation_id: str, reason: str = "Requires human attention") -> Dict:
        """
        Assign conversation to a human CS agent in Guesty.
        This creates a note and marks conversation for agent follow-up.
        """
        if not self.guesty:
            return {"error": "Guesty client not configured"}

        try:
            # Create a draft message noting the escalation
            escalation_note = f"[CasitAI CS Bot] This conversation has been assigned to a human agent.\nReason: {reason}\n\nPlease review and respond to the guest."

            self.guesty.create_draft_message(conversation_id, escalation_note)

            return {
                "action": "assigned_to_agent",
                "conversation_id": conversation_id,
                "reason": reason
            }

        except Exception as e:
            return {"error": str(e)}

    # ============================================
    # MESSAGE ANALYSIS
    # ============================================

    def _needs_escalation(self, message: str) -> Tuple[bool, str]:
        """Check if message needs immediate escalation to human agent"""
        message_lower = message.lower()

        # Check escalation keywords
        for keyword in self.ESCALATION_KEYWORDS:
            if keyword in message_lower:
                return True, f"Message contains sensitive keyword: '{keyword}'"

        # Check negative sentiment
        is_negative, severity, reason = self._detect_negative_sentiment(message)
        if is_negative and severity >= 0.5:
            return True, reason

        return False, ""

    def _classify_intent(self, message: str) -> Dict:
        """Classify guest message intent using Ollama"""
        system_prompt = """You are a hospitality assistant that classifies guest messages.
        Analyze the message and return a JSON response with:
        - intent: one of [check_in, check_out, amenities, location, parking, wifi, rules, booking, pricing, weather, events, transportation, complaint, other]
        - confidence: 0.0 to 1.0
        - summary: brief summary of the question
        - needs_human: true if this requires human judgment
        - sentiment: one of [positive, neutral, negative]

        Return ONLY valid JSON, no other text."""

        prompt = f"Classify this guest message:\n\n{message}"

        response = self._call_ollama(prompt, system_prompt, temperature=0.1)

        # Parse JSON response
        try:
            # Extract JSON from response if wrapped in markdown
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            result = json.loads(response.strip())

            # Add sentiment check if not present
            if 'sentiment' not in result:
                is_negative, _, _ = self._detect_negative_sentiment(message)
                result['sentiment'] = 'negative' if is_negative else 'neutral'

            return result
        except:
            return {
                "intent": "other",
                "confidence": 0.5,
                "summary": message[:100],
                "needs_human": True,
                "sentiment": "neutral"
            }

    def _generate_web_search_response(self, message: str, search_type: str, context: Dict = None) -> str:
        """Generate response for queries needing web search info"""
        location = "Miami Beach, FL"  # Default location
        if context and context.get('listing_address'):
            location = context['listing_address']

        if search_type == 'weather':
            return f"For the most up-to-date weather information in {location}, I recommend checking weather.com or your phone's weather app. The area typically enjoys warm, tropical weather. Is there anything specific about your stay I can help with?"

        elif search_type == 'events':
            return f"For current events and activities in {location}, I suggest checking local event sites like Eventbrite, Miami New Times, or asking our team for personalized recommendations. We'd be happy to help you plan something special during your stay!"

        elif search_type == 'transportation':
            return f"For transportation options in {location}, popular choices include Uber, Lyft, and local taxis. The area is also walkable for many activities. If you need specific directions to/from the property or airport shuttle information, please let us know and we'll be happy to assist!"

        return "I'd be happy to help with that! Let me connect you with our team who can provide the most current information."

    # ============================================
    # SAVED REPLY MATCHING
    # ============================================

    def _match_saved_reply(self, message: str, listing_id: str = None) -> Tuple[Dict, float]:
        """
        Try to match guest message to a saved reply.
        Returns (matched_reply, match_score) or (None, 0.0)
        """
        # Get saved replies for this listing
        replies = self._load_saved_replies(listing_id)
        if not replies:
            replies = self._load_saved_replies(None)  # Fall back to global

        if not replies:
            return None, 0.0

        message_lower = message.lower()

        # Build a list of potential matches
        best_match = None
        best_score = 0.0

        for reply in replies:
            title = reply.get('title', reply.get('name', '')).lower()
            body = reply.get('body', reply.get('text', '')).lower()
            keywords = reply.get('keywords', [])

            # Calculate match score
            score = 0.0

            # Check title keywords
            title_words = title.split()
            for word in title_words:
                if len(word) > 3 and word in message_lower:
                    score += 0.2

            # Check explicit keywords
            for keyword in keywords:
                if keyword.lower() in message_lower:
                    score += 0.3

            # Common question patterns
            patterns = {
                'check-in': ['check in', 'checkin', 'check-in', 'arrival', 'arrive'],
                'check-out': ['check out', 'checkout', 'check-out', 'departure', 'leave'],
                'wifi': ['wifi', 'wi-fi', 'internet', 'password'],
                'parking': ['parking', 'park', 'car', 'garage'],
                'amenities': ['amenities', 'amenity', 'pool', 'gym', 'kitchen'],
                'location': ['location', 'address', 'directions', 'where'],
                'rules': ['rules', 'policy', 'policies', 'allowed', 'smoking', 'pets']
            }

            for category, keywords in patterns.items():
                if category in title.lower() or category in body[:100].lower():
                    for keyword in keywords:
                        if keyword in message_lower:
                            score += 0.25

            if score > best_score:
                best_score = score
                best_match = reply

        # Normalize score to 0-1 range (cap at 1.0)
        best_score = min(1.0, best_score)

        return best_match, best_score

    # ============================================
    # RESPONSE GENERATION
    # ============================================

    def generate_response(self, guest_message: str, context: Dict = None) -> Dict:
        """
        Generate a response to a guest message.

        PRIORITY ORDER:
        1. Check for negative sentiment / escalation keywords → Assign to human agent
        2. Try to match saved replies from Guesty → Use if match score >= 0.6
        3. Check if web info can help (weather/events/transport) → Use if effective
        4. Generate AI response with saved replies as context
        5. Low confidence → Escalate to human agent

        Returns:
            Dict with response details, confidence, source, escalation status
        """
        listing_id = context.get('listing_id') if context else None

        # Check if bot is enabled for this listing (if listing_id provided)
        if listing_id and not self.is_bot_enabled(listing_id):
            return {
                "response": None,
                "confidence": 0.0,
                "source": "disabled",
                "escalated": True,
                "reason": "Bot not enabled for this listing",
                "sentiment": "unknown",
                "assigned_to_agent": False
            }

        # STEP 1: Detect negative sentiment first - always escalate
        is_negative, severity, sentiment_reason = self._detect_negative_sentiment(guest_message)

        if is_negative:
            return {
                "response": None,
                "confidence": 0.0,
                "source": "escalated",
                "escalated": True,
                "reason": f"[ASSIGN TO CS AGENT] {sentiment_reason}",
                "sentiment": "negative",
                "assigned_to_agent": True
            }

        # Check for escalation keywords
        needs_escalation, reason = self._needs_escalation(guest_message)
        if needs_escalation:
            return {
                "response": None,
                "confidence": 0.0,
                "source": "escalated",
                "escalated": True,
                "reason": f"[ASSIGN TO CS AGENT] {reason}",
                "sentiment": "negative",
                "assigned_to_agent": True
            }

        # STEP 2: Try to match saved replies first (highest priority)
        matched_reply, match_score = self._match_saved_reply(guest_message, listing_id)

        if matched_reply and match_score >= 0.6:
            # Good match found in saved replies
            reply_body = matched_reply.get('body', matched_reply.get('text', ''))
            return {
                "response": reply_body,
                "confidence": match_score,
                "source": "saved_reply",
                "escalated": False,
                "reason": None,
                "sentiment": "neutral",
                "assigned_to_agent": False,
                "matched_reply_title": matched_reply.get('title', 'Untitled')
            }

        # STEP 3: Check if web info can help (weather, events, transportation)
        needs_web, search_type = self._needs_web_search(guest_message)
        if needs_web:
            response = self._generate_web_search_response(guest_message, search_type, context)
            # Web info responses are >= 75% effective for these topics
            return {
                "response": response,
                "confidence": 0.85,
                "source": "web_info",
                "escalated": False,
                "reason": None,
                "sentiment": "neutral",
                "assigned_to_agent": False
            }

        # STEP 4: Classify intent and generate AI response
        classification = self._classify_intent(guest_message)
        sentiment = classification.get('sentiment', 'neutral')

        # Double-check sentiment from classification
        if sentiment == 'negative':
            return {
                "response": None,
                "confidence": classification.get('confidence', 0.0),
                "source": "escalated",
                "escalated": True,
                "reason": "[ASSIGN TO CS AGENT] Negative sentiment detected by AI classifier",
                "sentiment": "negative",
                "assigned_to_agent": True
            }

        if classification.get('needs_human'):
            return {
                "response": None,
                "confidence": classification.get('confidence', 0.0),
                "source": "escalated",
                "escalated": True,
                "reason": f"Requires human judgment: {classification.get('summary', '')}",
                "sentiment": sentiment,
                "assigned_to_agent": False
            }

        # Build knowledge base from saved replies for AI context
        knowledge_base = self._build_knowledge_base(listing_id)

        # Build training context from past conversations
        training_context = self._build_training_context(guest_message)

        # Generate response using Ollama with saved replies context and brand personality
        system_prompt = f"""{self.BRAND_PERSONALITY}

PRIORITY ORDER FOR RESPONDING:
1. Use saved replies from KNOWLEDGE BASE below if they match
2. Apply your hospitality knowledge for common questions
3. Reference the CONVERSATION EXAMPLES to match your team's style
4. If you can't answer confidently, say: "Let me check with the team and get back to you on that."

KNOWLEDGE BASE (Saved Replies):
{knowledge_base}

{training_context}

CURRENT GUEST CONTEXT:
{json.dumps(context or {}, indent=2)}

Remember: Be conversational, not corporate. You're helping a guest, not writing a formal letter.
"""

        prompt = f"Guest says: \"{guest_message}\"\n\nRespond naturally, like you're texting a friend who's staying at your place. Keep it helpful and brief:"

        response = self._call_ollama(prompt, system_prompt, temperature=0.3)

        # Calculate effectiveness score
        confidence = classification.get('confidence', 0.5)

        # If AI had to defer to team, escalate
        if "connect you with our team" in response.lower():
            return {
                "response": response,
                "confidence": confidence,
                "source": "ai",
                "escalated": True,
                "reason": "Unable to answer from knowledge base - needs human review",
                "sentiment": sentiment,
                "assigned_to_agent": False
            }

        # STEP 5: Check confidence threshold (75%)
        if confidence < 0.75:
            return {
                "response": response,
                "confidence": confidence,
                "source": "ai",
                "escalated": True,
                "reason": f"[ASSIGN TO CS AGENT] Low confidence ({confidence:.0%})",
                "sentiment": sentiment,
                "assigned_to_agent": True
            }

        # High confidence AI response
        return {
            "response": response,
            "confidence": confidence,
            "source": "ai",
            "escalated": False,
            "reason": None,
            "sentiment": sentiment,
            "assigned_to_agent": False
        }

    # ============================================
    # CONVERSATION HANDLING
    # ============================================

    def process_conversation(self, conversation_id: str,
                             auto_respond: bool = False) -> Dict:
        """
        Process a conversation and generate/send response.

        Args:
            conversation_id: Guesty conversation ID
            auto_respond: If True, auto-send high-confidence responses

        Returns:
            Processing result with response and action taken
        """
        if not self.guesty:
            return {"error": "Guesty client not configured"}

        try:
            # Get conversation details
            conversation = self.guesty.get_conversation(conversation_id)
            messages = self.guesty.get_conversation_messages(conversation_id, limit=10)

            if not messages:
                return {"error": "No messages in conversation"}

            # Get latest guest message
            latest_message = None
            for msg in messages:
                if msg.get('from') == 'guest' or msg.get('type') == 'fromGuest':
                    latest_message = msg
                    break

            if not latest_message:
                return {"info": "No new guest messages"}

            # Build context
            listing_id = conversation.get('listingId')
            context = {
                "guest_name": conversation.get('guest', {}).get('firstName', 'Guest'),
                "listing_id": listing_id,
                "check_in": conversation.get('checkIn'),
                "check_out": conversation.get('checkOut'),
                "listing_address": conversation.get('listing', {}).get('address', {}).get('city', 'Miami Beach, FL')
            }

            # Generate response
            result = self.generate_response(
                latest_message.get('body', latest_message.get('text', '')),
                context
            )

            # Handle response based on result
            if result.get('assigned_to_agent'):
                # Negative sentiment or escalation - assign to human agent
                assignment = self.assign_to_agent(
                    conversation_id,
                    result.get('reason', 'Requires human attention')
                )
                return {
                    "action": "assigned_to_agent",
                    "reason": result['reason'],
                    "sentiment": result.get('sentiment', 'unknown'),
                    "assignment_result": assignment
                }

            elif result['escalated']:
                # Create draft for human review (but not urgent)
                if result['response']:
                    self.guesty.create_draft_message(conversation_id, result['response'])
                return {
                    "action": "escalated",
                    "reason": result['reason'],
                    "draft_created": result['response'] is not None,
                    "response": result['response'],
                    "sentiment": result.get('sentiment', 'neutral')
                }

            elif auto_respond and result['confidence'] >= 0.8:
                # Auto-send high confidence responses
                self.guesty.send_message(conversation_id, result['response'])
                return {
                    "action": "auto_responded",
                    "response": result['response'],
                    "confidence": result['confidence'],
                    "source": result.get('source', 'ai'),
                    "sentiment": result.get('sentiment', 'neutral')
                }

            else:
                # Create draft for review
                self.guesty.create_draft_message(conversation_id, result['response'])
                return {
                    "action": "draft_created",
                    "response": result['response'],
                    "confidence": result['confidence'],
                    "source": result.get('source', 'ai'),
                    "sentiment": result.get('sentiment', 'neutral')
                }

        except Exception as e:
            return {"error": str(e)}

    # ============================================
    # UTILITY METHODS
    # ============================================

    def get_status(self) -> Dict:
        """Get AI Bot system status"""
        ollama_available = self._check_ollama_available()
        models = self._get_available_models() if ollama_available else []
        replies = self._load_saved_replies()
        training_stats = self.get_training_stats()

        return {
            "ollama_available": ollama_available,
            "ollama_url": self.OLLAMA_BASE_URL,
            "default_model": self.DEFAULT_MODEL,
            "available_models": models,
            "model_ready": self.DEFAULT_MODEL in [m.split(':')[0] for m in models],
            "guesty_connected": self.guesty is not None,
            "saved_replies_count": len(replies),
            "confidence_threshold": self.CONFIDENCE_THRESHOLD,
            "training_loaded": training_stats.get('loaded', False),
            "training_examples": training_stats.get('total_examples', 0)
        }

    def test_response(self, message: str) -> Dict:
        """Test response generation without sending"""
        return self.generate_response(message)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_ai_bot(guesty_client=None) -> CasitaAIBot:
    """Get AI Bot instance"""
    if guesty_client is None:
        from guesty_api import get_guesty_client
        guesty_client = get_guesty_client()
    return CasitaAIBot(guesty_client)


def test_ollama_connection() -> bool:
    """Test if Ollama is available"""
    bot = CasitaAIBot()
    return bot._check_ollama_available()


if __name__ == "__main__":
    print("Testing Casita AI Bot...")
    print("=" * 50)

    bot = CasitaAIBot()
    status = bot.get_status()

    print(f"Ollama Available: {status['ollama_available']}")
    print(f"Ollama URL: {status['ollama_url']}")
    print(f"Default Model: {status['default_model']}")
    print(f"Available Models: {status['available_models']}")
    print(f"Model Ready: {status['model_ready']}")

    if status['ollama_available'] and status['model_ready']:
        print("\n" + "=" * 50)
        print("Testing response generation...")

        test_messages = [
            "What time is check-in?",
            "How do I get to the property?",
            "Is there parking available?",
            "I want a refund for my stay",  # Should escalate
            "What's the wifi password?",
        ]

        for msg in test_messages:
            print(f"\nGuest: {msg}")
            result = bot.test_response(msg)
            print(f"Response: {result.get('response', 'N/A')}")
            print(f"Confidence: {result['confidence']:.2f}")
            print(f"Escalated: {result['escalated']}")
            if result.get('reason'):
                print(f"Reason: {result['reason']}")
    else:
        print("\nOllama not available. Please ensure Ollama is running with a model.")
        print("Run: ollama pull llama3.2")
