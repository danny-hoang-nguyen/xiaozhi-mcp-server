# Xiaozhi MCP Server — Tiếng Việt

MCP server Python kết nối vào [Xiaozhi](https://xiaozhi.me) thông qua WebSocket relay, cung cấp 8 công cụ thực tế cho trợ lý AI nói tiếng Việt.

## Tính năng

| Tool | Mô tả | Nguồn dữ liệu |
|------|-------|---------------|
| `get_news_vietnam` | Tin tức mới nhất theo danh mục | VnExpress RSS |
| `get_weather_vietnam` | Thời tiết các thành phố Việt Nam | wttr.in |
| `get_stock_price` | Giá cổ phiếu HOSE/HNX, VN-Index | CafeF |
| `get_gold_price` | Giá vàng quốc tế quy đổi VND | CoinGecko + ExchangeRate API |
| `get_crypto_price` | Giá Bitcoin, Ethereum, các coin | CoinGecko |
| `get_traffic_vietnam` | Tình hình giao thông theo khu vực | HERE Maps Traffic API |
| `spotify_control` | Điều khiển Spotify (phát, dừng, tìm bài...) | Spotify Web API |
| `get_trending_topics` | Chủ đề đang hot tại Việt Nam | Google News RSS |

---

## Yêu cầu

- Python 3.10+
- Tài khoản [Xiaozhi](https://xiaozhi.me) (lấy MCP WebSocket token)
- API key [HERE Maps](https://developer.here.com) (free tier, 250k req/tháng)
- Tài khoản Spotify Premium + Spotify Developer App (để dùng tool Spotify)

---

## Cài đặt

### 1. Clone repo

```bash
git clone https://github.com/danny-hoang-nguyen/xiaozhi-mcp-server.git
cd xiaozhi-mcp-server
```

### 2. Tạo virtual environment và cài dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Tạo file `.env`

```bash
cp .env.example .env
```

Điền các giá trị vào `.env`:

```env
# Bắt buộc
RELAY_URL=wss://api.xiaozhi.me/mcp/?token=<token-của-bạn>
HERE_API_KEY=<here-api-key>

# Tùy chọn — chỉ cần nếu dùng Spotify
SPOTIFY_CLIENT_ID=<spotify-client-id>
SPOTIFY_CLIENT_SECRET=<spotify-client-secret>
SPOTIFY_REFRESH_TOKEN=<spotify-refresh-token>
```

### 4. Chạy server

```bash
python server.py
```

---

## Lấy các API key

### Xiaozhi MCP Token

1. Đăng nhập [xiaozhi.me](https://xiaozhi.me)
2. Vào phần cấu hình Agent → MCP Endpoint
3. Copy URL dạng `wss://api.xiaozhi.me/mcp/?token=...`

### HERE Maps API Key (giao thông)

1. Đăng ký tại [developer.here.com](https://developer.here.com)
2. Tạo project → Generate API Key
3. Free tier: 250.000 request/tháng, không cần thẻ tín dụng

### Spotify Refresh Token

Spotify yêu cầu OAuth2 — cần thực hiện một lần để lấy refresh token. Sau đó server tự gia hạn access token, không cần đăng nhập lại.

**Bước 1:** Tạo Spotify App

1. Vào [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Tạo app mới (tên tùy ý)
3. Vào Settings → Redirect URIs → thêm một URL HTTPS (xem Bước 2)
4. Lưu lại **Client ID** và **Client Secret**

**Bước 2:** Tạo callback URL công khai

Spotify không chấp nhận `http://localhost` làm redirect URI. Dùng [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/do-more-with-tunnels/trycloudflare/) để tạo URL tạm thời miễn phí:

```bash
# Cài cloudflared nếu chưa có
brew install cloudflared         # macOS
# hoặc: https://github.com/cloudflare/cloudflared/releases

# Tạo tunnel trỏ vào cổng 8888
cloudflared tunnel --url http://localhost:8888
```

Tunnel sẽ in ra URL dạng `https://xxxx.trycloudflare.com` — dùng URL này + `/callback`:

```
https://xxxx.trycloudflare.com/callback
```

Thêm URL đó vào Spotify App → Settings → Redirect URIs → Save.

**Bước 3:** Chạy script OAuth

Điền Client ID, Client Secret và Redirect URI vào đầu file `spotify_auth.py`, rồi chạy:

```bash
SPOTIFY_CLIENT_ID=xxx SPOTIFY_CLIENT_SECRET=yyy python spotify_auth.py
```

Script sẽ in URL Spotify — mở trong trình duyệt, đăng nhập, cho phép quyền. Refresh token sẽ tự động lưu vào `spotify_refresh_token.txt` và in ra terminal.

**Bước 4:** Thêm vào `.env`

```env
SPOTIFY_CLIENT_ID=<client-id>
SPOTIFY_CLIENT_SECRET=<client-secret>
SPOTIFY_REFRESH_TOKEN=<refresh-token-từ-bước-3>
```

> **Lưu ý:** `spotify_auth.py` và `spotify_refresh_token.txt` đã được thêm vào `.gitignore`. Không commit refresh token lên GitHub.

---

## Deploy lên server (tùy chọn)

Để server chạy 24/7, deploy lên VPS (DigitalOcean, Hetzner, v.v.) với systemd:

### Cài đặt trên VPS

```bash
# Upload code lên server
rsync -av . root@<server-ip>:/root/xiaozhi-mcp/

# SSH vào server
ssh root@<server-ip>

# Tạo venv và cài dependencies
python3 -m venv /root/venv
/root/venv/bin/pip install -r /root/xiaozhi-mcp/requirements.txt

# Tạo file .env trên server
nano /root/xiaozhi-mcp/.env
```

### Tạo systemd service

```bash
cat > /etc/systemd/system/xiaozhi-mcp.service << 'EOF'
[Unit]
Description=Xiaozhi MCP Server
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/root/xiaozhi-mcp
EnvironmentFile=/root/xiaozhi-mcp/.env
ExecStart=/root/venv/bin/python /root/xiaozhi-mcp/server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xiaozhi-mcp
systemctl start xiaozhi-mcp
```

### Kiểm tra log

```bash
journalctl -u xiaozhi-mcp -f
```

---

## Cách dùng với Xiaozhi

Sau khi server chạy, nói chuyện với Xiaozhi bằng tiếng Việt:

| Ví dụ câu nói | Tool được gọi |
|---------------|---------------|
| "Tin tức hôm nay có gì?" | `get_news_vietnam` |
| "Tin thể thao mới nhất" | `get_news_vietnam` (category: thể thao) |
| "Thời tiết Hà Nội hôm nay" | `get_weather_vietnam` |
| "Giá cổ phiếu VNM bao nhiêu?" | `get_stock_price` |
| "Giá vàng hôm nay" | `get_gold_price` |
| "Bitcoin giá bao nhiêu?" | `get_crypto_price` |
| "Đường về quận 1 có kẹt không?" | `get_traffic_vietnam` |
| "Phát bài Nơi này có anh" | `spotify_control` (search) |
| "Dừng nhạc" / "Next bài" | `spotify_control` (pause/next) |
| "Bài gì đang phát vậy?" | `spotify_control` (current) |
| "Mọi người đang nói gì?" | `get_trending_topics` |

### Lưu ý khi dùng Spotify

- Phải có **Spotify Premium** (API điều khiển playback yêu cầu Premium)
- App Spotify phải **đang mở** trên ít nhất một thiết bị (điện thoại, máy tính, web player)
- Server tự động phát hiện thiết bị đang active; nếu Spotify idle quá lâu server sẽ tự wake up thiết bị available

---

## Cấu trúc project

```
xiaozhi-mcp-server/
├── server.py          # MCP server chính (8 tools)
├── spotify_auth.py    # Script lấy Spotify refresh token (chạy 1 lần)
├── requirements.txt
├── .env               # Secrets (không commit)
├── .env.example       # Template
└── .gitignore
```

---

## Thêm tool mới

Mỗi tool gồm 3 phần:

**1. Khai báo schema trong `TOOLS`:**

```python
{
    "name": "my_tool",
    "description": "Mô tả để AI biết khi nào dùng tool này.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "..."}
        },
        "required": [],
    },
}
```

**2. Viết hàm xử lý:**

```python
async def tool_my_tool(args: dict) -> str:
    param = args.get("param", "default")
    # ... xử lý ...
    return "Kết quả trả về cho AI"
```

**3. Đăng ký trong `TOOL_HANDLERS`:**

```python
TOOL_HANDLERS = {
    ...
    "my_tool": tool_my_tool,
}
```

---

## License

MIT
