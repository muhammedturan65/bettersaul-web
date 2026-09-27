BetterSaul MCP — masaüstü bağlantısı
====================================

Kurulum BetterSaul MCP + Claude / ChatGPT / Gemini Desktop ile tamamlanır.
İçtihat taraması BetterSaul MCP ile yapılır.
BetterSaul ve seçtiğiniz masaüstü aynı anda açık kalır.

Claude Desktop indir: https://claude.ai/download
ChatGPT Desktop indir: https://chatgpt.com/download
Gemini Desktop indir: https://gemini.google/desktop/

1) Claude Desktop
   %APPDATA%\Claude\claude_desktop_config.json
   Ayar yazılırken uygulama kapanır; yazılınca yeniden açılır. Yeni sohbet açın.

2) ChatGPT Desktop
   Yalnızca %USERPROFILE%\.codex\config.toml
   [mcp_servers.BetterSaul] — Windows yolları tek tırnaklı TOML.
   Ayar yazılırken ChatGPT kapanır; yazılınca yeniden açılır. Yeni sohbet açın.

3) Gemini
   Yalnızca %USERPROFILE%\.gemini\settings.json içindeki mcpServers.
   Ayar yazılırken Gemini kapanır; yazılınca yeniden açılır. Yeni sohbet açın.

4) Cursor
   cursor-mcp.json içeriğini Settings → MCP’ye yapıştırın
   veya %USERPROFILE%\.cursor\mcp.json dosyasına ekleyin.

5) HTTP (BetterSaul açıkken)
   https://127.0.0.1:8000/mcp

stdio komutu:
  "C:\Users\user\AppData\Local\BetterSaul\runtime\python\python.exe" "C:\Users\user\AppData\Local\BetterSaul\app\engine\run_mcp.py" --stdio
çalışma dizini:
  C:\Users\user\AppData\Local\BetterSaul\app\engine

Dilekçe BetterSaul Geçmiş’e yazılır. Tam metin gönderilir.
