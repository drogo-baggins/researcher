# 🔒 セキュリティと設定ガイド

researcher の Streamlit WebUI におけるセキュリティについての重要な情報です。

## ⚠️ セキュリティに関する重要な注意

**researcher は個人的なローカル研究ツールとしての使用を想定しています。**

以下の点を十分に理解した上で使用してください。

## 1. アーキテクチャとセキュリティの前提

### Streamlit WebUI の特性

```
┌─────────────────────────────────────────┐
│  ブラウザ (ローカル)                    │
│  http://localhost:8501                  │
└──────────┬──────────────────────────────┘
           │ (ローカルのみ)
┌──────────▼──────────────────────────────┐
│  Streamlit WebUI                        │
│  - 認証機構なし                         │
│  - セッションデータ = 平文保存          │
│  - MCP ツール経由のファイルアクセス     │
└──────────┬──────────────────────────────┘
           │ (IPC or ネットワーク)
┌──────────▴──────────────────────────────┐
│  外部コンポーネント                     │
│  - Ollama (LLM)                        │
│  - SearXNG (検索エンジン)              │
│  - MCP サーバー (ファイルアクセス等)   │
└─────────────────────────────────────────┘
```

### 認証がない理由

1. **ローカルのみの使用**: インターネット経由のアクセスを想定していない
2. **個人ツール**: 複数ユーザーの分離機能が不要
3. **シンプルさ**: 設定複雑度を最小化

**結果**: ローカルネットワークに接続されたマシンから誰でもアクセス可能

## 2. セキュリティ上の制限事項

### 2.1 ローカルホスト制限

**デフォルト動作:**

```
WebUI は localhost (127.0.0.1) にのみバインドされます
→ 同じマシン上からのみアクセス可能
→ ローカルネットワークからはアクセス不可
```

**確認方法:**

```bash
lsof -i :8501
# 出力例:
# COMMAND   PID     USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
# Python  12345 username    5u  IPv4 567890      0t0  TCP localhost:8501 (LISTEN)
```

### 2.2 セッションデータの暗号化がない

**保存内容:**

```json
{
  "id": "session_123",
  "name": "政治ニュース調査",
  "history": [
    {"role": "user", "content": "最新の支持率は？"},
    {"role": "assistant", "content": "検索結果から..."}
  ],
  "model": "llama2",
  "language": "ja",
  "created_at": "2024-01-20T10:30:00",
  "updated_at": "2024-01-20T10:35:00"
}
```

**保存場所:**

```
~/.researcher/sessions.db (SQLite, 平文)
```

**リスク:**
- ローカルマシンへのアクセス権を持つユーザーは全会話を閲覧可能
- ディスク復旧ツールで削除済みセッションも復旧可能

**対策:**
- 機密情報をプロンプトに入力しない
- FDE (Full Disk Encryption) を使用

### 2.3 認証機構がない

**Streamlit デフォルト:**

- Cookie ベースの認証: **なし**
- API トークン: **なし**
- ユーザー権限管理: **なし**

**ローカルネットワークでの影響:**

マシンの IP アドレスが分かると、同じネットワーク上の誰でも WebUI にアクセス可能:

```bash
# ローカルネットワークのマシンから
http://192.168.1.100:8501

# すべてのセッション表示・編集・削除が可能
```

### 2.4 MCP ツールによるファイルアクセス

**MCP (Model Context Protocol) の役割:**

LLM が以下の操作をプロンプト経由で実行可能:

- ファイルの読取
- ファイルの作成
- ファイルの削除
- コマンド実行

**リスク:**

```
ユーザー入力 → LLM 処理
    ↓ (MCP ツール経由)
  ファイルシステム
```

**悪意あるプロンプト例:**

```
「ホームディレクトリのすべてのファイルをリスト表示してください」
→ LLM が MCP ツールを使用してファイルアクセス

「~/.ssh/id_rsa の内容を表示してください」
→ 秘密鍵が LLM に送信される可能性
```

**対策:**
- プロンプト内容をよく確認
- 信頼できないソースからのプロンプト実行は避ける
- 重要なファイルのアクセス権限を制限

## 3. 安全な運用方法

### 3.1 単一ユーザー、ローカル使用（推奨）

**設定:**

```bash
# デフォルト設定のまま使用
researcher-webui

# ローカルマシンのブラウザからのみアクセス
```

**セキュリティレベル:** 🟢 **安全** (ただし同一マシン上のユーザー間での分離なし)

### 3.2 VPN 経由のリモートアクセス

**使用例:**

```bash
# ローカルマシン上で WebUI を起動
researcher-webui

# リモートマシンから VPN 経由で接続
ssh -N -L 8501:localhost:8501 user@vpn-server
# ブラウザで http://localhost:8501 にアクセス
```

**セキュリティレベル:** 🟡 **中程度** (認証なしですが、VPN で保護)

