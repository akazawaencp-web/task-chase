# Task #32: スマホからClaude Codeを操作する方法 — 調査レポート

調査日: 2026-03-08

---

## 1. エグゼクティブサマリー（結論）

**最もオススメの方法: Claude Code Remote Control（公式機能）**

2026年2月25日にAnthropicが公式リリースした「Remote Control」機能を使えば、PCのターミナルでClaude Codeを起動したまま、スマホのClaudeアプリからそのセッションを操作できる。追加アプリのインストールやVPN設定は不要。QRコードをスキャンするだけで接続完了。

RIOの使い方（PCでdeepdiveスキルを実行 → スマホから進捗確認・追加指示）にぴったり合致する。

**必要なもの:**
- Claude Pro（月$20）またはMax（月$100/$200）プラン
- iPhoneのClaudeアプリ（無料）
- PCのターミナルは開いたまま＆スリープさせない

---

## 2. 方法の一覧と比較

| 方法 | 難易度 | 月額費用 | セキュリティ | RIOへのオススメ度 |
|------|--------|----------|------------|-------------------|
| **1. Remote Control（公式）** | ★☆☆ 超簡単 | $0（既にPro契約なら追加なし） | ◎ TLS暗号化、ポート開放なし | ★★★ 最推奨 |
| **2. Happy Coder（無料アプリ）** | ★★☆ やや手間 | $0（完全無料） | ○ E2E暗号化 | ★★☆ 代替案 |
| **3. Claude Remote（サードパーティ）** | ★★☆ やや手間 | $0（現在無料） | ○ Cloudflare経由 | ★☆☆ 不安定 |
| **4. SSH + Termius** | ★★★ 技術者向け | Termius $15/月 | ○ SSH暗号化 | ☆☆☆ 非推奨 |
| **5. LINE → 自動実行** | ★★★ 開発必要 | ngrok等 $0〜 | △ 設定次第 | ☆☆☆ 将来検討 |

---

## 3. 各方法の詳細調査結果

### 方法1: Claude Code Remote Control（公式） — 最推奨

#### 概要
Anthropicが2026年2月25日にリリースした公式機能。PCで動いているClaude Codeセッションに、スマホやブラウザからリモート接続できる。

#### セットアップ手順（3ステップ、所要時間5分）

**ステップ1: PCで Claude Code を起動**
```bash
cd ~/プロジェクトフォルダ
claude
```

**ステップ2: Remote Controlを有効化**
Claude Codeの中で以下を入力:
```
/remote-control
```
（短縮形: `/rc` でもOK）

→ 画面にQRコードとURLが表示される

**ステップ3: スマホで接続**
- iPhoneのカメラでQRコードを読み取る
- Claudeアプリが開き、そのセッションに接続完了

#### 常時有効化の設定（推奨）
毎回 `/rc` を打つのが面倒な場合、Claude Codeの中で:
```
/config
```
→ 「Enable Remote Control for all sessions」を `true` に設定

これで、claude を起動するたびに自動的にリモート接続可能になる。

#### できること
- スマホからテキスト入力でClaude Codeに指示を出す
- deepdiveスキルの実行指示
- 生成中の進捗をリアルタイムで確認
- ツール実行の承認（「このファイルを編集していいですか？」への回答）
- PCのターミナルとスマホ、両方から同時に操作可能（自動同期）

#### 制限事項
- **PCのターミナルは開いたまま**: ターミナルを閉じるとセッション終了
- **PCがスリープすると切断**: 後述の「スリープ防止」設定が必要
- **ネットワーク切断10分で終了**: Wi-Fiが10分以上切れるとセッション終了
- **1セッション1接続**: 複数セッションを同時リモートはできない

#### セキュリティ
- 通信はすべてAnthropicのサーバー経由でTLS暗号化
- PCにポートを開ける必要なし（外部から直接アクセスされない）
- 一時的な認証情報を使用、自動で期限切れ
- → **セキュリティリスクは低い**

#### 料金
- Claude Proプラン（月$20、約3,000円）で利用可能
- 追加費用なし

#### 注意: 一部ユーザーでエラー報告あり
2026年3月時点で「Remote Control failed」エラーが出るケースが報告されている。リサーチプレビュー段階のため、動作しない場合はAnthropicのサポートに問い合わせが必要。

---

### 方法2: Happy Coder（コミュニティ製アプリ）

