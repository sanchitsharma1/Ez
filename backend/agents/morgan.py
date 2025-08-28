import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

from agents.base_agent import BaseAgent
from integrations.financial.market_data import MarketDataClient
from core.config import settings

logger = logging.getLogger(__name__)

class MorganAgent(BaseAgent):
    """Morgan - Financial Analysis and Market Intelligence Specialist"""
    
    def __init__(self):
        super().__init__(
            agent_id="morgan",
            name="Morgan",
            persona="""You are Morgan, a highly analytical and data-driven financial advisor. 
            You specialize in market analysis, investment research, and financial intelligence. 
            You provide objective, evidence-based insights about stocks, markets, and economic trends. 
            You're precise with numbers, thorough in analysis, and always emphasize risk factors. 
            You help users make informed financial decisions through clear, actionable intelligence."""
        )
        
        self.capabilities = [
            "stock_analysis",
            "market_research",
            "financial_reporting",
            "portfolio_analysis",
            "economic_intelligence",
            "investment_insights"
        ]
        
        self.voice_id = "VR6AewLTigWG4xSOukaG"  # Male voice for Morgan
        
        # Financial data services
        self.market_data_client: Optional[MarketDataClient] = None
        
        # Cache for market data
        self._market_cache = {}
        self._cache_expiry = {}
    
    async def _initialize_agent(self):
        """Initialize Morgan-specific services"""
        try:
            self.market_data_client = MarketDataClient()
            await self.market_data_client.initialize()
            
            logger.info("Morgan agent initialized with financial market data services")
            
        except Exception as e:
            logger.error(f"Failed to initialize Morgan's services: {e}")
            raise
    
    def _get_agent_instructions(self) -> str:
        """Get Morgan-specific instructions"""
        return """
        As Morgan, you should:
        
        1. STOCK ANALYSIS:
           - Provide current stock prices and performance metrics
           - Analyze price trends and technical indicators
           - Compare stocks within sectors and against benchmarks
           - Identify key support and resistance levels
        
        2. MARKET RESEARCH:
           - Monitor market indices and sector performance
           - Track economic indicators and their market impact
           - Analyze market sentiment and volatility
           - Provide context for market movements
        
        3. FINANCIAL REPORTING:
           - Generate comprehensive investment reports
           - Create portfolio performance summaries
           - Analyze company fundamentals and financials
           - Provide risk-adjusted return calculations
        
        4. INVESTMENT INSIGHTS:
           - Identify potential investment opportunities
           - Assess risk factors and market risks
           - Provide sector rotation recommendations
           - Analyze dividend yields and growth prospects
        
        5. ECONOMIC INTELLIGENCE:
           - Monitor macroeconomic trends
           - Analyze Federal Reserve policies and interest rates
           - Track inflation, employment, and GDP data
           - Assess geopolitical impact on markets
        
        IMPORTANT DISCLAIMERS:
        - Always include appropriate investment disclaimers
        - Emphasize that past performance doesn't guarantee future results
        - Recommend consulting with qualified financial advisors
        - Never provide specific investment advice without proper context
        """
    
    async def process_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process message as Morgan"""
        try:
            messages = context.get("messages", [])
            intent = context.get("intent", "financial_analysis")
            user_context = context.get("context", {})
            mode = context.get("mode", "online")
            
            if not messages:
                return await self._generate_market_overview()
            
            user_message = messages[-1]["content"]
            
            # Route to specific handler based on intent
            if intent == "stock_analysis" or intent == "market_data":
                return await self._handle_stock_analysis(user_message, user_context, mode)
            elif intent == "portfolio_analysis":
                return await self._handle_portfolio_analysis(user_message, user_context, mode)
            elif intent == "market_research":
                return await self._handle_market_research(user_message, user_context, mode)
            elif intent == "economic_analysis":
                return await self._handle_economic_analysis(user_message, user_context, mode)
            else:
                return await self._handle_general_financial_request(messages, user_context, mode)
                
        except Exception as e:
            logger.error(f"Error processing message in Morgan: {e}")
            return await self.handle_error(str(e), context)
    
    async def _generate_market_overview(self) -> Dict[str, Any]:
        """Generate current market overview"""
        try:
            # Get major market indices
            market_data = await self._get_market_indices()
            
            overview = f"""📈 **Market Overview** - {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Major Indices:**
{market_data.get('indices_summary', 'Market data unavailable')}

**Market Sentiment:** {market_data.get('sentiment', 'Neutral')}
**VIX (Fear Index):** {market_data.get('vix', 'N/A')}

**Today's Highlights:**
{market_data.get('highlights', '• Market data loading...')}

**Economic Calendar:**
{market_data.get('upcoming_events', '• No major events scheduled')}

How can I assist you with financial analysis today? I can help with:
• Stock research and analysis
• Portfolio performance review  
• Market trend analysis
• Economic intelligence
• Investment opportunity screening

*Disclaimer: This information is for educational purposes only and should not be considered as investment advice.*"""
            
            return {
                "response": overview,
                "requires_approval": False,
                "metadata": {
                    "market_data": market_data,
                    "message_type": "market_overview"
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating market overview: {e}")
            return {
                "response": "Market data is currently unavailable. Please try again later or ask me about specific stocks or financial topics.",
                "requires_approval": False,
                "metadata": {"error": "market_data_unavailable"}
            }
    
    async def _handle_stock_analysis(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle stock analysis requests"""
        try:
            # Extract stock symbols from message
            stock_symbols = await self._extract_stock_symbols(message)
            
            if not stock_symbols:
                return {
                    "response": """I'd be happy to analyze stocks for you! Please specify the stock ticker symbol(s) you're interested in.

**Examples:**
• "Analyze AAPL" (Apple Inc.)
• "Compare MSFT vs GOOGL" 
• "What's Tesla's stock performance?" (TSLA)
• "Show me the top tech stocks"

**I can provide:**
📊 Current price and performance metrics
📈 Technical analysis and trends  
💰 Valuation metrics and fundamentals
📋 Analyst recommendations and price targets
⚠️ Risk factors and volatility analysis

Which stocks would you like me to analyze?""",
                    "requires_approval": False,
                    "metadata": {"needs_stock_symbol": True}
                }
            
            # Analyze requested stocks
            if len(stock_symbols) == 1:
                return await self._analyze_single_stock(stock_symbols[0], message, mode)
            else:
                return await self._compare_stocks(stock_symbols, message, mode)
                
        except Exception as e:
            logger.error(f"Error handling stock analysis: {e}")
            return await self.handle_error(str(e), {})
    
    async def _analyze_single_stock(self, symbol: str, user_message: str, mode: str) -> Dict[str, Any]:
        """Analyze a single stock in detail"""
        try:
            # Get stock data
            stock_data = await self._get_stock_data(symbol)
            
            if not stock_data:
                return {
                    "response": f"I couldn't retrieve data for stock symbol '{symbol}'. Please check the ticker symbol and try again.",
                    "requires_approval": False,
                    "metadata": {"invalid_symbol": symbol}
                }
            
            # Generate comprehensive analysis
            analysis = await self._generate_stock_analysis(stock_data, user_message, mode)
            
            # Format response
            response = f"""📊 **Stock Analysis: {stock_data.get('name', symbol)} ({symbol.upper()})**

**Current Price:** ${stock_data.get('current_price', 'N/A'):.2f}
**Change:** {stock_data.get('change', 0):.2f} ({stock_data.get('change_percent', 0):.1f}%)
**Volume:** {self._format_number(stock_data.get('volume', 0))}

{analysis}

**Key Metrics:**
• Market Cap: ${self._format_number(stock_data.get('market_cap', 0))}
• P/E Ratio: {stock_data.get('pe_ratio', 'N/A')}
• 52-Week Range: ${stock_data.get('year_low', 0):.2f} - ${stock_data.get('year_high', 0):.2f}
• Beta: {stock_data.get('beta', 'N/A')}
• Dividend Yield: {stock_data.get('dividend_yield', 0):.2f}%

*Last updated: {stock_data.get('last_updated', 'Unknown')}*

**⚠️ Investment Disclaimer:** This analysis is for informational purposes only. Past performance does not guarantee future results. Please consult with a qualified financial advisor before making investment decisions."""
            
            # Store analysis in memory
            await self.store_memory(
                content=f"Analyzed {symbol}: Current price ${stock_data.get('current_price', 0):.2f}, analysis provided to user",
                content_type="stock_analysis",
                tags=["stock", symbol.lower(), "analysis"]
            )
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "stock_analyzed": symbol,
                    "current_price": stock_data.get('current_price'),
                    "analysis_provided": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}")
            return await self.handle_error(str(e), {})
    
    async def _get_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive stock data"""
        try:
            # Check cache first
            cache_key = f"stock_{symbol.upper()}"
            if cache_key in self._market_cache:
                cache_time = self._cache_expiry.get(cache_key, 0)
                if datetime.now().timestamp() < cache_time:
                    return self._market_cache[cache_key]
            
            # Fetch from yfinance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            history = ticker.history(period="1d")
            
            if history.empty:
                return None
            
            current_price = history['Close'].iloc[-1]
            previous_close = info.get('previousClose', current_price)
            
            stock_data = {
                'symbol': symbol.upper(),
                'name': info.get('longName', symbol.upper()),
                'current_price': float(current_price),
                'previous_close': float(previous_close),
                'change': float(current_price - previous_close),
                'change_percent': float((current_price - previous_close) / previous_close * 100),
                'volume': int(info.get('volume', 0)),
                'market_cap': int(info.get('marketCap', 0)),
                'pe_ratio': info.get('trailingPE'),
                'year_high': float(info.get('fiftyTwoWeekHigh', 0)),
                'year_low': float(info.get('fiftyTwoWeekLow', 0)),
                'beta': info.get('beta'),
                'dividend_yield': float(info.get('dividendYield', 0) * 100) if info.get('dividendYield') else 0,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Cache the data for 5 minutes
            self._market_cache[cache_key] = stock_data
            self._cache_expiry[cache_key] = datetime.now().timestamp() + 300
            
            return stock_data
            
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {e}")
            return None
    
    async def _generate_stock_analysis(self, stock_data: Dict[str, Any], user_message: str, mode: str) -> str:
        """Generate detailed stock analysis"""
        try:
            symbol = stock_data['symbol']
            current_price = stock_data['current_price']
            change_percent = stock_data['change_percent']
            
            # Create analysis prompt
            prompt = f"""Provide a professional financial analysis for {stock_data['name']} ({symbol}) based on the following data:

