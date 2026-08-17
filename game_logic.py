import time
import random
import json
import logging

import config
import db

logger = logging.getLogger("carwash.game")
_last_status_message: dict[int, int] = {}
_event_history: dict[int, list] = {}  # user_id -> [(timestamp, text), ...]

def relative_time(ts: float) -> str:
    diff = int(time.time() - ts)
    if diff < 60:
        return "только что"
    if diff < 3600:
        return f"{diff // 60} мин назад"
    return f"{diff // 3600} ч назад"

def roll_payout(service_type: str, quality: float, reputation: float, multiplier: float = 1.0) -> float:
    svc = config.SERVICES[service_type]
    base = random.uniform(svc["min_pay"], svc["max_pay"])
    payout = base * (0.7 + 0.3 * quality) * (1 + reputation / 200) * multiplier
    return round(payout, 1)


def worker_can_do(user_row, worker_row, service_type: str) -> bool:
    svc = config.SERVICES[service_type]
    if svc["equipment"]:
        col = f"has_{svc['equipment']}"
        if not user_row[col]:
            return False
    if svc["min_level"]:
        levels = config.WORKER_ORDER
        if levels.index(worker_row["level"]) < levels.index(svc["min_level"]):
            return False
    return True


def available_services(user_row):
    """Список услуг, доступных владельцу по купленному оборудованию."""
    result = []
    for s in config.SERVICE_ORDER:
        svc = config.SERVICES[s]
        if svc["equipment"] and not user_row[f"has_{svc['equipment']}"]:
            continue
        result.append(s)
    return result


async def generate_client(db_conn, user_row):
    """С некоторым шансом добавляет нового клиента в очередь."""
    owner_id = user_row["user_id"]
    cur = await db_conn.execute("SELECT COUNT(*) as c FROM queue WHERE owner_id=?", (owner_id,))
    row = await cur.fetchone()
    if row["c"] >= config.MAX_QUEUE_SIZE:
        return

    chance = config.client_arrival_chance(user_row["reputation"])
    if random.random() > chance:
        return

    services = available_services(user_row)
    if not services:
        services = ["express"]
    # чем выше репутация, тем выше шанс клиента захотеть дорогую услугу
    weights = []
    for s in services:
        idx = config.SERVICE_ORDER.index(s)
        weights.append(1 + idx * (user_row["reputation"] / 100))
    service_type = random.choices(services, weights=weights, k=1)[0]

    await db_conn.execute(
        "INSERT INTO queue (owner_id, service_type, is_vip, created_at) VALUES (?, ?, 0, ?)",
        (owner_id, service_type, time.time()),
    )


async def match_queue(db_conn, user_row):
    """Автоматически назначает свободные боксы+мойщиков на клиентов из очереди."""
    owner_id = user_row["user_id"]
    now = time.time()

    bays = await db.get_bays(db_conn, owner_id)
    free_bays = [b for b in bays if b["status"] == "free"]
    if not free_bays:
        return []

    workers = await db.get_workers(db_conn, owner_id)
    idle_workers = [w for w in workers if w["status"] == "idle"]
    if not idle_workers:
        return []
    # лучшие мойщики (выше качество) обслуживают клиентов первыми
    idle_workers.sort(key=lambda w: config.WORKER_LEVELS[w["level"]]["quality"], reverse=True)

    queue_items = await db.get_queue(db_conn, owner_id)

    created_orders = []
    for item in queue_items:
        if not free_bays or not idle_workers:
            break
        assigned_worker = None
        for w in idle_workers:
            if worker_can_do(user_row, w, item["service_type"]):
                assigned_worker = w
                break
        if not assigned_worker:
            continue  # никто не может выполнить эту услугу, ждём в очереди

        bay = free_bays.pop(0)
        idle_workers.remove(assigned_worker)

        svc = config.SERVICES[item["service_type"]]
        wl = config.WORKER_LEVELS[assigned_worker["level"]]
        duration = svc["duration"] / wl["speed"]
        multiplier = config.VIP_BONUS_MULTIPLIER if item["is_vip"] else 1.0
        payout = roll_payout(item["service_type"], wl["quality"], user_row["reputation"], multiplier)

        finish_at = now + duration
        await db_conn.execute(
            "INSERT INTO orders (owner_id, worker_id, bay_id, service_type, started_at, finish_at, payout, resolved) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (owner_id, assigned_worker["worker_id"], bay["bay_id"], item["service_type"], now, finish_at, payout),
        )
        await db_conn.execute("UPDATE bays SET status='busy' WHERE bay_id=?", (bay["bay_id"],))
        await db_conn.execute(
            "UPDATE workers SET status='working', busy_until=? WHERE worker_id=?", (finish_at, assigned_worker["worker_id"])
        )
        await db_conn.execute("DELETE FROM queue WHERE queue_id=?", (item["queue_id"],))
        created_orders.append((item["service_type"], svc["name"], payout, finish_at))

    return created_orders


