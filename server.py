"""
MCP server kết nối vào xiaozhi.me relay.
Chạy: python server.py
"""
import asyncio
import json
import logging
import os
import re
import httpx
import xml.etree.ElementTree as ET
import websockets
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RELAY_URL = os.environ["RELAY_URL"]
HERE_API_KEY = os.environ["HERE_API_KEY"]

# ── Ticker aliases (tên công ty → mã cổ phiếu) ───────────────────────────────
TICKER_ALIASES = {
    "vinamilk": "VNM", "vinhomes": "VHM", "vingroup": "VIC",
    "hòa phát": "HPG", "hoa phat": "HPG",
    "vietcombank": "VCB", "vcb": "VCB",
    "vietinbank": "CTG", "bidv": "BID",
    "fpt": "FPT", "masan": "MSN", "pnj": "PNJ",
    "mb bank": "MBB", "mb": "MBB", "mbbank": "MBB",
    "techcombank": "TCB", "acb": "ACB",
    "sacombank": "STB", "vpbank": "VPB",
    "sabeco": "SAB", "habeco": "BHN",
    "petrolimex": "PLX", "pvgas": "GAS",
    "vietnam airlines": "HVN",
    "thế giới di động": "MWG", "the gioi di dong": "MWG",
}

CATEGORY_MAP = {
    "thể thao": "the-thao", "bóng đá": "the-thao", "thể dục": "the-thao",
    "kinh doanh": "kinh-doanh", "kinh tế": "kinh-doanh", "tài chính": "kinh-doanh",
    "thế giới": "the-gioi", "quốc tế": "the-gioi",
    "công nghệ": "khoa-hoc", "khoa học": "khoa-hoc",
    "giải trí": "giai-tri", "âm nhạc": "giai-tri",
    "sức khỏe": "suc-khoe", "y tế": "suc-khoe",
    "giáo dục": "giao-duc", "pháp luật": "phap-luat",
}

