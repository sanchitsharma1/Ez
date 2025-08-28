import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class IntentDetector:
    """Intent detection service for routing user requests to appropriate agents"""
    
    def __init__(self):
        # Intent patterns and keywords
        self.intent_patterns = {
            "email": {
                "keywords": ["email", "mail", "send", "compose", "inbox", "reply", "message"],
                "patterns": [
                    r"send.*email",
                    r"compose.*message",
                    r"check.*inbox",
                    r"reply.*to",
                    r"email.*about"
                ]
            },
            "calendar": {
                "keywords": ["calendar", "schedule", "meeting", "appointment", "event", "remind"],
                "patterns": [
                    r"schedule.*meeting",
                    r"book.*appointment",
                    r"add.*calendar",
                    r"remind.*me",
                    r"what.*my.*schedule"
                ]
            },
            "task_management": {
                "keywords": ["task", "todo", "reminder", "complete", "finish", "deadline"],
                "patterns": [
                    r"add.*task",
                    r"create.*todo",
                    r"mark.*complete",
                    r"finish.*task",
                    r"what.*tasks"
                ]
            },
            "system_monitoring": {
                "keywords": ["system", "performance", "cpu", "memory", "disk", "monitor", "status"],
                "patterns": [
                    r"system.*status",
                    r"check.*performance",
                    r"how.*system",
                    r"cpu.*usage",
                    r"memory.*usage"
                ]
            },
            "system_command": {
                "keywords": ["run", "execute", "command", "mkdir", "create", "directory"],
                "patterns": [
                    r"run.*command",
                    r"execute.*",
                    r"create.*directory",
                    r"mkdir.*",
                    r"cmd.*"
                ]
            },
            "document_processing": {
                "keywords": ["document", "file", "pdf", "analyze", "summarize", "process"],
                "patterns": [
                    r"analyze.*document",
                    r"summarize.*file",
                    r"process.*pdf",
                    r"read.*document",
                    r"extract.*from"
                ]
            },
            "knowledge_query": {
                "keywords": ["search", "find", "lookup", "information", "knowledge", "what", "how"],
                "patterns": [
                    r"search.*for",
                    r"find.*information",
                    r"what.*is",
                    r"how.*to",
                    r"tell.*me.*about"
                ]
            },
            "content_generation": {
                "keywords": ["write", "create", "generate", "essay", "article", "content"],
                "patterns": [
                    r"write.*essay",
                    r"create.*article",
                    r"generate.*content",
                    r"help.*write",
                    r"draft.*"
                ]
            },
            "financial_analysis": {
                "keywords": ["stock", "market", "finance", "investment", "portfolio", "price"],
                "patterns": [
                    r"stock.*price",
                    r"market.*analysis",
                    r"analyze.*portfolio",
                    r"financial.*report",
                    r"investment.*"
                ]
            },
            "validation_request": {
                "keywords": ["validate", "verify", "check", "confirm", "judge", "assess"],
                "patterns": [
                    r"validate.*",
                    r"verify.*",
                    r"is.*this.*correct",
                    r"check.*accuracy",
                    r"judge.*"
                ]
            },
            "consensus_building": {
                "keywords": ["consensus", "multiple", "sources", "compare", "opinions"],
                "patterns": [
                    r"build.*consensus",
                    r"multiple.*sources",
                    r"compare.*opinions",
                    r"what.*do.*sources",
                    r"consensus.*on"
                ]
            }
        }
        
        # Agent routing based on intent
        self.intent_to_agent = {
            "email": "carol",
            "calendar": "carol",
            "task_management": "carol",
            "system_monitoring": "alex",
            "system_command": "alex",
            "document_processing": "sofia",
            "knowledge_query": "sofia",
            "content_generation": "sofia",
            "financial_analysis": "morgan",
            "market_data": "morgan",
            "validation_request": "judy",
            "consensus_building": "judy",
            "general": "carol"
        }
    
    async def detect_intent(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Detect intent from user message"""
        try:
            if not user_message or not user_message.strip():
                return {
                    "intent": "general",
                    "confidence": 0.5,
                    "agent": "carol",
                    "entities": {},
                    "reasoning": "Empty or invalid message"
                }
            
            message_lower = user_message.lower().strip()
            
            # Calculate intent scores
            intent_scores = {}
            
            for intent, config in self.intent_patterns.items():
                score = self._calculate_intent_score(message_lower, config)
                if score > 0:
                    intent_scores[intent] = score
            
            # Determine best intent
            if not intent_scores:
                best_intent = "general"
                confidence = 0.5
            else:
                best_intent = max(intent_scores, key=intent_scores.get)
                max_score = intent_scores[best_intent]
                total_score = sum(intent_scores.values())
                confidence = max_score / total_score if total_score > 0 else 0.5
            
            # Extract entities
            entities = await self._extract_entities(user_message, best_intent)
            
            # Get recommended agent
            agent = self.intent_to_agent.get(best_intent, "carol")
            
            # Generate reasoning
            reasoning = self._generate_reasoning(best_intent, confidence, intent_scores)
            
            return {
                "intent": best_intent,
                "confidence": confidence,
                "agent": agent,
                "entities": entities,
                "all_scores": intent_scores,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            return {
                "intent": "general",
                "confidence": 0.0,
                "agent": "carol",
                "entities": {},
                "reasoning": f"Error in intent detection: {str(e)}"
            }
    
    def _calculate_intent_score(self, message: str, config: Dict[str, Any]) -> float:
        """Calculate intent score based on keywords and patterns"""
        try:
            score = 0.0
            
            # Keyword matching
            keywords = config.get("keywords", [])
            for keyword in keywords:
                if keyword in message:
                    score += 1.0
                    # Bonus for exact word match (not substring)
                    if re.search(r'\b' + re.escape(keyword) + r'\b', message):
                        score += 0.5
            
            # Pattern matching
            patterns = config.get("patterns", [])
            for pattern in patterns:
                try:
                    if re.search(pattern, message, re.IGNORECASE):
                        score += 2.0  # Patterns get higher weight
                except re.error:
                    continue  # Skip invalid patterns
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating intent score: {e}")
            return 0.0
    
    async def _extract_entities(self, message: str, intent: str) -> Dict[str, Any]:
        """Extract entities based on intent type"""
        entities = {}
        
        try:
            if intent == "email":
                entities.update(self._extract_email_entities(message))
            elif intent == "calendar":
                entities.update(self._extract_calendar_entities(message))
            elif intent == "task_management":
                entities.update(self._extract_task_entities(message))
            elif intent == "system_command":
                entities.update(self._extract_command_entities(message))
            elif intent == "financial_analysis":
                entities.update(self._extract_financial_entities(message))
            elif intent == "document_processing":
                entities.update(self._extract_document_entities(message))
            
            # Common entities
            entities.update(self._extract_time_entities(message))
            entities.update(self._extract_priority_entities(message))
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
        
        return entities
    
    def _extract_email_entities(self, message: str) -> Dict[str, Any]:
        """Extract email-specific entities"""
        entities = {}
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, message)
        if emails:
            entities["email_addresses"] = emails
        
        # Extract email actions
        if any(word in message.lower() for word in ["send", "compose"]):
            entities["action"] = "send"
        elif any(word in message.lower() for word in ["reply", "respond"]):
            entities["action"] = "reply"
        elif any(word in message.lower() for word in ["check", "read"]):
            entities["action"] = "read"
        
        return entities
    
    def _extract_calendar_entities(self, message: str) -> Dict[str, Any]:
        """Extract calendar-specific entities"""
        entities = {}
        
        # Extract meeting types
        meeting_types = ["meeting", "call", "appointment", "conference", "interview"]
        for meeting_type in meeting_types:
            if meeting_type in message.lower():
                entities["event_type"] = meeting_type
                break
        
        # Extract attendees (simple name patterns)
        name_pattern = r'\bwith\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        name_matches = re.findall(name_pattern, message)
        if name_matches:
            entities["attendees"] = name_matches
        
        return entities
    
    def _extract_task_entities(self, message: str) -> Dict[str, Any]:
        """Extract task-specific entities"""
        entities = {}
        
        # Extract task status
        if any(word in message.lower() for word in ["complete", "done", "finished"]):
            entities["status"] = "completed"
        elif any(word in message.lower() for word in ["start", "begin"]):
            entities["status"] = "in_progress"
        else:
            entities["status"] = "pending"
        
        # Extract task title (simple heuristic)
        task_markers = ["task", "todo", "reminder"]
        for marker in task_markers:
            pattern = fr'{marker}\s*:?\s*(.+?)(?:\s+(?:by|due|before|on)|\.|$)'
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                entities["task_title"] = match.group(1).strip()
                break
        
        return entities
    
    def _extract_command_entities(self, message: str) -> Dict[str, Any]:
        """Extract system command entities"""
        entities = {}
        
        # Extract command
        command_patterns = [
            r'run\s+"([^"]+)"',
            r'execute\s+"([^"]+)"',
            r'command\s+"([^"]+)"',
            r'mkdir\s+(\S+)',
            r'create\s+directory\s+(\S+)'
        ]
        
        for pattern in command_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                entities["command"] = match.group(1)
                break
        
        return entities
    
    def _extract_financial_entities(self, message: str) -> Dict[str, Any]:
        """Extract financial entities"""
        entities = {}
        
        # Extract stock symbols (3-5 uppercase letters)
        stock_pattern = r'\b([A-Z]{3,5})\b'
        stocks = re.findall(stock_pattern, message)
        if stocks:
            # Filter out common false positives
            false_positives = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL'}
            entities["stock_symbols"] = [s for s in stocks if s not in false_positives]
        
        # Extract dollar amounts
        amount_pattern = r'\$([0-9,]+(?:\.[0-9]{2})?)'
        amounts = re.findall(amount_pattern, message)
        if amounts:
            entities["amounts"] = amounts
        
        return entities
    
    def _extract_document_entities(self, message: str) -> Dict[str, Any]:
        """Extract document processing entities"""
        entities = {}
        
        # Extract file extensions/types
        file_types = ["pdf", "doc", "docx", "txt", "rtf"]
        for file_type in file_types:
            if file_type in message.lower():
                entities["file_type"] = file_type
                break
        
        # Extract processing actions
        if any(word in message.lower() for word in ["summarize", "summary"]):
            entities["action"] = "summarize"
        elif any(word in message.lower() for word in ["analyze", "analysis"]):
            entities["action"] = "analyze"
        elif any(word in message.lower() for word in ["extract", "get"]):
            entities["action"] = "extract"
        
        return entities
    
    def _extract_time_entities(self, message: str) -> Dict[str, Any]:
        """Extract time-related entities"""
        entities = {}
        
        # Time patterns
        time_patterns = {
            "today": r'\btoday\b',
            "tomorrow": r'\btomorrow\b',
            "next_week": r'\bnext\s+week\b',
            "this_week": r'\bthis\s+week\b',
            "urgent": r'\burgent\b|\basap\b|immediately\b'
        }
        
        for time_type, pattern in time_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                entities["time_reference"] = time_type
                break
        
        # Extract specific times
        time_pattern = r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b'
        time_matches = re.findall(time_pattern, message, re.IGNORECASE)
        if time_matches:
            entities["specific_times"] = time_matches
        
        return entities
    
    def _extract_priority_entities(self, message: str) -> Dict[str, Any]:
        """Extract priority-related entities"""
        entities = {}
        
        priority_keywords = {
            "high": ["urgent", "asap", "immediately", "critical", "important"],
            "medium": ["soon", "when possible", "moderate"],
            "low": ["later", "whenever", "low priority", "not urgent"]
        }
        
        message_lower = message.lower()
        for priority, keywords in priority_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                entities["priority"] = priority
                break
        
        return entities
    
    def _generate_reasoning(self, best_intent: str, confidence: float, all_scores: Dict[str, float]) -> str:
        """Generate reasoning for intent detection"""
        try:
            if confidence > 0.8:
                confidence_level = "high"
            elif confidence > 0.5:
                confidence_level = "medium"
            else:
                confidence_level = "low"
            
            reasoning = f"Intent '{best_intent}' detected with {confidence_level} confidence ({confidence:.2f})"
            
            if len(all_scores) > 1:
                # Show runner-up intents
                sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
                if len(sorted_scores) > 1:
                    runner_up = sorted_scores[1]
                    reasoning += f". Runner-up: '{runner_up[0]}' ({runner_up[1]:.2f})"
            
            return reasoning
            
        except Exception as e:
            return f"Intent detection completed with error: {str(e)}"
    
    def get_supported_intents(self) -> List[str]:
        """Get list of supported intents"""
        return list(self.intent_patterns.keys())
    
    def get_agent_for_intent(self, intent: str) -> str:
        """Get recommended agent for intent"""
        return self.intent_to_agent.get(intent, "carol")