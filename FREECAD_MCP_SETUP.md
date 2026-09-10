# FreeCAD MCP セットアップ記録

構築日: 2026-09-07 / FreeCAD 1.1.3 (Windows 11)

## 構成

```
Claude Code  --stdio-->  freecad-mcp (venv)  --XML-RPC 127.0.0.1:9875-->  FreeCAD GUI (FreeCADMCP アドオン)
```

FreeCAD の GUI が起動していないと MCP ツールは全て失敗する。ヘッドレスでは動かない。

## 設置場所

| 要素 | パス |
|---|---|
| upstream クローン | `vendor/freecad-mcp`（neka-nat/freecad-mcp, v0.1.22） |
| FreeCAD アドオン | `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADMCP\` |
| RPC 設定 | `%APPDATA%\FreeCAD\v1-1\freecad_mcp_settings.json` |
| MCP サーバ venv | `.venv-mcp\Scripts\freecad-mcp.exe` |
| Claude Code 設定 | `.mcp.json`（プロジェクトスコープ） |

**注意: README の Windows パス `%APPDATA%\FreeCAD\Mod` は FreeCAD 1.0 以前のもの。**
1.1 は `FreeCAD.getUserAppDataDir()` = `%APPDATA%\FreeCAD\v1-1\` を返すので `v1-1\Mod` に置く。

`uvx freecad-mcp` ではなく専用 venv にソースからインストールしている。
アドオンと MCP サーバが同一コミットになりバージョン不整合が起きないため。

## RPC 設定

```json
{ "remote_enabled": false, "allowed_ips": "127.0.0.1", "auto_start_rpc": true }
```

`auto_start_rpc: true` なので FreeCAD 起動と同時に RPC サーバが立ち上がる（実測 6 秒）。
手動で操作する場合は FreeCAD のワークベンチ選択で **MCP Addon** を選ぶと
Start / Stop RPC Server のツールバーが出る。

リモート接続は無効のまま。有効にすると LAN の他ホストから FreeCAD に
任意の Python を実行させられるので、必要になるまで触らない。

## 更新手順

```
git -C vendor/freecad-mcp pull
cp -r vendor/freecad-mcp/addon/FreeCADMCP "%APPDATA%/FreeCAD/v1-1/Mod/"
.venv-mcp/Scripts/python.exe -m pip install --force-reinstall ./vendor/freecad-mcp
```
アドオンと venv は必ずセットで更新すること。

## 動作確認結果

- MCP ハンドシェイク OK。ツール 15 個
  `create_document, create_object, edit_object, delete_object, execute_code_async,
   execute_code, get_view, insert_part_from_library, get_objects, get_object,
   get_parts_list, reload_document, list_documents, get_rpc_status, run_fem_analysis`
- `get_rpc_status` → `rpc_server: running`, `gui_dispatch: healthy`
- `list_documents` → `[]`

## トラブル時の切り分け

1. `netstat -ano | findstr 9875` → LISTENING が無ければ FreeCAD 側（アドオン未ロード / 未起動）
2. LISTENING があるのに MCP がこける → venv 側。`.venv-mcp\Scripts\freecad-mcp.exe` を
   直接起動して stderr を見る
3. FreeCAD のビュー → パネル → レポートビュー に `[MCP]` のログが出る