**注意:**
- VPN の認証情報は別途管理が必要
- VPN 接続内の全ユーザーがアクセス可能

### 3.3 リバースプロキシ + 認証（更に安全）

**例: Nginx + Basic Auth**

```nginx
server {
    listen 443 ssl;
    server_name researcher.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    auth_basic "researcher";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**セキュリティレベル:** 🟢 **安全** (HTTPS + 認証)

## 4. セッションデータの管理

### 4.1 セッションの保存内容

```json
{
  "id": "uuid",
  "name": "セッション名",
  "model": "使用したモデル",
  "language": "ja|en",
  "history": [
    {
      "role": "user|assistant",
      "content": "会話内容"
    }
  ],
  "created_at": "ISO8601形式",
  "updated_at": "ISO8601形式"
}
```

### 4.2 セッションの暗号化

**現状:** 暗号化されていません

**推奨される対策:**

```bash
# LUKS ボリュームを使用
sudo cryptsetup luksFormat /dev/sdX
sudo cryptsetup luksOpen /dev/sdX researcher_vol
sudo mkfs.ext4 /dev/mapper/researcher_vol

# ~/.researcher をマウント
sudo mount /dev/mapper/researcher_vol ~/.researcher
```

### 4.3 セッションのバックアップ

**定期的なバックアップ:**

```bash
# 毎日のバックアップ
0 2 * * * cp ~/.researcher/sessions.db ~/.researcher/sessions.db.$(date +\%Y\%m\%d)

# 7日分を保持
0 3 * * * find ~/.researcher -name "sessions.db.*" -mtime +6 -delete
```

### 4.4 セッションの削除

**UI から削除:**

```
サイドバーで該当セッション → 🗑️ ボタン
```

**コマンドラインから全削除:**

```bash
rm ~/.researcher/sessions.db
```

**特定セッションの完全削除:**

SQLite CLI で削除後、vacuum で領域解放:

```bash
sqlite3 ~/.researcher/sessions.db
> DELETE FROM sessions WHERE id = 'session_id';
> VACUUM;
> .quit
```

## 5. ネットワークセキュリティ設定

### 5.1 デフォルト設定（推奨）

```bash
researcher-webui
# バインド: localhost:8501
# アクセス可能範囲: 同一マシンのみ
```

### 5.2 特定 IP からのアクセスのみ許可

**方法: ファイアウォール設定**

```bash
# macOS (pf)
echo "pass in on lo0 proto tcp from any to any port 8501" | sudo pfctl -f -

# Linux (iptables)
sudo iptables -A INPUT -p tcp --dport 8501 -s 192.168.1.0/24 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8501 -j DROP
```

### 5.3 Streamlit 設定による制御

```toml
# ~/.streamlit/config.toml
[server]
port = 8501
# ローカルホストのみにバインド（デフォルト）
# headless = true は Jupyter/Colab でのみ使用

[client]
# エラーメッセージ詳細表示を無効化
showErrorDetails = false
```

## 6. チェックリスト

起動前に確認してください:

- [ ] **ローカル使用確認**: インターネット接続マシンでの使用ではない
- [ ] **機密情報チェック**: SSHキーや APIキーをプロンプトに入力していない
- [ ] **ネットワーク設定**: ローカルホストのみにバインドされているか確認
- [ ] **権限管理**: `~/.researcher/` の権限が適切か確認
  ```bash
  ls -la ~/.researcher/
  # drwx------  (700) が理想
  ```
- [ ] **定期バックアップ**: セッションデータの定期バックアップを設定
- [ ] **ログ監視**: 異常なアクセスログがないか確認

## 7. トラブルシューティング

### Q: 他のマシンから WebUI にアクセスしたいのですが？

**A:** セキュリティの観点から、以下の順序で検討してください:

1. **VPN 経由でのアクセス** (推奨)
2. **SSH トンネル経由** (`ssh -L`)
3. **リバースプロキシ + HTTPS + 認証**

インターネット直通でのバインドは避けてください。

### Q: セッションを暗号化できますか？

**A:** 現在、Streamlit WebUI には組み込みの暗号化機能がありません。代替案:

1. **LUKS 暗号化パーティション** (OS レベルの暗号化)
2. **ecryptfs** (`~/.researcher` を暗号化)
3. **BitLocker / FileVault** (ディスク全体暗号化)

### Q: LLM にファイルアクセスさせたくないのですが？

**A:** 現在、MCP ツールの選択的無効化機能はありません。代わりに:

- プロンプト入力を信頼できるソースのみに限定
- MCP ツールのアクセス権限を制限 (パーミッション設定)
- 重要ファイルを別ディレクトリに隔離

## 参考資料

- [Streamlit セキュリティドキュメント](https://docs.streamlit.io/develop/concepts/configuration/secrets-management)
- [OWASP セキュリティガイド](https://owasp.org/)
- [MCP 仕様](https://spec.modelcontextprotocol.io/)
