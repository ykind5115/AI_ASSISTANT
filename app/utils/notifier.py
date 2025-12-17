"""
本地通知模块
实现跨平台的桌面通知功能
"""
import platform
from typing import Optional
from app.config import settings


class Notifier:
    """通知管理器"""
    
    @staticmethod
    def send_notification(title: str, message: str, duration: int = 5) -> bool:
        """
        发送桌面通知
        
        Args:
            title: 通知标题
            message: 通知内容
            duration: 显示时长（秒）
            
        Returns:
            是否发送成功
        """
        if not settings.ENABLE_DESKTOP_NOTIFICATION:
            return False
        
        try:
            system = platform.system()
            
            if system == "Windows":
                return Notifier._notify_windows(title, message, duration)
            elif system == "Darwin":  # macOS
                return Notifier._notify_macos(title, message, duration)
            elif system == "Linux":
                return Notifier._notify_linux(title, message, duration)
            else:
                print(f"通知：{title} - {message}")
                return False
        except Exception as e:
            print(f"发送通知失败: {e}")
            return False
    
    @staticmethod
    def _notify_windows(title: str, message: str, duration: int) -> bool:
        """Windows通知"""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title,
                message,
                duration=duration,
                threaded=True
            )
            return True
        except ImportError:
            # 如果没有win10toast，使用系统命令
            try:
                import subprocess
                # 使用PowerShell发送通知
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $textNodes = $template.GetElementsByTagName("text")
                $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
                $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("CareMate").Show($toast)
                '''
                subprocess.run(["powershell", "-Command", ps_script], check=False)
                return True
            except Exception:
                print(f"通知：{title} - {message}")
                return False
    
    @staticmethod
    def _notify_macos(title: str, message: str, duration: int) -> bool:
        """macOS通知"""
        try:
            import subprocess
            script = f'''
            display notification "{message}" with title "{title}"
            '''
            subprocess.run(["osascript", "-e", script], check=False)
            return True
        except Exception:
            print(f"通知：{title} - {message}")
            return False
    
    @staticmethod
    def _notify_linux(title: str, message: str, duration: int) -> bool:
        """Linux通知（使用notify-send）"""
        try:
            import subprocess
            subprocess.run(
                ["notify-send", title, message, f"--expire-time={duration * 1000}"],
                check=False
            )
            return True
        except Exception:
            print(f"通知：{title} - {message}")
            return False