async def resolve_orders(db_conn, user_row):
    """Закрывает завершённые заказы, начисляет деньги, чаевые/жалобы."""
    owner_id = user_row["user_id"]
    now = time.time()
    cur = await db_conn.execute(
        "SELECT * FROM orders WHERE owner_id=? AND resolved=0 AND finish_at<=?", (owner_id, now)
    )
    finished = await cur.fetchall()
    if not finished:
        return [], 0.0, 0

    total_income = 0.0
    reputation_delta = 0.0
    complaints = 0
    results = []

    for order in finished:
        worker = await (await db_conn.execute("SELECT * FROM workers WHERE worker_id=?", (order["worker_id"],))).fetchone()
        quality = config.WORKER_LEVELS[worker["level"]]["quality"] if worker else 0.6

        payout = order["payout"]
        tip = 0.0
        complaint = False

        if random.random() < quality * 0.3:
            tip = round(payout * random.uniform(0.1, 0.15), 1)
        elif random.random() < (1 - quality) * 0.2:
            complaint = True
            complaints += 1

        income = payout + tip
        total_income += income
        reputation_delta += (0.15 if not complaint else -1.0)

        await db_conn.execute(
            "UPDATE orders SET resolved=1 WHERE order_id=?", (order["order_id"],)
        )
        await db_conn.execute("UPDATE bays SET status='free' WHERE bay_id=?", (order["bay_id"],))
        await db_conn.execute("UPDATE workers SET status='idle', busy_until=0 WHERE worker_id=?", (order["worker_id"],))
        await db_conn.execute(
            "UPDATE users SET washes_today = washes_today + 1 WHERE user_id=?", (owner_id,)
        )

        results.append({
            "service": config.SERVICES[order["service_type"]]["name"],
            "income": income,
            "tip": tip,
            "complaint": complaint,
        })

    new_balance = user_row["balance"] + total_income
    new_rep = max(0.0, user_row["reputation"] + reputation_delta)
    await db_conn.execute(
        "UPDATE users SET balance=?, reputation=? WHERE user_id=?", (new_balance, new_rep, owner_id)
    )

    return results, total_income, complaints