TOOLS = [
    {
        "name": "get_news_vietnam",
        "description": (
            "Lấy tin tức mới nhất từ VnExpress. Gọi khi người dùng muốn nghe tin tức, "
            "hỏi có gì mới, hoặc hỏi tin theo danh mục (thể thao, kinh doanh, thế giới, "
            "công nghệ, giải trí, sức khỏe). Trả về nhiều tiêu đề để người dùng chọn "
            "hoặc tóm tắt nội dung."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Danh mục: the-thao, kinh-doanh, the-gioi, khoa-hoc, giai-tri, suc-khoe, giao-duc, phap-luat. Để trống = tin mới nhất.",
                },
                "count": {
                    "type": "integer",
                    "description": "Số lượng tin muốn lấy (1-10). Mặc định 5.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_weather_vietnam",
        "description": (
            "Lấy thông tin thời tiết tại các thành phố Việt Nam. "
            "Nếu người dùng không nói rõ thành phố, mặc định là Hồ Chí Minh."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Tên thành phố. Mặc định: Hồ Chí Minh. Ví dụ: Hà Nội, Đà Nẵng, Cần Thơ.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_stock_price",
        "description": (
            "Tra giá cổ phiếu trên sàn chứng khoán Việt Nam (HOSE, HNX). "
            "Gọi khi người dùng hỏi giá cổ phiếu, thị trường chứng khoán, "
            "ví dụ: VNM, VIC, HPG, VCB, FPT, VNIndex..."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Mã cổ phiếu (VD: VNM, VIC, HPG) hoặc tên công ty (VD: Vinamilk, Hòa Phát). Dùng VNINDEX để tra chỉ số thị trường.",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_gold_price",
        "description": (
            "Tra giá vàng SJC và vàng nhẫn hiện tại tại Việt Nam. "
            "Gọi khi người dùng hỏi giá vàng hôm nay."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_crypto_price",
        "description": (
            "Tra giá tiền điện tử (Bitcoin, Ethereum, và các coin phổ biến). "
            "Gọi khi người dùng hỏi giá Bitcoin, BTC, ETH, crypto..."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "coins": {
                    "type": "string",
                    "description": "Tên coin, ví dụ: bitcoin, ethereum, BTC, ETH, BNB, SOL. Mặc định: bitcoin,ethereum.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_traffic_vietnam",
        "description": (
            "Xem tình hình giao thông hiện tại tại các thành phố Việt Nam. "
            "Gọi khi người dùng hỏi kẹt xe, tắc đường, tình hình giao thông, "
            "đường có thông không. Mặc định là Hồ Chí Minh."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Tên thành phố hoặc khu vực. Mặc định: Hồ Chí Minh. Ví dụ: Hà Nội, Đà Nẵng, Quận 1, Thủ Đức.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_trending_topics",
        "description": (
            "Lấy danh sách chủ đề đang hot/trending trên mạng tại Việt Nam hôm nay "
            "(Google Trends Việt Nam). Gọi khi người dùng hỏi chủ đề hot, "
            "đang trending, mọi người đang nói gì..."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def fetch_rss(url: str) -> list:
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            desc_el = item.find("description")
            if title_el is not None and title_el.text:
                desc = desc_el.text if desc_el is not None and desc_el.text else ""
                desc = re.sub(r"<[^>]+>", " ", desc).strip()
                items.append({"title": title_el.text.strip(), "description": desc})
        return items
    except Exception as e:
        log.error(f"RSS fetch error {url}: {e}")
        return []


# ── Tool implementations ──────────────────────────────────────────────────────

async def tool_get_news(args: dict) -> str:
    category = args.get("category", "").strip().lower()
    count = min(int(args.get("count", 5)), 10)
    slug = CATEGORY_MAP.get(category, category) if category else ""
    url = f"https://vnexpress.net/rss/{slug}.rss" if slug else "https://vnexpress.net/rss/tin-moi-nhat.rss"
    items = await fetch_rss(url)
    if not items:
        return "Không lấy được tin tức lúc này, xin thử lại sau."
    selected = items[:count]
    if count == 1:
        news = selected[0]
        return f"Tiêu đề: {news['title']}\nNội dung: {news['description'][:400]}"
    lines = [f"{i+1}. {item['title']}" for i, item in enumerate(selected)]
    return "Tin tức mới nhất:\n" + "\n".join(lines)


async def tool_get_weather(args: dict) -> str:
    city = args.get("city", "Hồ Chí Minh")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                f"https://wttr.in/{city}?format=j1",
                headers={"Accept": "application/json"},
            )
            data = r.json()
            current = data["current_condition"][0]
            temp_c = current["temp_C"]
            feels = current["FeelsLikeC"]
            humidity = current["humidity"]
            desc = current["weatherDesc"][0]["value"]
            return (
                f"Thời tiết tại {city}: {desc}, nhiệt độ {temp_c}°C "
                f"(cảm giác {feels}°C), độ ẩm {humidity}%."
            )
    except Exception as e:
        log.error(f"Weather error: {e}")
        return f"Không lấy được thông tin thời tiết cho {city}."


async def tool_get_stock(args: dict) -> str:
    from datetime import datetime, timedelta

    raw = args.get("ticker", "VNM").strip()
    ticker = TICKER_ALIASES.get(raw.lower(), raw.upper())

    today = datetime.now()
    end_date = today.strftime("%d/%m/%Y")
    start_date = (today - timedelta(days=10)).strftime("%d/%m/%Y")

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            if ticker in {"VNINDEX", "HNXINDEX", "UPCOM", "VN30", "HNX30"}:
                # CafeF returns index data as part of any stock query — use VNM as vehicle
                r = await client.get(
                    "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx",
                    params={"Symbol": "VNM", "StartDate": start_date, "EndDate": end_date, "PageIndex": 1, "PageSize": 1},
                )
                data = r.json()
                if not data.get("Success") or not data.get("Data"):
                    return "Không lấy được chỉ số thị trường."
                idx = data["Data"]
                close = float(idx.get("ClosePriceIndex", 0))
                chg = float(idx.get("ChgIndex", 0))
                pct = float(idx.get("PctIndex", 0))
                date = idx.get("DateIndex", "")
                direction = "tăng" if chg >= 0 else "giảm"
                return (
                    f"VN-Index ngày {date}: {close:,.2f} điểm "
                    f"({direction} {abs(chg):.2f} điểm, {abs(pct):.2f}%)"
                )
            else:
                r = await client.get(
                    "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx",
                    params={"Symbol": ticker, "StartDate": start_date, "EndDate": end_date, "PageIndex": 1, "PageSize": 3},
                )
                data = r.json()

        if not data.get("Success") or not data.get("Data"):
            return f"Không tìm thấy cổ phiếu {ticker}. Kiểm tra lại mã."

        rows = data["Data"].get("Data", [])
        if not rows:
            return f"Không có dữ liệu giao dịch gần đây cho {ticker}."

        last = rows[0]
        close  = float(last.get("GiaDongCua", 0)) * 1000
        open_p = float(last.get("GiaMoCua", 0)) * 1000
        high   = float(last.get("GiaCaoNhat", 0)) * 1000
        low    = float(last.get("GiaThapNhat", 0)) * 1000
        volume = int(last.get("KhoiLuongKhopLenh", 0))
        date   = last.get("Ngay", "")
        change_str = last.get("ThayDoi", "")

        return (
            f"Cổ phiếu {ticker} ngày {date}: "
            f"đóng cửa {close:,.0f} đ ({change_str}), "
            f"mở cửa {open_p:,.0f} đ, cao {high:,.0f} đ, thấp {low:,.0f} đ, "
            f"khối lượng {volume:,} cổ phiếu."
        )
    except Exception as e:
        log.error(f"Stock error {ticker}: {e}")
        return f"Không lấy được giá cổ phiếu {ticker}."


async def tool_get_gold(args: dict) -> str:
    # 1 PAXG = 1 troy oz gold; 1 lượng VN = 37.5g; 1 troy oz = 31.1035g
    GRAMS_PER_LUONG = 37.5
    GRAMS_PER_TROY_OZ = 31.1035

    try:
        async with httpx.AsyncClient(timeout=8.0, headers={"Accept": "application/json"}) as client:
            r_gold, r_fx = await asyncio.gather(
                client.get("https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd"),
                client.get("https://api.exchangerate-api.com/v4/latest/USD"),
            )
        gold_usd_per_oz = r_gold.json()["pax-gold"]["usd"]
        usd_vnd = r_fx.json()["rates"]["VND"]

        gold_usd_per_luong = gold_usd_per_oz * (GRAMS_PER_LUONG / GRAMS_PER_TROY_OZ)
        gold_vnd_per_luong = gold_usd_per_luong * usd_vnd

        # SJC in Vietnam typically has a ~5–10% premium over international; note this
        return (
            f"Giá vàng quốc tế hôm nay:\n"
            f"  Vàng thế giới: ${gold_usd_per_oz:,.0f}/troy oz (${gold_usd_per_luong:,.0f}/lượng)\n"
            f"  Quy đổi VND (tỷ giá ~{usd_vnd:,.0f}): ~{gold_vnd_per_luong/1_000_000:.1f} triệu đ/lượng\n"
            f"  (Lưu ý: Giá vàng SJC trong nước có thể cao hơn thị trường quốc tế)"
        )
    except Exception as e:
        log.error(f"Gold price error: {e}")
        return "Không lấy được giá vàng lúc này."


COIN_ID_MAP = {
    "btc": "bitcoin", "eth": "ethereum", "bnb": "binancecoin",
    "sol": "solana", "xrp": "ripple", "ada": "cardano",
    "doge": "dogecoin", "dot": "polkadot", "matic": "matic-network",
    "avax": "avalanche-2", "link": "chainlink", "ltc": "litecoin",
    "usdt": "tether", "usdc": "usd-coin",
}


async def tool_get_crypto(args: dict) -> str:
    raw = args.get("coins", "bitcoin,ethereum").strip().lower()
    # Map common short names to CoinGecko IDs
    parts = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
    ids = [COIN_ID_MAP.get(p, p) for p in parts]
    ids_str = ",".join(ids[:5])  # max 5 coins

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                f"https://api.coingecko.com/api/v3/simple/price"
                f"?ids={ids_str}&vs_currencies=usd&include_24hr_change=true",
                headers={"Accept": "application/json"},
            )
            data = r.json()

        if not data:
            return "Không lấy được giá crypto lúc này."

        lines = []
        for coin_id, info in data.items():
            price_usd = info.get("usd", 0)
            change_24h = info.get("usd_24h_change", 0)
            direction = "tăng" if change_24h >= 0 else "giảm"
            name = coin_id.capitalize()
            lines.append(
                f"{name}: ${price_usd:,.2f} ({direction} {abs(change_24h):.1f}% 24h)"
            )

        return "Giá crypto:\n" + "\n".join(lines)
    except Exception as e:
        log.error(f"Crypto error: {e}")
        return "Không lấy được giá crypto lúc này."


async def tool_get_traffic(args: dict) -> str:
    location = args.get("location", "Hồ Chí Minh").strip() or "Hồ Chí Minh"
    query = location if "việt nam" in location.lower() or "vietnam" in location.lower() else f"{location}, Việt Nam"

    try:
        async with httpx.AsyncClient(timeout=10.0, headers={"Accept": "application/json"}) as client:
            # Step 1: geocode location name → lat/lng
            geo = await client.get(
                "https://geocode.search.hereapi.com/v1/geocode",
                params={"q": query, "apiKey": HERE_API_KEY, "lang": "vi"},
            )
            geo_data = geo.json()
            if not geo_data.get("items"):
                return f"Không tìm thấy địa điểm '{location}'."

            pos = geo_data["items"][0]["position"]
            lat, lng = pos["lat"], pos["lng"]
            place_name = geo_data["items"][0].get("title", location)

            # Step 2: query traffic flow in 5km radius
            flow = await client.get(
                "https://data.traffic.hereapi.com/v7/flow",
                params={
                    "in": f"circle:{lat},{lng};r=5000",
                    "locationReferencing": "olr",
                    "apiKey": HERE_API_KEY,
                },
            )
            results = flow.json().get("results", [])

        if not results:
            return f"Không có dữ liệu giao thông cho khu vực {location}."

        # Aggregate jam factors (ignore low-confidence segments)
        jam_factors = [
            r["currentFlow"]["jamFactor"]
            for r in results
            if r.get("currentFlow") and r["currentFlow"].get("confidence", 0) >= 0.5
        ]
        if not jam_factors:
            return f"Không đủ dữ liệu giao thông cho khu vực {location}."

        avg_jam = sum(jam_factors) / len(jam_factors)
        congested = [r for r in results if r.get("currentFlow", {}).get("jamFactor", 0) >= 7]

        # Overall level
        if avg_jam < 2:
            level = "thông thoáng"
        elif avg_jam < 4:
            level = "bình thường"
        elif avg_jam < 6:
            level = "hơi đông"
        elif avg_jam < 8:
            level = "kẹt xe"
        else:
            level = "kẹt nặng"

        # Top congested roads
        congested_sorted = sorted(congested, key=lambda r: r["currentFlow"]["jamFactor"], reverse=True)
        hot_roads = []
        seen = set()
        for r in congested_sorted[:10]:
            name = r.get("location", {}).get("description") or r.get("location", {}).get("name", "")
            if name and name not in seen:
                seen.add(name)
                jf = r["currentFlow"]["jamFactor"]
                spd = r["currentFlow"]["speed"] * 3.6  # m/s → km/h
                hot_roads.append(f"  - {name}: {spd:.0f} km/h (kẹt {jf:.0f}/10)")
            if len(hot_roads) >= 5:
                break

        pct_congested = sum(1 for j in jam_factors if j >= 5) * 100 // len(jam_factors)
        summary = (
            f"Giao thông tại {place_name}: {level.upper()} "
            f"(chỉ số kẹt trung bình {avg_jam:.1f}/10, {pct_congested}% đường đông)\n"
        )
        if hot_roads:
            summary += "Khu vực kẹt nhất:\n" + "\n".join(hot_roads)
        else:
            summary += "Không có điểm kẹt nặng nào trong bán kính 5km."

        return summary

    except Exception as e:
        log.error(f"Traffic error: {e}")
        return f"Không lấy được thông tin giao thông cho {location}."


async def tool_get_trending(args: dict) -> str:
    # Google News RSS Vietnam top stories
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        ) as client:
            r = await client.get("https://news.google.com/rss?hl=vi&gl=VN&ceid=VN:vi")

        root = ET.fromstring(r.content)
        items = root.findall(".//item")

        titles = []
        for item in items:
            t = item.find("title")
            if t is not None and t.text:
                # Strip source suffix like " - VnExpress"
                title = re.sub(r"\s*-\s*[^-]{3,40}$", "", t.text.strip())
                titles.append(title)
            if len(titles) >= 8:
                break

        if not titles:
            return "Không lấy được chủ đề trending lúc này."

        lines = [f"{i+1}. {t}" for i, t in enumerate(titles)]
        return "Tin tức nổi bật / đang hot tại Việt Nam hôm nay:\n" + "\n".join(lines)
    except Exception as e:
        log.error(f"Trending error: {e}")
        return "Không lấy được chủ đề trending lúc này."


# ── MCP protocol ──────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "get_news_vietnam":    tool_get_news,
    "get_weather_vietnam": tool_get_weather,
    "get_stock_price":     tool_get_stock,
    "get_gold_price":      tool_get_gold,
    "get_crypto_price":    tool_get_crypto,
    "get_traffic_vietnam": tool_get_traffic,
    "get_trending_topics": tool_get_trending,
}


async def send(ws, msg: dict):
    await ws.send(json.dumps(msg, ensure_ascii=False))


async def handle_message(ws, raw: str):
    try:
        msg = json.loads(raw)
    except Exception:
        log.error(f"Invalid JSON: {raw[:200]}")
        return

    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        log.info("← initialize")
        await send(ws, {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "xiaozhi-vietnam-mcp", "version": "2.0.0"},
            },
        })

    elif method == "notifications/initialized":
        log.info("← notifications/initialized")

    elif method == "tools/list":
        log.info("← tools/list")
        await send(ws, {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        })

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        log.info(f"← tools/call: {tool_name}({arguments})")

        handler = TOOL_HANDLERS.get(tool_name)
        if handler:
            try:
                result_text = await handler(arguments)
                await send(ws, {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                        "isError": False,
                    },
                })
                log.info(f"→ {tool_name} OK")
            except Exception as e:
                await send(ws, {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Lỗi: {e}"}],
                        "isError": True,
                    },
                })
        else:
            await send(ws, {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
            })

    elif method == "ping":
        await send(ws, {"jsonrpc": "2.0", "id": msg_id, "result": {}})

    else:
        log.warning(f"Unknown method: {method}")


async def run():
    backoff = 3
    while True:
        try:
            log.info(f"Connecting to relay...")
            async with websockets.connect(RELAY_URL, ping_interval=30, ping_timeout=10) as ws:
                log.info("Connected — 7 tools ready: news, weather, stock, gold, crypto, traffic, trending")
                backoff = 3
                async for raw in ws:
                    await handle_message(ws, raw)
        except websockets.exceptions.ConnectionClosed as e:
            log.warning(f"Connection closed: {e}. Reconnecting in {backoff}s...")
        except Exception as e:
            log.error(f"Error: {e}. Reconnecting in {backoff}s...")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    asyncio.run(run())