#### 概要
オープンソース（MIT）の無料モバイルクライアント。Claude CodeとOpenAI Codexの両方に対応。

#### セットアップ
```bash
npm i -g happy-coder && happy
```
※ npmコマンドが必要（Node.jsのインストールが前提）

#### 特徴
- iOS/Android/Webアプリ対応
- プッシュ通知あり（Remote Controlにはない機能）
- 音声入力対応
- エンドツーエンド暗号化
- 複数セッション並行実行可能

#### 難易度
npmコマンドの実行が必要なため、Remote Controlより一段階難しい。ただし、プッシュ通知機能は魅力的。

#### 公式サイト
https://happy.engineering/

---

### 方法3: Claude Remote（サードパーティiOSアプリ）

#### 概要
MacサーバーアプリとiPhoneアプリの組み合わせ。tmuxによるセッション永続化、Cloudflare Tunnel経由の暗号化接続。

#### セットアップ
1. Macにサーバーアプリをインストール
2. iPhoneにアプリをインストール（現在TestFlight）
3. サーバーURLとAPIキーを入力して接続

#### 特徴
- プッシュ通知対応
- ファイルブラウジング機能
- パーミッション承認のリモート操作

#### 注意点
- TestFlight段階（正式版ではない）
- 将来的に有料化の可能性あり
- Cloudflareアカウント（無料）が必要

#### 公式サイト
https://www.clauderc.com/

---

### 方法4: SSH + Termius（技術者向け）

#### 概要
iPhoneのSSHアプリ（Termius等）でMacに直接接続し、ターミナルを操作する方法。

#### 必要なもの
- Termius（iOS、基本無料/Pro版 $15/月）
- MacのSSH有効化（システム設定 → 共有 → リモートログイン）
- 同じネットワーク内 or Tailscale VPN（外出先から）

#### 難易度: 高
- SSH、tmux、Tailscaleの知識が必要
- スマホの小さい画面でターミナル操作は苦痛
- RIOには非推奨

---

### 方法5: LINE → 自動でClaude Code実行

#### 概要
LINEにメッセージを送ると、自動でMac上のClaude Codeが実行される仕組み。

#### 技術的な仕組み
1. LINE Messaging API でWebhookを設定
2. ngrok等でMacをインターネットに公開
3. Webhookを受信したらClaude Codeをヘッドレスモードで実行
4. 結果をLINE APIで返信

#### 実現可能性
技術的には可能だが、以下の理由でRIOには非推奨:
- ngrokの常時起動が必要
- セキュリティリスク（Macをインターネットに公開）
- 開発・保守コストが高い
- Remote Controlがあれば不要

#### 代替: Claude-Code-Remote（メール/Discord/Telegram経由）
GitHub: https://github.com/JessyTsui/Claude-Code-Remote
- メール返信でClaude Codeに指示を送れるオープンソースツール
- Telegram/Discord経由も対応
- セットアップはやや複雑だが、LINEよりは現実的

---

## 4. RIOへの最終提案

### 「Claude Code Remote Control（公式）」一択

理由:
1. **圧倒的に簡単**: `/rc` コマンド一発 + QRコード読み取りで完了
2. **追加費用ゼロ**: 既にClaude Proを契約していれば追加なし
3. **セキュリティが堅い**: Anthropic公式、TLS暗号化、ポート開放なし
4. **RIOのユースケースに完全合致**: PCでdeepdive開始 → スマホで進捗確認・追加指示
5. **保守不要**: 公式機能なのでアップデートも自動

### 補足: プッシュ通知が欲しい場合
Remote Controlにはプッシュ通知機能がない（2026年3月時点）。
「deepdiveが終わったらスマホに通知してほしい」場合は:
- **Happy Coder**を併用（プッシュ通知あり）
- **Barkアプリ + Claude Code Hooks**で通知設定（やや技術的）
→ まずはRemote Controlだけで始めて、通知が必要と感じたら追加検討

---

## 5. アクションプラン（上から順にやれば完了）

### Phase 1: 基本セットアップ（所要時間10分）

**ステップ1: iPhoneにClaudeアプリをインストール**
- App Storeで「Claude by Anthropic」を検索してダウンロード（無料）
- https://apps.apple.com/us/app/claude-by-anthropic/id6473753684

**ステップ2: Claudeアプリにログイン**
- PCと同じアカウントでログイン（Proプランのアカウント）

**ステップ3: PCでRemote Controlを試す**
- ターミナルでClaude Codeを起動:
  ```bash
  claude
  ```
