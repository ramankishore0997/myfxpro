# trading/apps.py
from django.apps import AppConfig

class ForexTradingConfig(AppConfig):
    name = 'forex_trading'

    def ready(self):
        import forex_trading.signals  # This will connect the signals
