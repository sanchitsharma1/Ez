import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import os

from agents.base_agent import BaseAgent
from services.file_service import FileService
from utils.knowledge_manager import KnowledgeManager
from core.config import settings

logger = logging.getLogger(__name__)

class SofiaAgent(BaseAgent):
    """Sofia - Knowledge Management and Content Creation Specialist"""
    
    def __init__(self):
        super().__init__(
            agent_id="sofia",
            name="Sofia",
            persona="""You are Sofia, an intellectual and articulate knowledge specialist. 
            You excel at processing documents, extracting insights, building knowledge bases, and creating 
            high-quality content. You're thorough in your analysis, eloquent in your writing, and passionate 
            about organizing information in meaningful ways. You help users understand complex topics and 
            create compelling written content."""
        )
        
        self.capabilities = [
            "document_processing",
            "text_summarization",
            "knowledge_base_management",
            "content_creation",
            "research_analysis",
            "essay_writing"
        ]
        
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Female voice for Sofia
        
        # Services
        self.file_service: Optional[FileService] = None
        self.knowledge_manager: Optional[KnowledgeManager] = None
    
    async def _initialize_agent(self):
        """Initialize Sofia-specific services"""
        try:
            self.file_service = FileService()
            await self.file_service.initialize()
            
            self.knowledge_manager = KnowledgeManager()
            await self.knowledge_manager.initialize()
            
            logger.info("Sofia agent initialized with document processing and knowledge management")
            
        except Exception as e:
            logger.error(f"Failed to initialize Sofia's services: {e}")
            raise
    
    def _get_agent_instructions(self) -> str:
        """Get Sofia-specific instructions"""
        return """
        As Sofia, you should:
        
        1. DOCUMENT PROCESSING:
           - Analyze PDFs, Word documents, and text files
           - Extract key information and themes
           - Create comprehensive summaries
           - Identify important quotes and references
        
        2. KNOWLEDGE BASE MANAGEMENT:
           - Store and organize processed information
           - Build searchable knowledge repositories
           - Create topic taxonomies and tags
           - Maintain information relationships
        
        3. CONTENT CREATION:
           - Write essays, reports, and articles
           - Create structured documents with proper formatting
           - Develop compelling narratives from data
           - Generate creative and analytical content
        
        4. RESEARCH ANALYSIS:
           - Synthesize information from multiple sources
           - Identify patterns and insights
           - Compare and contrast different perspectives
           - Provide evidence-based conclusions
        
        5. WRITING ASSISTANCE:
           - Help improve writing quality and style
           - Suggest structural improvements
           - Enhance clarity and coherence
           - Provide editing recommendations
        
        Always provide well-structured, thoughtful responses with proper citations when referencing sources.
        Focus on clarity, accuracy, and intellectual depth in all communications.
        """
    
    async def process_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process message as Sofia"""
        try:
            messages = context.get("messages", [])
            intent = context.get("intent", "knowledge_query")
            user_context = context.get("context", {})
            mode = context.get("mode", "online")
            
            if not messages:
                return await self._generate_greeting()
            
            user_message = messages[-1]["content"]
            
            # Route to specific handler based on intent
            if intent == "document_processing":
                return await self._handle_document_processing(user_message, user_context, mode)
            elif intent == "knowledge_query":
                return await self._handle_knowledge_query(user_message, user_context, mode)
            elif intent == "content_generation":
                return await self._handle_content_generation(user_message, user_context, mode)
            elif intent == "text_summarization":
                return await self._handle_summarization(user_message, user_context, mode)
            else:
                return await self._handle_general_knowledge_request(messages, user_context, mode)
                
        except Exception as e:
            logger.error(f"Error processing message in Sofia: {e}")
            return await self.handle_error(str(e), context)
    
    async def _generate_greeting(self) -> Dict[str, Any]:
        """Generate Sofia's greeting"""
        greeting = """Hello! I'm Sofia, your knowledge management and content creation specialist. I'm here to help you with:

📄 **Document Processing** - Analyze and summarize PDFs, documents, and texts
🧠 **Knowledge Management** - Build and query searchable knowledge bases
✍️ **Content Creation** - Write essays, reports, and compelling content
🔍 **Research Analysis** - Synthesize insights from multiple sources
📚 **Writing Assistance** - Improve clarity, structure, and style

What knowledge task can I assist you with today?"""
        
        return {
            "response": greeting,
            "requires_approval": False,
            "metadata": {
                "agent_id": self.agent_id,
                "message_type": "greeting"
            }
        }
    
    async def _handle_document_processing(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle document processing requests"""
        try:
            # Check if file is mentioned or attached
            file_info = context.get("uploaded_file") or await self._extract_file_reference(message)
            
            if not file_info:
                return {
                    "response": """I'd be happy to process a document for you! Please upload or specify the document you'd like me to analyze. I can work with:

📄 **Supported formats:** PDF, DOC/DOCX, TXT, RTF
🔍 **Analysis types:** Summarization, key points extraction, theme analysis, fact extraction
📊 **Output formats:** Executive summary, detailed analysis, bullet points, structured report

Simply upload your file and let me know what type of analysis you need.""",
                    "requires_approval": False,
                    "metadata": {"needs_file_upload": True}
                }
            
            # Process the document
            return await self._process_document(file_info, message, mode)
            
        except Exception as e:
            logger.error(f"Error handling document processing: {e}")
            return await self.handle_error(str(e), {})
    
    async def _process_document(self, file_info: Dict[str, Any], user_request: str, mode: str) -> Dict[str, Any]:
        """Process uploaded document"""
        try:
            if not self.file_service:
                return await self.handle_error("File service not available", {})
            
            # Extract text from document
            text_content = await self.file_service.extract_text(
                file_info["file_path"], 
                file_info.get("file_type", "")
            )
            
            if not text_content:
                return {
                    "response": "I wasn't able to extract readable text from the uploaded file. Please ensure the file is not corrupted and is in a supported format (PDF, DOC, DOCX, TXT).",
                    "requires_approval": False,
                    "metadata": {"extraction_failed": True}
                }
            
            # Determine analysis type from user request
            analysis_type = await self._determine_analysis_type(user_request, mode)
            
            # Perform analysis
            if analysis_type == "summary":
                result = await self._create_summary(text_content, user_request, mode)
            elif analysis_type == "key_points":
                result = await self._extract_key_points(text_content, user_request, mode)
            elif analysis_type == "theme_analysis":
                result = await self._analyze_themes(text_content, user_request, mode)
            else:
                result = await self._comprehensive_analysis(text_content, user_request, mode)
            
            # Store in knowledge base
            await self._store_processed_document(
                file_info["filename"], 
                text_content, 
                result, 
                analysis_type
            )
            
            response = f"""📄 **Document Analysis Complete**

**File:** {file_info.get('filename', 'Unknown')}
**Type:** {analysis_type.replace('_', ' ').title()}
**Content Length:** {len(text_content)} characters

{result}

The document has been added to your knowledge base for future reference."""
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "document_processed": True,
                    "analysis_type": analysis_type,
                    "content_length": len(text_content),
                    "filename": file_info.get("filename")
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return await self.handle_error(str(e), {})
    
    async def _create_summary(self, content: str, user_request: str, mode: str) -> str:
        """Create document summary"""
        try:
            # Split content into chunks if too long
            chunks = self._split_content(content, max_length=3000)
            
            if len(chunks) == 1:
                # Single chunk - direct summarization
                prompt = f"""Please create a comprehensive summary of the following document:

{content[:3000]}

Focus on:
- Main topics and themes
- Key findings and conclusions
- Important facts and figures
- Actionable insights

User's specific request: {user_request}"""
                
                return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
            else:
                # Multiple chunks - summarize each then create master summary
                chunk_summaries = []
                
                for i, chunk in enumerate(chunks):
                    prompt = f"""Summarize this section (part {i+1} of {len(chunks)}) of a larger document:

{chunk}

Focus on key points and main ideas."""
                    
                    chunk_summary = await self._generate_response([{"role": "user", "content": prompt}], mode)
                    chunk_summaries.append(chunk_summary)
                
                # Create master summary
                master_prompt = f"""Create a comprehensive summary from these section summaries:

{' '.join(chunk_summaries)}

Provide a cohesive overview that captures the document's main themes, findings, and insights."""
                
                return await self._generate_response([{"role": "user", "content": master_prompt}], mode)
                
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return "Unable to create summary due to processing error."
    
    async def _extract_key_points(self, content: str, user_request: str, mode: str) -> str:
        """Extract key points from document"""
        try:
            prompt = f"""Extract the key points from the following document in a structured format:

{content[:4000]}

Please organize as:
**Main Topics:**
- [Topic 1]
- [Topic 2]

**Key Findings:**
- [Finding 1]
- [Finding 2]

**Important Facts:**
- [Fact 1]
- [Fact 2]

**Actionable Items:**
- [Action 1]
- [Action 2]

User's focus: {user_request}"""
            
            return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error extracting key points: {e}")
            return "Unable to extract key points due to processing error."
    
    async def _handle_knowledge_query(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle knowledge base queries"""
        try:
            if not self.knowledge_manager:
                return await self.handle_error("Knowledge management service not available", {})
            
            # Search knowledge base
            search_results = await self.knowledge_manager.search_knowledge(
                query=message,
                limit=5,
                content_types=["document", "summary", "analysis"]
            )
            
            if not search_results:
                return {
                    "response": f"""I couldn't find specific information about "{message}" in the knowledge base. 

Would you like me to:
🔍 Research this topic online
📄 Help you upload relevant documents
✍️ Create content on this subject

What would be most helpful?""",
                    "requires_approval": False,
                    "metadata": {"no_results": True, "query": message}
                }
            
            # Generate response based on search results
            context_info = "\n".join([
                f"**{result.get('title', 'Untitled')}**: {result.get('content', '')[:200]}..."
                for result in search_results[:3]
            ])
            
            response_prompt = f"""Based on the following information from the knowledge base, answer this question: "{message}"

Available information:
{context_info}

Provide a comprehensive answer with proper citations to the source documents."""
            
            response = await self._generate_response([{"role": "user", "content": response_prompt}], mode)
            
            # Add source references
            sources = [f"- {result.get('title', 'Untitled Document')}" for result in search_results[:3]]
            response += f"\n\n**Sources:**\n" + "\n".join(sources)
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "search_results": len(search_results),
                    "sources_used": len(sources)
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling knowledge query: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_content_generation(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle content creation requests"""
        try:
            # Extract content requirements
            content_requirements = await self._extract_content_requirements(message, mode)
            
            if not content_requirements.get("type"):
                return {
                    "response": """I'd be happy to help create content for you! Please specify:

✍️ **Content Types I can create:**
- Essays and articles
- Reports and summaries
- Blog posts and web content
- Technical documentation
- Creative writing
- Research papers

📋 **Please provide:**
- Content type and purpose
- Target audience
- Key topics to cover
- Desired length/format
- Any specific requirements

What would you like me to write?""",
                    "requires_approval": False,
                    "metadata": {"needs_content_spec": True}
                }
            
            # Generate content based on requirements
            content = await self._generate_content(content_requirements, mode)
            
            # Store generated content
            await self._store_generated_content(content_requirements, content)
            
            return {
                "response": content,
                "requires_approval": False,
                "metadata": {
                    "content_generated": True,
                    "content_type": content_requirements.get("type"),
                    "word_count": len(content.split())
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling content generation: {e}")
            return await self.handle_error(str(e), {})
    
    async def _generate_content(self, requirements: Dict[str, Any], mode: str) -> str:
        """Generate content based on requirements"""
        try:
            content_type = requirements.get("type", "article")
            topic = requirements.get("topic", "")
            audience = requirements.get("audience", "general")
            length = requirements.get("length", "medium")
            
            # Get relevant knowledge from knowledge base
            knowledge_context = ""
            if self.knowledge_manager:
                related_info = await self.knowledge_manager.search_knowledge(
                    query=topic,
                    limit=3
                )
                if related_info:
                    knowledge_context = "Relevant information from knowledge base:\n"
                    knowledge_context += "\n".join([
                        f"- {info.get('content', '')[:300]}..."
                        for info in related_info
                    ])
            
            prompt = f"""Create a high-quality {content_type} on the topic: "{topic}"

**Requirements:**
- Target audience: {audience}
- Length: {length}
- Format: Well-structured with headers and sections
- Style: Professional and engaging

{knowledge_context}

**Additional specifications:**
{requirements.get('additional_specs', 'None')}

Please create compelling, well-researched content that is informative and engaging."""
            
            return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return "Unable to generate content due to processing error."
    
    async def _extract_content_requirements(self, message: str, mode: str) -> Dict[str, Any]:
        """Extract content creation requirements from message"""
        try:
            prompt = f"""Extract content creation requirements from: "{message}"

Return JSON with:
- type: content type (essay, article, report, etc.)
- topic: main subject/topic
- audience: target audience
- length: desired length (short, medium, long)
- additional_specs: any other requirements"""
            
            return await self._extract_structured_info(prompt, mode)
            
        except Exception as e:
            logger.error(f"Error extracting content requirements: {e}")
            return {}
    
    async def _determine_analysis_type(self, user_request: str, mode: str) -> str:
        """Determine what type of analysis to perform"""
        request_lower = user_request.lower()
        
        if any(word in request_lower for word in ["summary", "summarize", "overview"]):
            return "summary"
        elif any(word in request_lower for word in ["key points", "bullet points", "main points"]):
            return "key_points"
        elif any(word in request_lower for word in ["themes", "topics", "analyze themes"]):
            return "theme_analysis"
        else:
            return "comprehensive"
    
    def _split_content(self, content: str, max_length: int = 3000) -> List[str]:
        """Split long content into manageable chunks"""
        if len(content) <= max_length:
            return [content]
        
        chunks = []
        words = content.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 > max_length:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    async def _analyze_themes(self, content: str, user_request: str, mode: str) -> str:
        """Analyze themes in document"""
        try:
            prompt = f"""Analyze the themes and topics in this document:

{content[:4000]}

Please provide:
**Major Themes:**
1. [Theme 1] - [Description]
2. [Theme 2] - [Description]

**Supporting Topics:**
- [Topic 1]
- [Topic 2]

**Recurring Concepts:**
- [Concept 1]
- [Concept 2]

**Tone and Style:**
- [Analysis of writing style and tone]

User's specific interest: {user_request}"""
            
            return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error analyzing themes: {e}")
            return "Unable to analyze themes due to processing error."
    
    async def _comprehensive_analysis(self, content: str, user_request: str, mode: str) -> str:
        """Perform comprehensive document analysis"""
        try:
            # Split into multiple focused analyses
            analyses = []
            
            # Summary
            summary = await self._create_summary(content, user_request, mode)
            analyses.append(f"**Executive Summary:**\n{summary}")
            
            # Key points
            key_points = await self._extract_key_points(content, user_request, mode)
            analyses.append(f"**Key Points Analysis:**\n{key_points}")
            
            # Themes (for longer documents)
            if len(content) > 1000:
                themes = await self._analyze_themes(content, user_request, mode)
                analyses.append(f"**Theme Analysis:**\n{themes}")
            
            return "\n\n".join(analyses)
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return "Unable to complete comprehensive analysis due to processing error."
    
    async def _store_processed_document(self, filename: str, content: str, analysis: str, analysis_type: str):
        """Store processed document in knowledge base"""
        try:
            if not self.knowledge_manager:
                return
            
            # Create document hash for deduplication
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            await self.knowledge_manager.store_knowledge(
                title=f"{analysis_type.title()} - {filename}",
                content=analysis,
                content_type=analysis_type,
                source_file=filename,
                tags=[analysis_type, "document_analysis", "processed"],
                metadata={
                    "original_filename": filename,
                    "content_hash": content_hash,
                    "processed_at": datetime.utcnow().isoformat(),
                    "content_length": len(content)
                }
            )
            
            # Store memory for retrieval
            await self.store_memory(
                content=f"Processed document: {filename}\nAnalysis type: {analysis_type}\nSummary: {analysis[:200]}...",
                content_type="document_processing",
                tags=["document", filename, analysis_type]
            )
            
        except Exception as e:
            logger.error(f"Error storing processed document: {e}")
    
    async def _store_generated_content(self, requirements: Dict[str, Any], content: str):
        """Store generated content"""
        try:
            if not self.knowledge_manager:
                return
            
            content_type = requirements.get("type", "article")
            topic = requirements.get("topic", "Generated Content")
            
            await self.knowledge_manager.store_knowledge(
                title=f"{content_type.title()}: {topic}",
                content=content,
                content_type="generated_content",
                tags=["generated", content_type, "content_creation"],
                metadata={
                    "requirements": requirements,
                    "generated_at": datetime.utcnow().isoformat(),
                    "word_count": len(content.split())
                }
            )
            
            # Store memory
            await self.store_memory(
                content=f"Generated {content_type} on topic: {topic}\nLength: {len(content.split())} words",
                content_type="content_generation",
                tags=["content", content_type, topic.lower().replace(" ", "_")]
            )
            
        except Exception as e:
            logger.error(f"Error storing generated content: {e}")
    
    async def _extract_file_reference(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract file references from message"""
        # This would extract file paths or names mentioned in the message
        # For now, return None (file upload handled by frontend)
        return None
    
    async def _handle_summarization(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle text summarization requests"""
        try:
            # Check if there's text content to summarize
            text_content = context.get("text_content")
            
            if not text_content:
                # Extract text from message
                if len(message) < 200:
                    return {
                        "response": "Please provide the text you'd like me to summarize, or upload a document. For best results, I need at least a few paragraphs of content to work with.",
                        "requires_approval": False,
                        "metadata": {"insufficient_content": True}
                    }
                text_content = message
            
            # Determine summary length
            summary_length = "medium"  # Default
            if "brief" in message.lower() or "short" in message.lower():
                summary_length = "brief"
            elif "detailed" in message.lower() or "comprehensive" in message.lower():
                summary_length = "detailed"
            
            # Create summary
            summary = await self._create_targeted_summary(text_content, summary_length, mode)
            
            response = f"""📝 **Text Summary** ({summary_length})

{summary}

**Original length:** {len(text_content)} characters
**Summary length:** {len(summary)} characters
**Compression ratio:** {len(summary)/len(text_content)*100:.1f}%"""
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "summarized": True,
                    "original_length": len(text_content),
                    "summary_length": len(summary),
                    "compression_ratio": len(summary)/len(text_content)*100
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling summarization: {e}")
            return await self.handle_error(str(e), {})
    
    async def _create_targeted_summary(self, content: str, length: str, mode: str) -> str:
        """Create summary with specific length target"""
        try:
            if length == "brief":
                instruction = "Create a brief, concise summary in 2-3 sentences capturing only the most essential points."
            elif length == "detailed":
                instruction = "Create a comprehensive summary that covers all major points, key details, and important context."
            else:
                instruction = "Create a balanced summary that captures the main points and key supporting details."
            
            prompt = f"""{instruction}

Text to summarize:
{content[:4000]}"""
            
            return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error creating targeted summary: {e}")
            return "Unable to create summary due to processing error."
    
    async def _handle_general_knowledge_request(self, messages: List[Dict[str, Any]], context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle general knowledge and writing requests"""
        try:
            # Add knowledge base context if available
            user_message = messages[-1]["content"]
            
            # Search for relevant knowledge
            knowledge_context = ""
            if self.knowledge_manager:
                related_info = await self.knowledge_manager.search_knowledge(
                    query=user_message,
                    limit=3
                )
                if related_info:
                    knowledge_context = "\n\nRelevant information from your knowledge base:\n"
                    knowledge_context += "\n".join([
                        f"• {info.get('title', 'Untitled')}: {info.get('content', '')[:150]}..."
                        for info in related_info
                    ])
            
            # Add knowledge context to system message if available
            enhanced_messages = messages.copy()
            if knowledge_context:
                if enhanced_messages and enhanced_messages[0]["role"] == "system":
                    enhanced_messages[0]["content"] += knowledge_context
                else:
                    enhanced_messages.insert(0, {"role": "system", "content": f"You are Sofia, a knowledge specialist.{knowledge_context}"})
            
            response = await self._generate_response(enhanced_messages, mode, context)
            
            # Store interaction in memory
            await self.store_memory(
                content=f"User query: {user_message}\nSofia response: {response[:200]}...",
                content_type="knowledge_interaction",
                tags=["general", "knowledge", "assistance"]
            )
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "knowledge_enhanced": bool(knowledge_context),
                    "message_type": "general_knowledge"
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling general knowledge request: {e}")
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