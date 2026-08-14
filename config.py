import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "carwash.db")

# как часто крутится глобальный игровой тик (сек)
TICK_INTERVAL = 60

# --- Экономика старта ---
STARTING_BALANCE = 3000
RENT_PER_DAY = 40
UTILITIES_PER_DAY = 10
UTILITIES_PER_WASH = 2
BAY_PRICE = 6000
MAX_QUEUE_SIZE = 6

# --- Уровни мойщиков ---
WORKER_LEVELS = {
    "novice":      {"name": "Новичок",              "price": 200,   "speed": 1.0, "quality": 0.60, "salary": 30},
    "experienced": {"name": "Опытный",               "price": 800,   "speed": 1.3, "quality": 0.80, "salary": 60},
    "master":      {"name": "Мастер",                "price": 2500,  "speed": 1.6, "quality": 0.95, "salary": 100},
    "legend":      {"name": "Легенда детейлинга",    "price": 8000,  "speed": 2.0, "quality": 0.99, "salary": 200},
}
WORKER_ORDER = ["novice", "experienced", "master", "legend"]

# --- Оборудование ---
EQUIPMENT = {
    "vacuum":  {"name": "Пылесос",                    "price": 500,   "unlocks": "full"},
    "polisher":{"name": "Полировальная машина",        "price": 2000,  "unlocks": "polish"},
    "steamer": {"name": "Парогенератор",               "price": 3500,  "unlocks": "chemcleaning"},
    "ceramic": {"name": "Керамическое покрытие",       "price": 10000, "unlocks": "vip"},
}
EQUIPMENT_ORDER = ["vacuum", "polisher", "steamer", "ceramic"]

# --- Услуги ---
# duration в секундах (реальное время), min_level - минимальный уровень мойщика, требуемый для услуги
SERVICES = {
    "express":      {"name": "Экспресс-мойка кузова",  "duration": 10 * 60,  "min_pay": 80,   "max_pay": 150,  "equipment": None,      "min_level": None},
    "full":         {"name": "Полная мойка + салон",   "duration": 30 * 60,  "min_pay": 250,  "max_pay": 450,  "equipment": "vacuum",  "min_level": None},
    "polish":       {"name": "Полировка",               "duration": 60 * 60,  "min_pay": 600,  "max_pay": 1200, "equipment": "polisher","min_level": None},
    "chemcleaning": {"name": "Химчистка салона",        "duration": 90 * 60,  "min_pay": 900,  "max_pay": 1800, "equipment": "steamer", "min_level": None},
    "vip":          {"name": "VIP-детейлинг (керамика)","duration": 180 * 60, "min_pay": 3000, "max_pay": 7000, "equipment": "ceramic", "min_level": "master"},
}
SERVICE_ORDER = ["express", "full", "polish", "chemcleaning", "vip"]

# --- События ---
DAILY_BREAKDOWN_CHANCE = 0.15       # шанс поломки бокса раз в день
DAILY_SANITARY_CHANCE = 0.10        # шанс проверки санстанции раз в день
DAILY_VIP_EVENT_CHANCE = 0.20       # шанс визита VIP-клиента раз в день

BREAKDOWN_REPAIR_COST = 400
BREAKDOWN_DOWNTIME_MIN = 60 * 60      # 1 час
BREAKDOWN_DOWNTIME_MAX = 3 * 60 * 60  # 3 часа

SANITARY_FINE_MIN = 200
SANITARY_FINE_MAX = 800

VIP_BONUS_MULTIPLIER = 1.8  # доход VIP-события относительно обычного vip-заказа

# --- Клиенты в очередь ---
def client_arrival_chance(reputation: float) -> float:
    """Шанс появления нового клиента в очереди за один тик."""
    base = 0.35
    bonus = min(reputation / 300, 0.35)
    return min(base + bonus, 0.7)
