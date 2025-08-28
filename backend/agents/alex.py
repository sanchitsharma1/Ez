import asyncio
import logging
import psutil
import platform
import subprocess
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from agents.base_agent import BaseAgent
from utils.system_monitor import SystemMonitor
from core.config import settings

logger = logging.getLogger(__name__)

class AlexAgent(BaseAgent):
    """Alex - System Monitoring and Operations Specialist"""
    
    def __init__(self):
        super().__init__(
            agent_id="alex",
            name="Alex",
            persona="""You are Alex, a highly technical and security-conscious system administrator. 
            You monitor system health, analyze performance metrics, and execute approved system operations. 
            You prioritize security and stability, always assessing risks before taking action. You're methodical, 
            precise, and provide detailed technical analysis. You refuse dangerous operations and always 
            seek approval for sensitive commands."""
        )
        
        self.capabilities = [
            "system_monitoring",
            "performance_analysis", 
            "command_execution",
            "security_analysis",
            "root_cause_analysis",
            "system_diagnostics"
        ]
        
        self.voice_id = "ErXwobaYiN019PkySvjV"  # Male voice for Alex
        
        # System monitoring
        self.system_monitor: Optional[SystemMonitor] = None
        
        # Command safety lists
        self.allowed_commands = {
            "filesystem": ["mkdir", "ls", "dir", "tree", "find", "locate"],
            "system_info": ["systeminfo", "whoami", "hostname", "uptime", "uname"],
            "process": ["tasklist", "ps", "top", "htop"],
            "network": ["ping", "nslookup", "ipconfig", "ifconfig", "netstat"],
            "disk": ["df", "du", "diskutil", "fsutil"]
        }
        
        self.dangerous_commands = {
            "destructive": ["rm", "del", "rmdir", "rd", "format", "fdisk", "mkfs"],
            "system_modify": ["regedit", "reg", "systemctl", "service", "chkdsk"],
            "network_modify": ["iptables", "netsh", "route"],
            "user_modify": ["useradd", "userdel", "passwd", "net user"]
        }
    
    async def _initialize_agent(self):
        """Initialize Alex-specific services"""
        try:
            self.system_monitor = SystemMonitor()
            await self.system_monitor.initialize()
            
            logger.info("Alex agent initialized with system monitoring")
            
        except Exception as e:
            logger.error(f"Failed to initialize Alex's services: {e}")
            raise
    
    def _get_agent_instructions(self) -> str:
        """Get Alex-specific instructions"""
        return """
        As Alex, you should:
        
        1. SYSTEM MONITORING:
           - Monitor CPU, memory, disk, and network usage
           - Track running processes and services
           - Identify performance bottlenecks
           - Alert on anomalies and threshold breaches
        
        2. SECURITY ANALYSIS:
           - Analyze system logs for security events
           - Identify unauthorized access attempts
           - Monitor for malware indicators
           - Assess system vulnerabilities
        
        3. COMMAND EXECUTION:
           - Only execute approved, safe commands
           - Always request approval for sensitive operations
           - Refuse dangerous commands (file deletion, system modification)
           - Provide detailed explanations of command purposes
        
        4. ROOT CAUSE ANALYSIS:
           - Investigate system issues and errors
           - Correlate metrics and logs
           - Provide actionable recommendations
           - Document findings and solutions
        
        5. SYSTEM OPERATIONS:
           - Create directory structures when requested
           - Gather system information and diagnostics
           - Monitor service health and availability
           - Generate system reports
        
        SAFETY RULES:
        - Never execute commands that could harm the system
        - Always explain the risks and benefits of operations
        - Request user approval for all command executions
        - Maintain detailed logs of all activities
        """
    
    async def process_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process message as Alex"""
        try:
            messages = context.get("messages", [])
            intent = context.get("intent", "system_monitoring")
            user_context = context.get("context", {})
            mode = context.get("mode", "online")
            
            if not messages:
                return await self._generate_system_status()
            
            user_message = messages[-1]["content"]
            
            # Route to specific handler based on intent
            if intent == "system_monitoring":
                return await self._handle_monitoring_request(user_message, user_context, mode)
            elif intent == "system_command":
                return await self._handle_command_request(user_message, user_context, mode)
            elif intent == "performance_analysis":
                return await self._handle_performance_analysis(user_message, user_context, mode)
            elif intent == "security_analysis":
                return await self._handle_security_analysis(user_message, user_context, mode)
            else:
                return await self._handle_general_system_request(messages, user_context, mode)
                
        except Exception as e:
            logger.error(f"Error processing message in Alex: {e}")
            return await self.handle_error(str(e), context)
    
    async def _generate_system_status(self) -> Dict[str, Any]:
        """Generate current system status"""
        try:
            if not self.system_monitor:
                return {
                    "response": "System monitoring is not available. Please check system configuration.",
                    "requires_approval": False,
                    "metadata": {"error": "monitoring_unavailable"}
                }
            
            metrics = await self.system_monitor.get_current_metrics()
            
            status_report = f"""🖥️ **System Status Report**

