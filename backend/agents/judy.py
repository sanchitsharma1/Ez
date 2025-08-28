import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import statistics
import hashlib

from agents.base_agent import BaseAgent
from utils.llm_client import LLMClient
from core.config import settings

logger = logging.getLogger(__name__)

class JudyAgent(BaseAgent):
    """Judy - Decision Validation and Consensus Specialist"""
    
    def __init__(self):
        super().__init__(
            agent_id="judy",
            name="Judy",
            persona="""You are Judy, an impartial and thorough judge who specializes in validating responses, 
            building consensus from multiple sources, and providing confidence assessments. You're analytical, 
            methodical, and fair in your evaluations. You help ensure accuracy by cross-referencing multiple 
            AI models and sources, identifying potential hallucinations, and providing confidence scores for 
            sensitive decisions. You're the final validator for important actions."""
        )
        
        self.capabilities = [
            "response_validation",
            "consensus_building", 
            "confidence_scoring",
            "hallucination_detection",
            "multi_model_analysis",
            "risk_assessment"
        ]
        
        self.voice_id = "AZnzlk1XvdvUeBnXmlld"  # Female voice for Judy
        
        # Multiple LLM clients for consensus
        self.primary_llm: Optional[LLMClient] = None
        self.validation_sources = ["openai", "perplexity", "local"]
    
    async def _initialize_agent(self):
        """Initialize Judy-specific services"""
        try:
            self.primary_llm = LLMClient()
            await self.primary_llm.initialize()
            
            logger.info("Judy agent initialized with multi-model validation capabilities")
            
        except Exception as e:
            logger.error(f"Failed to initialize Judy's services: {e}")
            raise
    
    def _get_agent_instructions(self) -> str:
        """Get Judy-specific instructions"""
        return """
        As Judy, you should:
        
        1. RESPONSE VALIDATION:
           - Verify factual accuracy of other agents' responses
           - Cross-check information against multiple sources
           - Identify potential inaccuracies or hallucinations
           - Provide confidence scores (0.0-1.0) for responses
        
        2. CONSENSUS BUILDING:
           - Query multiple LLMs for the same question
           - Compare and analyze different responses
           - Identify areas of agreement and disagreement
           - Synthesize the most accurate and balanced answer
        
        3. RISK ASSESSMENT:
           - Evaluate potential risks of proposed actions
           - Assess confidence levels for sensitive decisions
           - Identify factors that could lead to negative outcomes
           - Recommend approval, rejection, or additional review
        
        4. QUALITY ASSURANCE:
           - Check response relevance and completeness
           - Ensure appropriate tone and professionalism
           - Verify that disclaimers and warnings are included
           - Assess if response meets user's actual needs
        
        5. DECISION SUPPORT:
           - Provide impartial analysis for approval requests
           - Offer multiple perspectives on complex issues
           - Highlight pros and cons of different approaches
           - Recommend best course of action with reasoning
        
        Always be objective, thorough, and fair in your assessments. 
        Provide clear reasoning for all judgments and confidence scores.
        """
    
    async def process_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process message as Judy"""
        try:
            messages = context.get("messages", [])
            intent = context.get("intent", "validation_request")
            user_context = context.get("context", {})
            mode = context.get("mode", "online")
            
            if not messages:
                return await self._generate_greeting()
            
            user_message = messages[-1]["content"]
            
            # Route to specific handler based on intent
            if intent == "validation_request":
                return await self._handle_validation_request(user_message, user_context, mode)
            elif intent == "consensus_building":
                return await self._handle_consensus_request(user_message, user_context, mode)
            elif intent == "risk_assessment":
                return await self._handle_risk_assessment(user_message, user_context, mode)
            else:
                return await self._handle_general_validation_request(messages, user_context, mode)
                
        except Exception as e:
            logger.error(f"Error processing message in Judy: {e}")
            return await self.handle_error(str(e), context)
    
    async def _generate_greeting(self) -> Dict[str, Any]:
        """Generate Judy's greeting"""
        greeting = """Hello! I'm Judy, your decision validation and consensus specialist. I help ensure accuracy and build confidence in important decisions by:

⚖️ **Response Validation** - Verify accuracy of information and responses
🤝 **Consensus Building** - Cross-reference multiple AI models and sources
📊 **Confidence Scoring** - Provide reliability assessments (0-100%)
🔍 **Hallucination Detection** - Identify potential inaccuracies or false information
⚠️ **Risk Assessment** - Evaluate potential risks for sensitive actions
✅ **Quality Assurance** - Ensure responses meet professional standards

I'm particularly useful for:
• Validating complex or sensitive information
• Building consensus on important decisions  
• Assessing confidence in AI-generated responses
• Evaluating approval requests from other agents

How can I help validate or assess something for you today?"""
        
        return {
            "response": greeting,
            "requires_approval": False,
            "metadata": {
                "agent_id": self.agent_id,
                "message_type": "greeting"
            }
        }
    
    async def validate_response(self, validation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a response from another agent"""
        try:
            original_query = validation_context.get("original_query", "")
            agent_response = validation_context.get("agent_response", "")
            responding_agent = validation_context.get("responding_agent", "unknown")
            intent = validation_context.get("intent", "")
            
            # Get multiple perspectives on the same question
            consensus_data = await self._build_consensus(original_query, intent)
            
            # Validate the agent's response against consensus
            validation_result = await self._validate_against_consensus(
                agent_response, 
                consensus_data,
                responding_agent
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(validation_result, consensus_data)
            
            # Assess risk level
            risk_assessment = self._assess_response_risk(agent_response, responding_agent)
            
            # Determine recommendation
            recommendation = self._make_recommendation(confidence_score, risk_assessment, validation_result)
            
            return {
                "confidence_score": confidence_score,
                "risk_assessment": risk_assessment,
                "recommendation": recommendation,
                "reasoning": validation_result.get("reasoning", ""),
                "consensus_sources": [source["name"] for source in consensus_data],
                "validated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating response: {e}")
            return {
                "confidence_score": 0.5,
                "risk_assessment": "unknown",
                "recommendation": "review",
                "reasoning": f"Validation failed due to error: {str(e)}",
                "consensus_sources": [],
                "validated_at": datetime.utcnow().isoformat()
            }
    
    async def _build_consensus(self, query: str, intent: str = "") -> List[Dict[str, Any]]:
        """Build consensus by querying multiple LLM sources"""
        try:
            consensus_sources = []
            
            # Query OpenAI (if available)
            if settings.OPENAI_API_KEY and self.primary_llm:
                try:
                    openai_response = await self.primary_llm.generate_response(
                        messages=[{"role": "user", "content": query}],
                        mode="online",
                        model="gpt-4-turbo-preview"
                    )
                    consensus_sources.append({
                        "name": "OpenAI GPT-4",
                        "response": openai_response,
                        "confidence": 0.9
                    })
                except Exception as e:
                    logger.warning(f"OpenAI consensus query failed: {e}")
            
            # Query Perplexity (if available)
            if settings.PERPLEXITY_API_KEY and self.primary_llm:
                try:
                    # Use Perplexity for research-based queries
                    perplexity_response = await self.primary_llm._generate_perplexity_response(
                        messages=[{"role": "user", "content": query}],
                        temperature=0.3,
                        max_tokens=1000
                    )
                    consensus_sources.append({
                        "name": "Perplexity AI",
                        "response": perplexity_response,
                        "confidence": 0.85
                    })
                except Exception as e:
                    logger.warning(f"Perplexity consensus query failed: {e}")
            
            # Query local model (Ollama)
            if self.primary_llm:
                try:
                    local_response = await self.primary_llm.generate_response(
                        messages=[{"role": "user", "content": query}],
                        mode="offline",
                        model="llama3:70b"  # Use larger model for better consensus
                    )
                    consensus_sources.append({
                        "name": "Local LLM (Llama3-70B)",
                        "response": local_response,
                        "confidence": 0.75
                    })
                except Exception as e:
                    logger.warning(f"Local LLM consensus query failed: {e}")
            
            return consensus_sources
            
        except Exception as e:
            logger.error(f"Error building consensus: {e}")
            return []
    
    async def _validate_against_consensus(
        self, 
        agent_response: str, 
        consensus_data: List[Dict[str, Any]], 
        responding_agent: str
    ) -> Dict[str, Any]:
        """Validate agent response against consensus"""
        try:
            if not consensus_data:
                return {
                    "validation_score": 0.5,
                    "reasoning": "Unable to build consensus for validation",
                    "agreements": [],
                    "disagreements": [],
                    "hallucination_risk": "unknown"
                }
            
            # Compare agent response with consensus
            validation_prompt = f"""Analyze this agent response against multiple consensus sources:

**Agent Response ({responding_agent}):**
{agent_response}

**Consensus Sources:**
{self._format_consensus_sources(consensus_data)}

Please evaluate:
1. **Factual Accuracy**: Are the facts consistent across sources?
2. **Completeness**: Does the response address the question fully?
3. **Consistency**: How well does it align with consensus?
4. **Hallucination Risk**: Any potential false information?
5. **Quality**: Is the response helpful and appropriate?

Provide a validation score (0.0-1.0) and detailed reasoning."""
            
            validation_analysis = await self._generate_response(
                [{"role": "user", "content": validation_prompt}],
                mode="online"
            )
            
            # Extract validation score and details
            validation_score = self._extract_validation_score(validation_analysis)
            
            return {
                "validation_score": validation_score,
                "reasoning": validation_analysis,
                "agreements": self._find_agreements(agent_response, consensus_data),
                "disagreements": self._find_disagreements(agent_response, consensus_data),
                "hallucination_risk": self._assess_hallucination_risk(validation_score)
            }
            
        except Exception as e:
            logger.error(f"Error validating against consensus: {e}")
            return {
                "validation_score": 0.5,
                "reasoning": f"Validation analysis failed: {str(e)}",
                "agreements": [],
                "disagreements": [],
                "hallucination_risk": "unknown"
            }
    
    def _calculate_confidence_score(self, validation_result: Dict[str, Any], consensus_data: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence score"""
        try:
            # Base confidence from validation
            base_score = validation_result.get("validation_score", 0.5)
            
            # Adjust based on consensus strength
            consensus_strength = len(consensus_data) / 3.0  # Normalize to 0-1
            
            # Adjust based on source reliability
            source_reliability = sum(source.get("confidence", 0.5) for source in consensus_data) / max(len(consensus_data), 1)
            
            # Calculate weighted confidence
            confidence = (base_score * 0.5 + consensus_strength * 0.3 + source_reliability * 0.2)
            
            return min(max(confidence, 0.0), 1.0)  # Clamp between 0 and 1
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0.5
    
    def _assess_response_risk(self, response: str, agent_id: str) -> str:
        """Assess risk level of response"""
        try:
            # High-risk indicators
            high_risk_terms = ["delete", "format", "remove", "destroy", "irreversible", "permanent"]
            medium_risk_terms = ["modify", "change", "alter", "update", "install"]
            
            response_lower = response.lower()
            
            if any(term in response_lower for term in high_risk_terms):
                return "high"
            elif any(term in response_lower for term in medium_risk_terms):
                return "medium"
            elif agent_id in ["alex"]:  # System agent actions need review
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            logger.error(f"Error assessing response risk: {e}")
            return "medium"
    
    def _make_recommendation(self, confidence_score: float, risk_level: str, validation_result: Dict[str, Any]) -> str:
        """Make recommendation based on confidence and risk"""
        try:
            hallucination_risk = validation_result.get("hallucination_risk", "unknown")
            
            # High confidence, low risk - approve
            if confidence_score >= 0.8 and risk_level == "low":
                return "approve"
            
            # Low confidence or high hallucination risk - reject
            elif confidence_score < 0.4 or hallucination_risk == "high":
                return "reject"
            
            # High risk always needs review
            elif risk_level in ["high", "critical"]:
                return "review"
            
            # Medium confidence/risk - review
            else:
                return "review"
                
        except Exception as e:
            logger.error(f"Error making recommendation: {e}")
            return "review"
    
    def _format_consensus_sources(self, consensus_data: List[Dict[str, Any]]) -> str:
        """Format consensus sources for prompt"""
        formatted = []
        for i, source in enumerate(consensus_data, 1):
            formatted.append(f"{i}. **{source['name']}**: {source['response'][:300]}...")
        return "\n".join(formatted)
    
    def _extract_validation_score(self, analysis: str) -> float:
        """Extract validation score from analysis text"""
        try:
            import re
            
            # Look for score patterns
            patterns = [
                r'validation score[:\s]*([0-9]*\.?[0-9]+)',
                r'score[:\s]*([0-9]*\.?[0-9]+)',
                r'confidence[:\s]*([0-9]*\.?[0-9]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, analysis.lower())
                if match:
                    score = float(match.group(1))
                    return min(max(score, 0.0), 1.0) if score <= 1.0 else score / 10.0
            
            # Default to medium confidence if no score found
            return 0.6
            
        except Exception as e:
            logger.error(f"Error extracting validation score: {e}")
            return 0.5
    
    def _find_agreements(self, response: str, consensus_data: List[Dict[str, Any]]) -> List[str]:
        """Find points of agreement between response and consensus"""
        # Simplified implementation - could be enhanced with NLP
        agreements = []
        if len(consensus_data) >= 2:
            agreements.append("Multiple sources provide consistent information")
        return agreements
    
    def _find_disagreements(self, response: str, consensus_data: List[Dict[str, Any]]) -> List[str]:
        """Find points of disagreement"""
        # Simplified implementation
        disagreements = []
        if len(consensus_data) < 2:
            disagreements.append("Limited consensus data available for comparison")
        return disagreements
    
    def _assess_hallucination_risk(self, validation_score: float) -> str:
        """Assess hallucination risk based on validation score"""
        if validation_score >= 0.8:
            return "low"
        elif validation_score >= 0.5:
            return "medium"
        else:
            return "high"
    
    async def _handle_validation_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle explicit validation requests"""
        try:
            # Extract what needs validation
            validation_target = await self._extract_validation_target(message, mode)
            
            if not validation_target:
                return {
                    "response": """I'd be happy to help validate information or responses! Please specify what you'd like me to validate:

🔍 **I can validate:**
• Factual information or claims
• AI-generated responses from other agents
• Research findings or data
• Decision recommendations
• Technical information

📋 **Please provide:**
• The specific information to validate
• The source or context
• What aspects you're concerned about

**Example:** "Please validate this response about stock market trends" or "Can you fact-check this information about climate change?"

What would you like me to validate?""",
                    "requires_approval": False,
                    "metadata": {"needs_validation_target": True}
                }
            
            # Perform validation
            validation_result = await self._perform_validation(validation_target, mode)
            
            return {
                "response": validation_result,
                "requires_approval": False,
                "metadata": {
                    "validation_performed": True,
                    "validation_type": validation_target.get("type", "general")
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling validation request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _extract_validation_target(self, message: str, mode: str) -> Dict[str, Any]:
        """Extract what needs to be validated from the message"""
        try:
            prompt = f"""Extract validation details from: "{message}"
            
            Return JSON with:
            - type: validation type (fact_check, response_validation, data_validation, etc.)
            - content: the specific content to validate
            - source: source of the information if mentioned
            - concerns: specific concerns or aspects to focus on"""
            
            return await self._extract_structured_info(prompt, mode)
            
        except Exception as e:
            logger.error(f"Error extracting validation target: {e}")
            return {}
    
    async def _perform_validation(self, validation_target: Dict[str, Any], mode: str) -> str:
        """Perform validation based on the target"""
        try:
            content = validation_target.get("content", "")
            validation_type = validation_target.get("type", "general")
            
            if validation_type == "fact_check":
                return await self._fact_check(content, mode)
            elif validation_type == "response_validation":
                return await self._validate_ai_response(content, mode)
            else:
                return await self._general_validation(content, mode)
                
        except Exception as e:
            logger.error(f"Error performing validation: {e}")
            return "Unable to complete validation due to processing error."
    
    async def _fact_check(self, content: str, mode: str) -> str:
        """Fact-check specific content"""
        try:
            # Build consensus from multiple sources
            consensus_data = await self._build_consensus(f"Fact-check this information: {content}")
            
            if not consensus_data:
                return "⚠️ Unable to fact-check - insufficient data sources available."
            
            # Analyze consensus
            fact_check_prompt = f"""Fact-check this statement using the provided sources:

**Statement to verify:** {content}

**Sources:**
{self._format_consensus_sources(consensus_data)}

Please provide:
1. **Verification Status**: True, False, Partially True, or Unverifiable
2. **Supporting Evidence**: What supports or contradicts the statement
3. **Confidence Level**: How certain are you (High/Medium/Low)
4. **Additional Context**: Important nuances or caveats
5. **Sources**: Which sources provide the most reliable information

Format as a clear fact-check report."""
            
            fact_check_result = await self._generate_response([{"role": "user", "content": fact_check_prompt}], mode)
            
            return f"🔍 **Fact-Check Report**\n\n{fact_check_result}\n\n**Verification completed using {len(consensus_data)} independent sources**"
            
        except Exception as e:
            logger.error(f"Error in fact-checking: {e}")
            return "❌ Fact-check failed due to processing error."
    
    async def _validate_ai_response(self, response: str, mode: str) -> str:
        """Validate an AI-generated response"""
        try:
            validation_context = {
                "agent_response": response,
                "original_query": "General validation request",
                "responding_agent": "unknown",
                "intent": "validation"
            }
            
            validation_result = await self.validate_response(validation_context)
            
            confidence = validation_result["confidence_score"]
            risk = validation_result["risk_assessment"]
            recommendation = validation_result["recommendation"]
            
            status_emoji = "✅" if recommendation == "approve" else "⚠️" if recommendation == "review" else "❌"
            
            return f"""{status_emoji} **AI Response Validation Report**

**Confidence Score:** {confidence:.1%}
**Risk Level:** {risk.upper()}
**Recommendation:** {recommendation.upper()}

**Analysis:**
{validation_result.get("reasoning", "No detailed analysis available")}

**Consensus Sources:** {len(validation_result.get("consensus_sources", []))} sources consulted

**Overall Assessment:** 
{self._get_assessment_message(confidence, risk, recommendation)}"""
            
        except Exception as e:
            logger.error(f"Error validating AI response: {e}")
            return "❌ Response validation failed due to processing error."
    
    def _get_assessment_message(self, confidence: float, risk: str, recommendation: str) -> str:
        """Get human-readable assessment message"""
        if recommendation == "approve":
            return "This response appears accurate and reliable with strong consensus support."
        elif recommendation == "review":
            return "This response requires additional review before full acceptance."
        else:
            return "This response has significant concerns and should be approached with caution."
    
    async def _handle_consensus_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle consensus building requests"""
        try:
            # Build consensus on the question
            consensus_data = await self._build_consensus(message)
            
            if not consensus_data:
                return {
                    "response": "I'm unable to build consensus at the moment due to limited access to multiple AI sources. Please try again later.",
                    "requires_approval": False,
                    "metadata": {"consensus_failed": True}
                }
            
            # Analyze and synthesize consensus
            consensus_analysis = await self._synthesize_consensus(message, consensus_data, mode)
            
            return {
                "response": consensus_analysis,
                "requires_approval": False,
                "metadata": {
                    "consensus_built": True,
                    "sources_consulted": len(consensus_data)
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling consensus request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _synthesize_consensus(self, query: str, consensus_data: List[Dict[str, Any]], mode: str) -> str:
        """Synthesize consensus from multiple sources"""
        try:
            synthesis_prompt = f"""Synthesize a consensus answer from these multiple AI sources:

**Original Question:** {query}

**Sources:**
{self._format_consensus_sources(consensus_data)}

Please provide:
1. **Consensus Answer**: The most accurate and balanced response
2. **Areas of Agreement**: What all sources agree on
3. **Areas of Disagreement**: Where sources differ
4. **Confidence Assessment**: Overall reliability of the consensus
5. **Recommended Action**: Based on the consensus

Format as a comprehensive consensus report."""
            
            synthesis = await self._generate_response([{"role": "user", "content": synthesis_prompt}], mode)
            
            return f"""🤝 **Consensus Report**

**Sources Consulted:** {len(consensus_data)} independent AI models

{synthesis}

**Methodology:** This consensus was built by consulting multiple AI sources and identifying areas of agreement and disagreement to provide the most balanced and accurate response possible."""
            
        except Exception as e:
            logger.error(f"Error synthesizing consensus: {e}")
            return "Unable to synthesize consensus due to processing error."
    
    async def _handle_risk_assessment(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle risk assessment requests"""
        try:
            # Extract risk assessment target
            risk_target = await self._extract_risk_target(message, mode)
            
            if not risk_target:
                return {
                    "response": """I can help assess risks for various scenarios! Please specify what you'd like me to evaluate:

⚠️ **Risk Assessment Types:**
• **Action Risk**: Potential consequences of a proposed action
• **Investment Risk**: Financial and market risks
• **System Risk**: Technical or operational risks
• **Decision Risk**: Potential outcomes of different choices

📋 **Please provide:**
• The specific action, decision, or scenario to assess
• Context and background information
• Your concerns or risk factors to consider
• Timeline and impact scope

**Example:** "Assess the risks of implementing this new software system" or "What are the risks of this investment strategy?"

What would you like me to assess?""",
                    "requires_approval": False,
                    "metadata": {"needs_risk_target": True}
                }
            
            # Perform risk assessment
            risk_assessment = await self._perform_risk_assessment(risk_target, mode)
            
            return {
                "response": risk_assessment,
                "requires_approval": False,
                "metadata": {
                    "risk_assessment_performed": True,
                    "risk_type": risk_target.get("type", "general")
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling risk assessment: {e}")
            return await self.handle_error(str(e), {})
    
    async def _extract_risk_target(self, message: str, mode: str) -> Dict[str, Any]:
        """Extract risk assessment target"""
        try:
            prompt = f"""Extract risk assessment details from: "{message}"
            
            Return JSON with:
            - type: risk type (action, investment, system, decision, etc.)
            - scenario: the specific scenario to assess
            - context: background information
            - concerns: specific risks or concerns mentioned
            - timeline: timeframe if mentioned"""
            
            return await self._extract_structured_info(prompt, mode)
            
        except Exception as e:
            logger.error(f"Error extracting risk target: {e}")
            return {}
    
    async def _perform_risk_assessment(self, risk_target: Dict[str, Any], mode: str) -> str:
        """Perform comprehensive risk assessment"""
        try:
            scenario = risk_target.get("scenario", "")
            risk_type = risk_target.get("type", "general")
            context = risk_target.get("context", "")
            
            # Get multiple perspectives on risk
            consensus_data = await self._build_consensus(f"Assess the risks of: {scenario}. Context: {context}")
            
            risk_prompt = f"""Perform a comprehensive risk assessment:

**Scenario:** {scenario}
**Type:** {risk_type}
**Context:** {context}

{self._format_consensus_sources(consensus_data) if consensus_data else ""}

Please provide:
1. **Risk Level**: Overall risk rating (Low/Medium/High/Critical)
2. **Key Risk Factors**: Primary risks and their likelihood
3. **Potential Impact**: Consequences if risks materialize
4. **Mitigation Strategies**: How to reduce or manage risks
5. **Risk-Benefit Analysis**: Weighing risks against benefits
6. **Recommendations**: Proceed, modify approach, or avoid

Use a structured format with clear risk ratings and actionable insights."""
            
            risk_analysis = await self._generate_response([{"role": "user", "content": risk_prompt}], mode)
            
            return f"""⚠️ **Risk Assessment Report**

{risk_analysis}

**Assessment Methodology:** This analysis considered multiple perspectives and potential scenarios to provide a comprehensive risk evaluation.

**Next Steps:** Review the mitigation strategies and consider implementing recommended safeguards before proceeding."""
            
        except Exception as e:
            logger.error(f"Error performing risk assessment: {e}")
            return "❌ Risk assessment failed due to processing error."
    
    async def _handle_general_validation_request(self, messages: List[Dict[str, Any]], context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle general validation and judgment requests"""
        try:
            user_message = messages[-1]["content"]
            
            # Determine if this is a validation, consensus, or risk assessment need
            if any(word in user_message.lower() for word in ["validate", "verify", "check", "confirm"]):
                return await self._handle_validation_request(user_message, context, mode)
            elif any(word in user_message.lower() for word in ["consensus", "agree", "sources", "confirm"]):
                return await self._handle_consensus_request(user_message, context, mode)
            elif any(word in user_message.lower() for word in ["risk", "danger", "safe", "assess"]):
                return await self._handle_risk_assessment(user_message, context, mode)
            else:
                # General judgment request
                return await self._provide_general_judgment(messages, context, mode)
                
        except Exception as e:
            logger.error(f"Error handling general validation request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _provide_general_judgment(self, messages: List[Dict[str, Any]], context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Provide general judgment and analysis"""
        try:
            user_message = messages[-1]["content"]
            
            # Add Judy's analytical context
            enhanced_messages = messages.copy()
            system_message = """You are Judy, an impartial judge and validator. Provide balanced, analytical responses with multiple perspectives. Always consider potential risks and benefits, and provide confidence assessments where appropriate."""
            
            if enhanced_messages and enhanced_messages[0]["role"] == "system":
                enhanced_messages[0]["content"] += " " + system_message
            else:
                enhanced_messages.insert(0, {"role": "system", "content": system_message})
            
            response = await self._generate_response(enhanced_messages, mode, context)
            
            # Store interaction in memory
            await self.store_memory(
                content=f"Judgment request: {user_message}\nJudy analysis: {response[:200]}...",
                content_type="judgment_analysis",
                tags=["judgment", "analysis", "validation"]
            )
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "judgment_provided": True,
                    "analysis_type": "general"
                }
            }
            
        except Exception as e:
            logger.error(f"Error providing general judgment: {e}")
            return await self.handle_error(str(e), {})
    
    async def _extract_structured_info(self, prompt: str, mode: str) -> Dict[str, Any]:
        """Extract structured information using LLM"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._generate_response(messages, mode)
            
            # Try to parse as JSON
            try:
                import json
                return json.loads(response)
            except json.JSONDecodeError:
                # Extract JSON from response if it's embedded in text
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {}
                
        except Exception as e:
            logger.error(f"Error extracting structured info: {e}")
            return {}
    
    async def _general_validation(self, content: str, mode: str) -> str:
        """Perform general validation"""
        try:
            validation_prompt = f"""Analyze and validate this content: "{content}"

Provide assessment on:
1. **Accuracy**: Is the information factually correct?
2. **Completeness**: Is important information missing?
3. **Clarity**: Is it clear and well-presented?
4. **Reliability**: How trustworthy is this information?
5. **Context**: Is proper context provided?

Give an overall validation rating and recommendations."""
            
            return await self._generate_response([{"role": "user", "content": validation_prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error in general validation: {e}")
            return "Unable to complete validation analysis."