Current Price: ${current_price:.2f}
Daily Change: {change_percent:.1f}%
Market Cap: ${self._format_number(stock_data['market_cap'])}
P/E Ratio: {stock_data.get('pe_ratio', 'N/A')}
52-Week Range: ${stock_data['year_low']:.2f} - ${stock_data['year_high']:.2f}
Beta: {stock_data.get('beta', 'N/A')}
Volume: {self._format_number(stock_data['volume'])}

Please provide:
1. **Technical Analysis**: Price trends, support/resistance levels
2. **Fundamental View**: Valuation assessment based on P/E and market cap
3. **Risk Assessment**: Volatility (beta) and market risk factors  
4. **Market Context**: How this stock fits in current market conditions

User's specific question: {user_message}

Keep analysis objective and professional. Include appropriate risk warnings."""
            
            return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error generating stock analysis: {e}")
            return "Unable to generate detailed analysis at this time."
    
    async def _extract_stock_symbols(self, message: str) -> List[str]:
        """Extract stock ticker symbols from message"""
        import re
        
        # Common patterns for stock symbols
        patterns = [
            r'\b([A-Z]{1,5})\b',  # 1-5 uppercase letters
            r'\$([A-Z]{1,5})\b',  # Dollar sign prefix
        ]
        
        symbols = []
        for pattern in patterns:
            matches = re.findall(pattern, message.upper())
            symbols.extend(matches)
        
        # Filter out common false positives
        false_positives = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAD', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WHO', 'BOY', 'DID', 'ITS', 'LET', 'PUT', 'SAY', 'SHE', 'TOO', 'USE'}
        
        symbols = [s for s in symbols if s not in false_positives and len(s) <= 5]
        
        # Remove duplicates while preserving order
        unique_symbols = []
        for symbol in symbols:
            if symbol not in unique_symbols:
                unique_symbols.append(symbol)
        
        return unique_symbols[:5]  # Limit to 5 symbols max
    
    async def _get_market_indices(self) -> Dict[str, Any]:
        """Get major market indices data"""
        try:
            indices = {
                '^GSPC': 'S&P 500',
                '^DJI': 'Dow Jones',
                '^IXIC': 'NASDAQ',
                '^VIX': 'VIX'
            }
            
            indices_data = []
            
            for symbol, name in indices.items():
                try:
                    ticker = yf.Ticker(symbol)
                    history = ticker.history(period="1d")
                    
                    if not history.empty:
                        current = history['Close'].iloc[-1]
                        previous = ticker.info.get('previousClose', current)
                        change_pct = (current - previous) / previous * 100
                        
                        indices_data.append(f"• **{name}**: {current:.2f} ({change_pct:+.1f}%)")
                
                except Exception as e:
                    logger.warning(f"Could not fetch data for {symbol}: {e}")
                    indices_data.append(f"• **{name}**: Data unavailable")
            
            return {
                'indices_summary': '\n'.join(indices_data),
                'sentiment': 'Mixed' if any('−' in item for item in indices_data) and any('+' in item for item in indices_data) else 'Positive' if any('+' in item for item in indices_data) else 'Negative',
                'vix': 'Loading...',
                'highlights': '• Market data updated\n• All major indices tracked',
                'upcoming_events': '• Check economic calendar for updates'
            }
            
        except Exception as e:
            logger.error(f"Error getting market indices: {e}")
            return {
                'indices_summary': 'Market data temporarily unavailable',
                'sentiment': 'Unknown',
                'vix': 'N/A',
                'highlights': '• Please try again later',
                'upcoming_events': '• Economic calendar unavailable'
            }
    
    def _format_number(self, num: int) -> str:
        """Format large numbers for display"""
        if num >= 1_000_000_000_000:
            return f"{num/1_000_000_000_000:.1f}T"
        elif num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        else:
            return str(num)
    
    async def _compare_stocks(self, symbols: List[str], user_message: str, mode: str) -> Dict[str, Any]:
        """Compare multiple stocks"""
        try:
            stocks_data = []
            
            for symbol in symbols:
                stock_data = await self._get_stock_data(symbol)
                if stock_data:
                    stocks_data.append(stock_data)
            
            if not stocks_data:
                return {
                    "response": "I couldn't retrieve data for any of the requested stocks. Please check the ticker symbols and try again.",
                    "requires_approval": False,
                    "metadata": {"comparison_failed": True}
                }
            
            # Generate comparison analysis
            comparison = await self._generate_stock_comparison(stocks_data, user_message, mode)
            
            # Format comparison table
            comparison_table = "| Stock | Price | Change | Volume | Market Cap | P/E |\n|-------|-------|--------|--------|------------|-----|\n"
            
            for stock in stocks_data:
                comparison_table += f"| {stock['symbol']} | ${stock['current_price']:.2f} | {stock['change_percent']:+.1f}% | {self._format_number(stock['volume'])} | ${self._format_number(stock['market_cap'])} | {stock.get('pe_ratio', 'N/A')} |\n"
            
            response = f"""📊 **Stock Comparison Analysis**

