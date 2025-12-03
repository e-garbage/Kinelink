import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
#import telegram
from TMCL import MotorManager  # Assuming this is your motor manager module
motor_manager: MotorManager | None = None
class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, motor_manager: MotorManager):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.motor_manager = motor_manager
        self.bot = telegram.Bot(token=bot_token)
        self.is_running = False
        self.interval = 300  # Default 5 minutes in seconds
        self.task = None
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def set_interval(self, seconds: int):
        """Set the interval for notifications"""
        self.interval = seconds
        self.logger.info(f"Notification interval set to {seconds} seconds")
    
    def enable_notifications(self):
        """Enable telegram notifications"""
        if not self.is_running:
            self.is_running = True
            self.logger.info("Telegram notifications enabled")
            # Start the notification loop
            asyncio.create_task(self._notification_loop())
    
    def disable_notifications(self):
        """Disable telegram notifications"""
        self.is_running = False
        if self.task:
            self.task.cancel()
        self.logger.info("Telegram notifications disabled")
    
    async def _notification_loop(self):
        """Main loop for sending notifications"""
        while self.is_running:
            try:
                # Execute motor scan
                scan_result = self.motor_manager.scan()
                
                # Process and send notification
                await self._process_and_send_notification(scan_result)
                
                # Wait for next interval
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                self.logger.error(f"Error in notification loop: {e}")
                # Continue running even if one iteration fails
                await asyncio.sleep(self.interval)
    
    async def _process_and_send_notification(self, scan_result: Dict[str, Any]):
        """Process scan result and send telegram notification"""
        try:
            if not scan_result:
                message = "No devices found during scan"
            else:
                message = self._format_scan_result(scan_result)
            
            # Send notification
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info("Telegram notification sent successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to send telegram notification: {e}")
    
    def _format_scan_result(self, scan_result: Dict[str, Any]) -> str:
        """Format the scan result into a readable message"""
        if not scan_result:
            return "No devices found during scan"
        
        message = f"Scan Results ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):\n\n"
        
        for addr, data in scan_result.items():
            message += f"Device: {addr}\n"
            if 'temp' in data:
                message += f"  Temperature: {data['temp']}°C\n"
            if 'humidity' in data:
                message += f"  Humidity: {data['humidity']}%\n"
            if 'status' in data:
                message += f"  Status: {data['status']}\n"
            message += "\n"
        
        return message
    
    async def send_manual_notification(self, message: str):
        """Send a manual notification (useful for testing)"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            self.logger.info("Manual notification sent")
        except Exception as e:
            self.logger.error(f"Failed to send manual notification: {e}")

# Global instance
telegram_notifier = None

def initialize_telegram_notifier(bot_token: str, chat_id: str, motor_manager: MotorManager):
    """Initialize the telegram notifier instance"""
    global telegram_notifier
    telegram_notifier = TelegramNotifier(bot_token, chat_id, motor_manager)
    return telegram_notifier

def get_telegram_notifier():
    """Get the global telegram notifier instance"""
    return telegram_notifier