**System Information:**
- Host: {metrics.get('hostname', 'Unknown')}
- OS: {metrics.get('os', 'Unknown')}
- Uptime: {self._format_uptime(metrics.get('uptime', 0))}

**Performance Metrics:**
- CPU Usage: {metrics.get('cpu_percent', 0):.1f}%
- Memory Usage: {metrics.get('memory_percent', 0):.1f}% ({self._format_bytes(metrics.get('memory_used', 0))} / {self._format_bytes(metrics.get('memory_total', 0))})
- Disk Usage: {metrics.get('disk_percent', 0):.1f}% ({self._format_bytes(metrics.get('disk_used', 0))} / {self._format_bytes(metrics.get('disk_total', 0))})

**Network Activity:**
- Bytes Sent: {self._format_bytes(metrics.get('network_sent', 0))}
- Bytes Received: {self._format_bytes(metrics.get('network_recv', 0))}

**Running Processes:** {metrics.get('process_count', 0)}

**System Health:** {"✅ Good" if self._assess_system_health(metrics) else "⚠️ Attention Needed"}

How can I assist you with system operations today?"""
            
            return {
                "response": status_report,
                "requires_approval": False,
                "metadata": {
                    "metrics": metrics,
                    "system_health": self._assess_system_health(metrics)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating system status: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_monitoring_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle system monitoring requests"""
        try:
            if any(keyword in message.lower() for keyword in ["status", "health", "performance"]):
                return await self._get_system_status(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["processes", "running", "tasks"]):
                return await self._get_running_processes(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["disk", "storage", "space"]):
                return await self._get_disk_usage(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["network", "connections", "bandwidth"]):
                return await self._get_network_info(message, context, mode)
            else:
                return await self._general_monitoring_response(message, context, mode)
                
        except Exception as e:
            logger.error(f"Error handling monitoring request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_command_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle system command execution requests"""
        try:
            # Extract command from message
            command_info = await self._extract_command_info(message, mode)
            
            if not command_info.get("command"):
                return {
                    "response": "I couldn't identify a specific command to execute. Please specify the exact command you'd like me to run.",
                    "requires_approval": False,
                    "metadata": {"needs_clarification": True}
                }
            
            command = command_info["command"]
            command_type = self._classify_command(command)
            
            # Check if command is dangerous
            if self._is_dangerous_command(command):
                return {
                    "response": f"⛔ **Command Rejected for Security**\n\nI cannot execute the command '{command}' as it poses security risks:\n\n{self._explain_command_risks(command)}\n\nPlease use safer alternatives or contact your system administrator.",
                    "requires_approval": False,
                    "metadata": {
                        "command_rejected": True,
                        "risk_level": "high",
                        "command": command
                    }
                }
            
            # Check if command is allowed
            if not self._is_allowed_command(command):
                return {
                    "response": f"🚫 **Command Not Permitted**\n\nThe command '{command}' is not in my allowed command list. I can only execute pre-approved safe commands.\n\nAllowed command categories:\n" + 
                               "\n".join([f"- **{cat}**: {', '.join(cmds)}" for cat, cmds in self.allowed_commands.items()]),
                    "requires_approval": False,
                    "metadata": {
                        "command_not_allowed": True,
                        "command": command
                    }
                }
            
            # Command is safe and allowed - request approval
            risk_assessment = self._assess_command_risk(command)
            
            approval_request = {
                "action_type": "execute_command",
                "description": f"Execute system command: {command}",
                "payload": {
                    "command": command,
                    "command_type": command_type,
                    "risk_assessment": risk_assessment,
                    "explanation": command_info.get("explanation", "")
                },
                "risk_level": risk_assessment.get("level", "medium")
            }
            
            response_text = f"""🔧 **Command Execution Request**

**Command:** `{command}`
**Type:** {command_type}
**Purpose:** {command_info.get('explanation', 'Command execution as requested')}

**Risk Assessment:**
- Level: {risk_assessment.get('level', 'medium').upper()}
- Impact: {risk_assessment.get('impact', 'Limited system impact')}
- Reversible: {'Yes' if risk_assessment.get('reversible', True) else 'No'}

**Expected Outcome:**
{risk_assessment.get('expected_outcome', 'Command will be executed and results displayed')}

Do you approve this command execution?"""
            
            return {
                "response": response_text,
                "requires_approval": True,
                "approval_request": approval_request,
                "metadata": {
                    "command_info": command_info,
                    "risk_assessment": risk_assessment
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling command request: {e}")
            return await self.handle_error(str(e), {})
    
    async def execute_approved_command(self, command: str, command_type: str) -> Dict[str, Any]:
        """Execute an approved command"""
        try:
            start_time = datetime.utcnow()
            
            # Execute command based on OS
            if platform.system() == "Windows":
                result = await self._execute_windows_command(command)
            else:
                result = await self._execute_unix_command(command)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Format result
            if result["success"]:
                response = f"""✅ **Command Executed Successfully**

**Command:** `{command}`
**Execution Time:** {execution_time:.2f} seconds

**Output:**
```
{result['output'][:2000]}{'...' if len(result['output']) > 2000 else ''}
```"""
            else:
                response = f"""❌ **Command Execution Failed**

**Command:** `{command}`
**Error:** {result['error']}

**Output:**
```
{result['output'][:1000]}{'...' if len(result['output']) > 1000 else ''}
```"""
            
            # Store command history
            await self.store_memory(
                content=f"Executed command: {command}\nResult: {'Success' if result['success'] else 'Failed'}\nOutput: {result['output'][:500]}",
                content_type="command_execution",
                tags=["command", command_type, "system_operation"]
            )
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "command": command,
                    "success": result["success"],
                    "execution_time": execution_time,
                    "output_length": len(result["output"])
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            return {
                "response": f"❌ **Command Execution Error**\n\nFailed to execute command '{command}': {str(e)}",
                "requires_approval": False,
                "metadata": {"execution_error": str(e)}
            }
    
    async def _execute_windows_command(self, command: str) -> Dict[str, Any]:
        """Execute command on Windows"""
        try:
            # Use PowerShell for better output handling
            if not command.startswith("powershell"):
                command = f"powershell -Command \"{command}\""
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=30
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "success": process.returncode == 0,
                "output": stdout.decode('utf-8', errors='ignore') if stdout else "",
                "error": stderr.decode('utf-8', errors='ignore') if stderr else "",
                "return_code": process.returncode
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "output": "",
                "error": "Command timed out after 30 seconds",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "return_code": -1
            }
    
    async def _execute_unix_command(self, command: str) -> Dict[str, Any]:
        """Execute command on Unix/Linux"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=30
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "success": process.returncode == 0,
                "output": stdout.decode('utf-8', errors='ignore') if stdout else "",
                "error": stderr.decode('utf-8', errors='ignore') if stderr else "",
                "return_code": process.returncode
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "output": "",
                "error": "Command timed out after 30 seconds",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "return_code": -1
            }
    
    def _classify_command(self, command: str) -> str:
        """Classify command type"""
        command_lower = command.lower()
        
        for category, commands in self.allowed_commands.items():
            if any(cmd in command_lower for cmd in commands):
                return category
        
        return "unknown"
    
    def _is_dangerous_command(self, command: str) -> bool:
        """Check if command is dangerous"""
        command_lower = command.lower()
        
        for category, commands in self.dangerous_commands.items():
            if any(cmd in command_lower for cmd in commands):
                return True
        
        return False
    
    def _is_allowed_command(self, command: str) -> bool:
        """Check if command is allowed"""
        command_lower = command.lower()
        
        for category, commands in self.allowed_commands.items():
            if any(command_lower.startswith(cmd) for cmd in commands):
                return True
        
        return False
    
    def _assess_command_risk(self, command: str) -> Dict[str, Any]:
        """Assess risk level of command"""
        command_lower = command.lower()
        
        # Low risk commands
        if any(cmd in command_lower for cmd in ["ls", "dir", "whoami", "hostname", "uptime"]):
            return {
                "level": "low",
                "impact": "No system modification, read-only operation",
                "reversible": True,
                "expected_outcome": "Display information without making changes"
            }
        
        # Medium risk commands
        elif any(cmd in command_lower for cmd in ["mkdir", "ping", "find", "tasklist"]):
            return {
                "level": "medium", 
                "impact": "Limited system modification or network activity",
                "reversible": True,
                "expected_outcome": "Create directories or gather system information"
            }
        
        # Default to medium risk
        return {
            "level": "medium",
            "impact": "Potential system impact, requires review",
            "reversible": True,
            "expected_outcome": "Execute system command with monitoring"
        }
    
    def _explain_command_risks(self, command: str) -> str:
        """Explain why a command is risky"""
        command_lower = command.lower()
        
        if any(cmd in command_lower for cmd in self.dangerous_commands.get("destructive", [])):
            return "This command can permanently delete files or data"
        elif any(cmd in command_lower for cmd in self.dangerous_commands.get("system_modify", [])):
            return "This command can modify critical system settings"
        elif any(cmd in command_lower for cmd in self.dangerous_commands.get("network_modify", [])):
            return "This command can change network configuration"
        elif any(cmd in command_lower for cmd in self.dangerous_commands.get("user_modify", [])):
            return "This command can modify user accounts or permissions"
        
        return "This command poses potential security or stability risks"
    
    async def _extract_command_info(self, message: str, mode: str) -> Dict[str, Any]:
        """Extract command information from user message"""
        try:
            extraction_prompt = f"""
            Extract command execution details from this message: "{message}"
            
            Return JSON with:
            - command: the exact command to execute
            - explanation: what the command does
            - parameters: any command parameters
            - purpose: why the user wants to run it
            """
            
            # Generate structured response
            command_info = await self._extract_structured_info(extraction_prompt, mode)
            return command_info
            
        except Exception as e:
            logger.error(f"Error extracting command info: {e}")
            return {}
    
    async def _get_system_status(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Get detailed system status"""
        try:
            if not self.system_monitor:
                return await self.handle_error("System monitoring unavailable", {})
            
            metrics = await self.system_monitor.get_current_metrics()
            historical_data = await self.system_monitor.get_historical_metrics(hours=1)
            
            # Analyze trends
            trend_analysis = self._analyze_performance_trends(historical_data)
            
            status_report = f"""📊 **Detailed System Status**

**Current Metrics:**
- CPU: {metrics.get('cpu_percent', 0):.1f}% (Cores: {metrics.get('cpu_count', 'Unknown')})
- Memory: {metrics.get('memory_percent', 0):.1f}% ({self._format_bytes(metrics.get('memory_used', 0))} used)
- Disk: {metrics.get('disk_percent', 0):.1f}% ({self._format_bytes(metrics.get('disk_free', 0))} free)
- Network: ↑ {self._format_bytes(metrics.get('network_sent_rate', 0))}/s ↓ {self._format_bytes(metrics.get('network_recv_rate', 0))}/s

**Performance Trends (Last Hour):**
{trend_analysis}

**System Alerts:**
{self._generate_system_alerts(metrics)}

**Recommendations:**
{self._generate_recommendations(metrics)}"""
            
            return {
                "response": status_report,
                "requires_approval": False,
                "metadata": {
                    "metrics": metrics,
                    "trends": trend_analysis,
                    "health_score": self._calculate_health_score(metrics)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return await self.handle_error(str(e), {})
    
    async def _get_running_processes(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Get information about running processes"""
        try:
            processes = await self._get_process_list()
            
            # Sort by CPU or memory usage
            if "memory" in message.lower():
                processes.sort(key=lambda x: x.get('memory_percent', 0), reverse=True)
                sort_key = "memory usage"
            else:
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
                sort_key = "CPU usage"
            
            # Get top 10 processes
            top_processes = processes[:10]
            
            process_report = f"""🔄 **Running Processes** (Top 10 by {sort_key})

"""
            
            for i, proc in enumerate(top_processes, 1):
                process_report += f"""{i}. **{proc.get('name', 'Unknown')}** (PID: {proc.get('pid', 'N/A')})
   - CPU: {proc.get('cpu_percent', 0):.1f}%
   - Memory: {proc.get('memory_percent', 0):.1f}% ({self._format_bytes(proc.get('memory_info', 0))})
   - Status: {proc.get('status', 'Unknown')}

"""
            
            process_report += f"**Total Processes:** {len(processes)}"
            
            return {
                "response": process_report,
                "requires_approval": False,
                "metadata": {
                    "total_processes": len(processes),
                    "top_processes": top_processes
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting running processes: {e}")
            return await self.handle_error(str(e), {})
    
    async def _get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of running processes"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status']):
                try:
                    proc_info = proc.info
                    proc_info['memory_info'] = proc_info['memory_info'].rss if proc_info['memory_info'] else 0
                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return processes
            
        except Exception as e:
            logger.error(f"Error getting process list: {e}")
            return []
    
    def _analyze_performance_trends(self, historical_data: List[Dict[str, Any]]) -> str:
        """Analyze performance trends from historical data"""
        if not historical_data or len(historical_data) < 2:
            return "Insufficient data for trend analysis"
        
        try:
            # Calculate trends
            cpu_trend = self._calculate_trend([d.get('cpu_percent', 0) for d in historical_data])
            memory_trend = self._calculate_trend([d.get('memory_percent', 0) for d in historical_data])
            
            trends = []
            if cpu_trend > 5:
                trends.append("🔺 CPU usage trending UP")
            elif cpu_trend < -5:
                trends.append("🔻 CPU usage trending DOWN")
            else:
                trends.append("➡️ CPU usage stable")
            
            if memory_trend > 2:
                trends.append("🔺 Memory usage trending UP") 
            elif memory_trend < -2:
                trends.append("🔻 Memory usage trending DOWN")
            else:
                trends.append("➡️ Memory usage stable")
            
            return "\n".join(trends)
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return "Trend analysis unavailable"
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate simple trend (difference between first and last values)"""
        if len(values) < 2:
            return 0.0
        return values[-1] - values[0]
    
    def _generate_system_alerts(self, metrics: Dict[str, Any]) -> str:
        """Generate system alerts based on metrics"""
        alerts = []
        
        cpu_percent = metrics.get('cpu_percent', 0)
        memory_percent = metrics.get('memory_percent', 0)
        disk_percent = metrics.get('disk_percent', 0)
        
        if cpu_percent > 90:
            alerts.append("🚨 Critical: CPU usage above 90%")
        elif cpu_percent > 75:
            alerts.append("⚠️ Warning: CPU usage above 75%")
        
        if memory_percent > 90:
            alerts.append("🚨 Critical: Memory usage above 90%")
        elif memory_percent > 80:
            alerts.append("⚠️ Warning: Memory usage above 80%")
        
        if disk_percent > 95:
            alerts.append("🚨 Critical: Disk space below 5%")
        elif disk_percent > 90:
            alerts.append("⚠️ Warning: Disk space below 10%")
        
        return "\n".join(alerts) if alerts else "✅ No critical alerts"
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> str:
        """Generate system recommendations"""
        recommendations = []
        
        cpu_percent = metrics.get('cpu_percent', 0)
        memory_percent = metrics.get('memory_percent', 0)
        disk_percent = metrics.get('disk_percent', 0)
        
        if cpu_percent > 75:
            recommendations.append("Consider closing unnecessary applications")
        
        if memory_percent > 80:
            recommendations.append("Restart memory-intensive applications")
            recommendations.append("Consider adding more RAM")
        
        if disk_percent > 90:
            recommendations.append("Clean up temporary files and downloads")
            recommendations.append("Consider disk cleanup or expansion")
        
        if not recommendations:
            recommendations.append("System performance is optimal")
        
        return "\n".join(f"• {rec}" for rec in recommendations)
    
    def _assess_system_health(self, metrics: Dict[str, Any]) -> bool:
        """Assess overall system health"""
        cpu_ok = metrics.get('cpu_percent', 0) < 80
        memory_ok = metrics.get('memory_percent', 0) < 85
        disk_ok = metrics.get('disk_percent', 0) < 90
        
        return cpu_ok and memory_ok and disk_ok
    
    def _calculate_health_score(self, metrics: Dict[str, Any]) -> int:
        """Calculate system health score (0-100)"""
        try:
            cpu_score = max(0, 100 - metrics.get('cpu_percent', 0))
            memory_score = max(0, 100 - metrics.get('memory_percent', 0))
            disk_score = max(0, 100 - metrics.get('disk_percent', 0))
            
            # Weighted average
            health_score = int((cpu_score * 0.4 + memory_score * 0.4 + disk_score * 0.2))
            return max(0, min(100, health_score))
            
        except Exception:
            return 50  # Default to neutral score
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds to readable string"""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
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
    
    # Additional helper methods for other request types...
    async def _handle_performance_analysis(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle performance analysis requests"""
        response = await self._generate_response(
            [{"role": "user", "content": message}], mode, context
        )
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _handle_security_analysis(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle security analysis requests"""
        response = await self._generate_response(
            [{"role": "user", "content": message}], mode, context
        )
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _handle_general_system_request(self, messages: List[Dict[str, Any]], context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle general system requests"""
        response = await self._generate_response(messages, mode, context)
        return {"response": response, "requires_approval": False, "metadata": {}}