{comparison_table}

{comparison}

**⚠️ Investment Disclaimer:** This comparison is for informational purposes only. Consider all risk factors and consult with a qualified financial advisor before making investment decisions."""
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "stocks_compared": [s['symbol'] for s in stocks_data],
                    "comparison_provided": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error comparing stocks: {e}")
            return await self.handle_error(str(e), {})
    
    async def _generate_stock_comparison(self, stocks_data: List[Dict[str, Any]], user_message: str, mode: str) -> str:
        """Generate comparative stock analysis"""
        try:
            stocks_info = "\n".join([
                f"{stock['name']} ({stock['symbol']}): ${stock['current_price']:.2f} ({stock['change_percent']:+.1f}%), P/E: {stock.get('pe_ratio', 'N/A')}, Beta: {stock.get('beta', 'N/A')}"
                for stock in stocks_data
            ])
            
            prompt = f"""Provide a comparative analysis of these stocks:

{stocks_info}

Please analyze:
1. **Performance Comparison**: Which stocks are outperforming and why
2. **Valuation Analysis**: P/E ratios and relative valuations
3. **Risk Assessment**: Beta values and volatility comparison
4. **Investment Perspective**: Strengths and weaknesses of each
5. **Recommendation Context**: Considerations for different investor profiles

User's specific question: {user_message}