async def maybe_daily_tick(db_conn, user_row, bot=None):
    """Раз в день: аренда, зарплаты, коммуналка, случайные события."""
    today = time.strftime("%Y-%m-%d")
    if user_row["last_daily_tick"] == today:
        return None

    owner_id = user_row["user_id"]
    workers = await db.get_workers(db_conn, owner_id)
    salaries = sum(config.WORKER_LEVELS[w["level"]]["salary"] for w in workers)
    utilities = config.UTILITIES_PER_DAY + user_row["washes_today"] * config.UTILITIES_PER_WASH
    total_expenses = config.RENT_PER_DAY + salaries + utilities

    new_balance = user_row["balance"] - total_expenses

    report_lines = [
        f"📅 Итоги дня:",
        f"— Аренда: -{config.RENT_PER_DAY}💰",
        f"— Зарплаты ({len(workers)} чел.): -{salaries}💰",
        f"— Коммуналка: -{utilities}💰",
    ]

    events = []

    # Поломка бокса
    if random.random() < config.DAILY_BREAKDOWN_CHANCE:
        bays = await db.get_bays(db_conn, owner_id)
        free_or_busy = [b for b in bays if b["status"] != "broken"]
        if free_or_busy:
            bay = random.choice(free_or_busy)
            downtime = random.uniform(config.BREAKDOWN_DOWNTIME_MIN, config.BREAKDOWN_DOWNTIME_MAX)
            await db_conn.execute(
                "UPDATE bays SET status='broken', broken_until=? WHERE bay_id=?",
                (time.time() + downtime, bay["bay_id"]),
            )
            events.append(("breakdown", bay["bay_id"], downtime))
            report_lines.append(f"🔧 Сломался бокс #{bay['bay_id']}! Простой ~{int(downtime/3600)}ч, или чинить за {config.BREAKDOWN_REPAIR_COST}💰 (/repair)")

    # Проверка санстанции
    if random.random() < config.DAILY_SANITARY_CHANCE:
        fine = round(random.uniform(config.SANITARY_FINE_MIN, config.SANITARY_FINE_MAX), 1)
        new_balance -= fine
        report_lines.append(f"🕵️ Проверка санстанции: штраф -{fine}💰")

    # VIP-событие (интерактивное)
    if random.random() < config.DAILY_VIP_EVENT_CHANCE:
        expires = time.time() + 3 * 3600  # 3 часа на решение
        await db_conn.execute(
            "INSERT INTO pending_events (owner_id, event_type, payload, created_at, expires_at, resolved) "
            "VALUES (?, 'vip_client', '{}', ?, ?, 0)",
            (owner_id, time.time(), expires),
        )
        report_lines.append("🚗 Похоже, к вам хочет заехать VIP-клиент. Загляните в /events!")

    await db_conn.execute(
        "UPDATE users SET balance=?, washes_today=0, last_daily_tick=? WHERE user_id=?",
        (new_balance, today, owner_id),
    )

    return {"lines": report_lines, "events": events, "expenses": total_expenses}


async def unlock_broken_bays(db_conn, owner_id: int):
    now = time.time()
    await db_conn.execute(
        "UPDATE bays SET status='free', broken_until=0 WHERE owner_id=? AND status='broken' AND broken_until<=?",
        (owner_id, now),
    )


async def process_user_tick(db_conn, user_id: int, bot=None):
    """Полный игровой тик для одного пользователя. Вызывается из фонового цикла."""
    user_row = await db.get_user(db_conn, user_id)
    if not user_row:
        return

    await unlock_broken_bays(db_conn, user_id)
    await generate_client(db_conn, user_row)
    await match_queue(db_conn, user_row)

    user_row = await db.get_user(db_conn, user_id)  # балансы/репутация могли не измениться, но перечитаем
    results, income, complaints = await resolve_orders(db_conn, user_row)

    user_row = await db.get_user(db_conn, user_id)
    daily = await maybe_daily_tick(db_conn, user_row, bot=bot)

    await db_conn.commit()

    if bot and (results or daily):
        await update_status_message(bot, user_id, results, income, daily)

async def update_status_message(bot, user_id: int, results, income, daily):
    new_lines = []
    if results:
        new_lines.append(f"✅ Обслужено клиентов: {len(results)}, доход +{round(income,1)}💰")
        complaints = [r for r in results if r["complaint"]]
        if complaints:
            new_lines.append(f"😡 Жалоб: {len(complaints)}")
    if daily:
        new_lines.extend(daily["lines"])

    if not new_lines:
        return

    now = time.time()
    history = _event_history.setdefault(user_id, [])
    history.append((now, "\n".join(new_lines)))
    _event_history[user_id] = history[-3:]  # оставляем только последние 3

    text = "\n\n".join(f"🕒 {relative_time(ts)}\n{t}" for ts, t in _event_history[user_id])

    message_id = _last_status_message.get(user_id)
    if message_id:
        try:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=text)
            return
        except Exception as e:
            logger.info(f"Не удалось отредактировать статус {user_id}: {e}")

    try:
        msg = await bot.send_message(user_id, text)
        _last_status_message[user_id] = msg.message_id
    except Exception as e:
        logger.warning(f"Не удалось отправить статус {user_id}: {e}")