- Claude Codeの中で入力:
  ```
  /rc
  ```
- 画面にQRコードが表示される
- iPhoneのカメラでQRコードを読み取る
- Claudeアプリでセッションが開く → 成功！

### Phase 2: 常時有効化（所要時間2分）

**ステップ4: 全セッションで自動有効化**
- Claude Codeの中で:
  ```
  /config
  ```
- 「Enable Remote Control for all sessions」を `true` に設定
- これで毎回 `/rc` を打たなくても、自動でリモート接続可能

### Phase 3: PCのスリープ防止（所要時間3分）

外出中もPCが動き続けるための設定。

**ステップ5: Macのスリープを防止**
- 方法A（簡単）: Macの「システム設定」→「ディスプレイとスリープ」→ スリープを「しない」に設定
- 方法B（ターミナル）: Claude Codeを起動する前に以下を実行:
  ```bash
  caffeinate -s &
  ```
  （電源接続中はスリープしない設定。ターミナルを閉じると解除される）

**ステップ6: Macの電源ケーブルを接続しておく**
- バッテリー切れ防止。スリープ防止中は電源接続が必須。

### Phase 4: 実際の運用フロー

**日常の使い方:**
1. PCのターミナルでClaude Codeを起動（`claude`）
2. deepdiveなどの大きなタスクを開始
3. PCから離れる
4. スマホのClaudeアプリを開く → セッション一覧にPCのセッションが表示される
5. タップして接続 → 進捗確認、追加指示、承認操作
6. PCに戻ったらターミナルでそのまま続行

---

## 6. 参考URL一覧

### 公式ドキュメント
- [Remote Control 公式ドキュメント（日本語）](https://code.claude.com/docs/ja/remote-control)
- [Remote Control 公式ドキュメント（英語）](https://code.claude.com/docs/en/remote-control)
- [Claude Code Headless Mode](https://code.claude.com/docs/en/headless)

### 日本語解説記事
- [Claude Code Remote Control でスマホからローカルマシンの作業を継続可能に | DevelopersIO](https://dev.classmethod.jp/articles/claude-coderemotecontrol-enables-you-to-work-on-your-local-machine-from-your-smartphone/)
- [Claude Code のリモートコントロールとスマホ通知の始め方 | Zenn](https://zenn.dev/schroneko/articles/claude-code-remote-control-and-mobile-notification)
- [Claude Code Remote Controlが登場 | Zenn](https://zenn.dev/ubie_dev/articles/claude-code-remote-control-intro)
- [スマホからClaude Codeを操作する | Zenn](https://zenn.dev/fuku_tech/articles/bba079706955fd)
- [Claude Code Remote Control 完全ガイド | note](https://note.com/ai_driven/n/nec0ea1a496cb)
- [カフェから自宅のMacを操る iPhone × Claude Code ガイド | Qiita](https://qiita.com/takao-shimizu/items/4941bb05d59c702795c3)

### 英語解説記事
- [3 Ways to Run Claude Code from Your Phone (2026) | Zilliz](https://zilliz.com/blog/3-easiest-ways-to-use-claude-code-on-your-mobile-phone)
- [Claude Code Remote Control: Code From Your Phone | Medium](https://medium.com/@richardhightower/claude-code-remote-control-code-from-your-phone-3c7059c3b5de)
- [Anthropic just released Remote Control | VentureBeat](https://venturebeat.com/orchestration/anthropic-just-released-a-mobile-version-of-claude-code-called-remote)
- [Claude Code on Your Phone | Builder.io](https://www.builder.io/blog/claude-code-mobile-phone)

### 代替ツール
- [Happy Coder（無料モバイルクライアント）](https://happy.engineering/)
- [Claude Remote（iOS専用サードパーティ）](https://www.clauderc.com/)
- [Claude-Code-Remote（メール/Discord/Telegram経由）](https://github.com/JessyTsui/Claude-Code-Remote)

### Mac設定関連
- [caffeinate コマンドまとめ | D-Box](https://do-zan.com/mac-terminal-caffeinate/)
- [Macをスリープさせない方法 | Zenn](https://zenn.dev/persona/articles/5bd040bc9dd48b)

### 料金
- [Claude 料金プラン公式](https://claude.com/pricing)
- [Claude Code料金ガイド | Zenn](https://zenn.dev/tmasuyama1114/books/claude_code_basic/viewer/pricing-guide)