Provide objective analysis with balanced perspective on each stock."""
            
            return await self._generate_response([{"role": "user", "content": prompt}], mode)
            
        except Exception as e:
            logger.error(f"Error generating stock comparison: {e}")
            return "Unable to generate comparative analysis at this time."
    
    async def _handle_portfolio_analysis(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle portfolio analysis requests"""
        try:
            # Extract portfolio information from message
            portfolio_info = await self._extract_portfolio_info(message, mode)
            
            if not portfolio_info.get("holdings"):
                return {
                    "response": """I'd be happy to analyze your portfolio! Please provide your current holdings in this format:

**Example:**
"Analyze my portfolio: AAPL 100 shares, MSFT 50 shares, GOOGL 25 shares"

Or specify:
• Stock symbols and quantities/dollar amounts
• Investment timeline and goals  
• Risk tolerance level
• Any specific concerns or objectives

**Portfolio Analysis I can provide:**
📊 Diversification assessment
⚖️ Risk-return profile
📈 Performance attribution
🎯 Rebalancing recommendations
⚠️ Risk concentration alerts

What portfolio would you like me to analyze?""",
                    "requires_approval": False,
                    "metadata": {"needs_portfolio_details": True}
                }
            
            # Analyze portfolio
            return await self._analyze_portfolio(portfolio_info, message, mode)
            
        except Exception as e:
            logger.error(f"Error handling portfolio analysis: {e}")
            return await self.handle_error(str(e), {})
    
    async def _extract_portfolio_info(self, message: str, mode: str) -> Dict[str, Any]:
        """Extract portfolio information from message"""
        try:
            prompt = f"""Extract portfolio holdings from this message: "{message}"

Return JSON with:
- holdings: list of objects with symbol, shares/amount
- investment_goals: any mentioned goals
- time_horizon: investment timeline if mentioned
- risk_tolerance: if mentioned (conservative, moderate, aggressive)"""
            
            return await self._extract_structured_info(prompt, mode)
            
        except Exception as e:
            logger.error(f"Error extracting portfolio info: {e}")
            return {}
    
    async def _handle_market_research(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle market research requests"""
        try:
            # Determine research type
            if any(word in message.lower() for word in ["sector", "industry"]):
                return await self._analyze_sector(message, mode)
            elif any(word in message.lower() for word in ["market", "index", "overall"]):
                return await self._analyze_market_trends(message, mode)
            elif any(word in message.lower() for word in ["news", "events", "catalyst"]):
                return await self._analyze_market_news(message, mode)
            else:
                return await self._general_market_research(message, context, mode)
                
        except Exception as e:
            logger.error(f"Error handling market research: {e}")
            return await self.handle_error(str(e), {})
    
    async def _analyze_market_trends(self, message: str, mode: str) -> str:
        """Analyze current market trends"""
        try:
            # Get current market data
            market_data = await self._get_market_indices()
            
            prompt = f"""Analyze current market trends based on this data:

{market_data.get('indices_summary', 'Market data unavailable')}

Market Sentiment: {market_data.get('sentiment', 'Unknown')}

User's question: {message}

Provide analysis of:
1. **Current Market Direction**: Bull/bear market indicators
2. **Sector Rotation**: Which sectors are leading/lagging
3. **Key Market Drivers**: Economic factors influencing markets
4. **Technical Outlook**: Support/resistance levels for major indices
5. **Risk Factors**: Potential market threats and opportunities

Focus on actionable insights for investors."""
            
            analysis = await self._generate_response([{"role": "user", "content": prompt}], mode)
            
            return {
                "response": f"📊 **Market Trend Analysis**\n\n{analysis}\n\n*Analysis based on current market data as of {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
                "requires_approval": False,
                "metadata": {"market_analysis": True}
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market trends: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_economic_analysis(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle economic analysis requests"""
        response = await self._generate_response(
            [{"role": "user", "content": message}], mode, context
        )
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _handle_general_financial_request(self, messages: List[Dict[str, Any]], context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle general financial requests"""
        try:
            # Add financial context and disclaimers
            user_message = messages[-1]["content"]
            
            # Check if we should add market context
            market_context = ""
            if any(word in user_message.lower() for word in ["market", "stock", "investment", "economy"]):
                market_data = await self._get_market_indices()
                market_context = f"\n\nCurrent market context:\n{market_data.get('indices_summary', '')}"
            
            # Enhance system message with financial expertise context
            enhanced_messages = messages.copy()
            system_message = f"""You are Morgan, a financial analysis specialist. Provide accurate, objective financial information with appropriate disclaimers.{market_context}"""
            
            if enhanced_messages and enhanced_messages[0]["role"] == "system":
                enhanced_messages[0]["content"] += system_message
            else:
                enhanced_messages.insert(0, {"role": "system", "content": system_message})
            
            response = await self._generate_response(enhanced_messages, mode, context)
            
            # Add disclaimer if discussing investments
            if any(word in user_message.lower() for word in ["invest", "buy", "sell", "recommendation", "advice"]):
                response += "\n\n**⚠️ Investment Disclaimer:** This information is for educational purposes only and should not be considered as personalized investment advice. Please consult with a qualified financial advisor before making investment decisions."
            
            # Store interaction in memory
            await self.store_memory(
                content=f"Financial query: {user_message}\nMorgan response: {response[:200]}...",
                content_type="financial_consultation",
                tags=["financial", "analysis", "consultation"]
            )
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "financial_advice": True,
                    "disclaimer_included": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling general financial request: {e}")
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
    
    # Placeholder methods for additional functionality
    async def _analyze_portfolio(self, portfolio_info: Dict[str, Any], message: str, mode: str) -> Dict[str, Any]:
        """Analyze portfolio holdings"""
        response = f"Portfolio analysis functionality coming soon. Holdings detected: {portfolio_info.get('holdings', [])}"
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _analyze_sector(self, message: str, mode: str) -> Dict[str, Any]:
        """Analyze sector performance"""
        response = await self._generate_response([{"role": "user", "content": message}], mode)
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _analyze_market_news(self, message: str, mode: str) -> Dict[str, Any]:
        """Analyze market news and events"""
        response = await self._generate_response([{"role": "user", "content": message}], mode)
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _general_market_research(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """General market research"""
        response = await self._generate_response([{"role": "user", "content": message}], mode, context)
        return {"response": response, "requires_approval": False, "metadata": {}}