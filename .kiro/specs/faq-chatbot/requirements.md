# Requirements Document

## Introduction

FAQチャットボットシステムは、組織内のFAQデータ（Excelファイル形式）および画像を取り込み、ベクトル化して保存し、ユーザーの質問に対してRAG（Retrieval-Augmented Generation）パターンで回答を生成するシステムである。FAQの元データはExcelファイル（.xlsx）で管理され、ETLパイプラインがこれを読み込んでベクトル化する。テキストだけでなく画像コンテンツもベクトル検索の対象とする。フロントエンドはVue.jsで構築し、バックエンドはPython/FastAPIで構築する。ローカル開発環境ではOpenAI GPTモデルを使用し、すべてのリソース（APIキーを除く）をローカルで管理する。Docker環境で動作し、将来的にはGCP/Vertex AIへの移行を想定する。チャット履歴を保存・活用して回答精度を向上させ、DeepEvalを用いた精度評価機能を備える。

## Glossary

- **FAQ_Chatbot**: ユーザーの質問に対してFAQデータベースから関連情報を検索し、LLMを用いて回答を生成するシステム
- **ETL_Pipeline**: FAQソースデータ（Excelファイル）および画像を抽出（Extract）、変換（Transform）、ロード（Load）するデータ処理パイプライン
- **FAQ_Excel**: FAQの元データを格納するExcelファイル（.xlsx形式）。カラム構成は No.、ステータス、親カテゴリ、子カテゴリ、タイトル、本文。行単位でFAQエントリを管理する
- **Vector_Store**: テキストおよび画像の埋め込みベクトルを保存・検索するローカルデータベース
- **Embedding**: テキストまたは画像を数値ベクトルに変換した表現
- **RAG**: Retrieval-Augmented Generation。関連ドキュメントを検索し、その情報をコンテキストとしてLLMに渡して回答を生成する手法
- **Chunk**: ドキュメントを分割した単位テキスト
- **Image_Document**: ベクトル検索対象となる画像ファイルとそのメタデータ（説明テキスト、ファイルパス等）を含むデータ単位
- **LLM_Client**: 大規模言語モデル（OpenAI GPTまたはVertex AI）へのリクエストを抽象化するクライアント
- **Similarity_Search**: ベクトル間のコサイン類似度等を用いて、クエリに最も関連するドキュメントチャンクまたは画像を検索する処理
- **Docker_Environment**: アプリケーションとその依存関係をコンテナとしてパッケージ化し、ローカル環境で一貫した実行環境を提供する仕組み
- **Chat_History**: ユーザーとFAQ_Chatbot間の過去の質問・回答のやり取りを保存したデータ
- **Conversation_Context**: 現在のセッションにおける直近のChat_Historyから構成されるコンテキスト情報
- **DeepEval**: LLMアプリケーションの回答品質を評価するためのPythonフレームワーク
- **Frontend_App**: Vue.jsで構築されたチャットボットのユーザーインターフェース

## Requirements

### Requirement 1: FAQデータの取り込み

**User Story:** As a システム管理者, I want to ExcelファイルのFAQデータをシステムに取り込む, so that チャットボットが回答に利用できるナレッジベースを構築できる

#### Acceptance Criteria

1. WHEN システム管理者がExcelファイル（.xlsx形式）を指定ディレクトリに配置する, THE ETL_Pipeline SHALL 指定ディレクトリ内のすべての対象Excelファイルを読み込む
2. WHEN ETL_Pipeline がExcelファイルを読み込む, THE ETL_Pipeline SHALL ステータスが「公開」の行のみを対象とし、各行のタイトルと本文を結合してChunkとして処理する
3. WHEN ETL_Pipeline がChunkを生成する, THE ETL_Pipeline SHALL 各Chunkにソースファイル名、シート名、行番号、親カテゴリ、子カテゴリのメタデータを付与する
4. IF 指定ディレクトリに対象Excelファイルが存在しない, THEN THE ETL_Pipeline SHALL 明確なエラーメッセージを返す
5. WHEN ETL_Pipeline がデータを処理する, THE ETL_Pipeline SHALL 処理結果（処理件数、エラー件数）をログに記録する

### Requirement 2: テキストのベクトル化と保存

**User Story:** As a システム管理者, I want to FAQデータのChunkをベクトル化してローカルに保存する, so that 類似度検索による高速な情報検索が可能になる

#### Acceptance Criteria

1. WHEN ETL_Pipeline がChunkを生成する, THE ETL_Pipeline SHALL OpenAI Embedding APIを使用して各Chunkのベクトル表現を生成する
2. WHEN ETL_Pipeline がEmbeddingを生成する, THE Vector_Store SHALL 各Embeddingをメタデータとともにローカルファイルベースのデータベースに永続化する
3. WHEN Vector_Store がデータを永続化する, THE Vector_Store SHALL サーバープロセスを必要とせずファイルベースで動作する
4. IF Embedding APIへのリクエストが失敗する, THEN THE ETL_Pipeline SHALL リトライを1回実行し、それでも失敗した場合はエラーを記録して次のChunkの処理を継続する

### Requirement 3: 画像の取り込みとベクトル検索

**User Story:** As a システム管理者, I want to 画像ファイルをベクトル化してナレッジベースに追加する, so that ユーザーが画像コンテンツも含めた検索を行える

#### Acceptance Criteria

1. WHEN システム管理者が画像ファイル（PNG、JPEG形式）を指定ディレクトリに配置する, THE ETL_Pipeline SHALL 指定ディレクトリ内のすべての対象画像ファイルを読み込む
2. WHEN ETL_Pipeline が画像を読み込む, THE ETL_Pipeline SHALL OpenAIのマルチモーダルAPIを使用して画像の説明テキストを生成する
3. WHEN ETL_Pipeline が画像の説明テキストを生成する, THE ETL_Pipeline SHALL 説明テキストのEmbeddingを生成してVector_Storeに保存する
4. WHEN ETL_Pipeline が画像データを保存する, THE ETL_Pipeline SHALL 画像ファイルパス、生成された説明テキスト、ソースファイル名をメタデータとして付与する
5. WHEN Vector_Store が画像関連の検索結果を返す, THE Vector_Store SHALL 結果に画像ファイルパスと説明テキストを含める

### Requirement 4: 類似ドキュメント検索

**User Story:** As a ユーザー, I want to 質問に関連するFAQドキュメントおよび画像を検索する, so that 正確な回答の根拠となる情報を取得できる

#### Acceptance Criteria

1. WHEN ユーザーが質問テキストを送信する, THE FAQ_Chatbot SHALL 質問テキストをEmbeddingに変換する
2. WHEN FAQ_Chatbot が質問のEmbeddingを取得する, THE Vector_Store SHALL コサイン類似度に基づいて上位k件（デフォルト3件）の関連Chunkまたは画像ドキュメントを返す
3. WHEN Vector_Store が検索結果を返す, THE Vector_Store SHALL 各結果にコンテンツ（テキストまたは画像説明）、類似度スコア、ソースメタデータ、コンテンツタイプ（text/image）を含める
4. IF Vector_Store に保存済みデータが存在しない, THEN THE FAQ_Chatbot SHALL 「ナレッジベースが未構築です」というメッセージを返す

### Requirement 5: LLMによる回答生成

**User Story:** As a ユーザー, I want to 質問に対してFAQに基づいた自然な回答を得る, so that 必要な情報を素早く理解できる

#### Acceptance Criteria

1. WHEN FAQ_Chatbot が関連Chunkおよび画像ドキュメントを取得する, THE LLM_Client SHALL 質問テキストと関連コンテンツをプロンプトに組み込んでLLMに送信する
2. WHEN LLM_Client が回答を生成する, THE FAQ_Chatbot SHALL 回答テキストと参照元ソース情報（テキストソースおよび画像ソース）をユーザーに返す
3. IF LLM APIへのリクエストが失敗する, THEN THE FAQ_Chatbot SHALL 「回答の生成に失敗しました。しばらくしてから再度お試しください」というエラーメッセージを返す
4. WHEN LLM_Client がプロンプトを構築する, THE LLM_Client SHALL FAQコンテキストに基づいた回答のみを生成するよう指示するシステムプロンプトを含める

### Requirement 6: チャット履歴の保存と活用

**User Story:** As a ユーザー, I want to 過去のチャット履歴を活用して文脈に沿った回答を得る, so that 会話の流れに基づいたより正確な回答を受け取れる

#### Acceptance Criteria

1. WHEN ユーザーが質問を送信する, THE FAQ_Chatbot SHALL 質問テキストと生成された回答をChat_Historyとしてローカルに保存する
2. WHEN FAQ_Chatbot がプロンプトを構築する, THE FAQ_Chatbot SHALL 同一セッション内の直近N件（デフォルト5件）のChat_HistoryをConversation_Contextとしてプロンプトに含める
3. WHEN Chat_History がConversation_Contextに含まれる, THE LLM_Client SHALL 過去の質問・回答の文脈を考慮した回答を生成する
4. THE FAQ_Chatbot SHALL Chat_Historyをセッション単位でローカルファイルに永続化する
5. WHEN ユーザーが新しいセッションを開始する, THE FAQ_Chatbot SHALL 新しいセッションIDを発行してChat_Historyを初期化する

### Requirement 7: REST APIエンドポイント

**User Story:** As a 開発者, I want to チャットボット機能にREST APIでアクセスする, so that フロントエンドやその他のクライアントから利用できる

#### Acceptance Criteria

1. THE FAQ_Chatbot SHALL POST /api/chat エンドポイントでユーザーの質問とセッションIDを受け付け、回答を返す
2. THE FAQ_Chatbot SHALL POST /api/ingest エンドポイントでETLパイプラインの実行をトリガーする
3. WHEN APIリクエストのバリデーションが失敗する, THE FAQ_Chatbot SHALL HTTPステータスコード422と詳細なエラーメッセージを返す
4. THE FAQ_Chatbot SHALL GET /api/health エンドポイントでシステムの稼働状態を返す
5. THE FAQ_Chatbot SHALL POST /api/session エンドポイントで新しいチャットセッションを作成しセッションIDを返す

### Requirement 8: LLMクライアントの抽象化

**User Story:** As a 開発者, I want to LLMクライアントを抽象化する, so that OpenAI GPTからVertex AIへの切り替えを最小限のコード変更で実現できる

#### Acceptance Criteria

1. THE LLM_Client SHALL 共通インターフェースを通じてチャット補完とEmbedding生成の機能を提供する
2. WHEN 環境設定でプロバイダーが指定される, THE LLM_Client SHALL 指定されたプロバイダー（OpenAIまたはVertex AI）の実装を使用する
3. WHEN LLM_Client がレスポンスを返す, THE LLM_Client SHALL プロバイダーに依存しない統一されたレスポンス形式で返す

### Requirement 9: チャンク・画像データのシリアライゼーション

**User Story:** As a 開発者, I want to Chunkデータおよび画像ドキュメントデータを正確にシリアライズ・デシリアライズする, so that データの永続化と復元が正確に行われる

#### Acceptance Criteria

1. WHEN ETL_Pipeline がChunkまたはImage_Documentを生成する, THE ETL_Pipeline SHALL データ（テキスト/説明テキスト、メタデータ、Embedding）をJSON形式でシリアライズする
2. WHEN Vector_Store がデータを読み込む, THE Vector_Store SHALL JSON形式のデータを元のChunkまたはImage_Documentオブジェクトにデシリアライズする
3. WHEN データをシリアライズしてデシリアライズする, THE FAQ_Chatbot SHALL 元のオブジェクトと同一の内容を復元する

### Requirement 10: 設定管理

**User Story:** As a 開発者, I want to システムの設定を一元管理する, so that 環境ごとの設定変更を容易に行える

#### Acceptance Criteria

1. THE FAQ_Chatbot SHALL 環境変数または設定ファイルからAPIキー、モデル名、チャンクサイズ等の設定を読み込む
2. WHEN 必須の設定値が未設定の場合, THE FAQ_Chatbot SHALL 起動時に明確なエラーメッセージを表示して起動を中止する
3. THE FAQ_Chatbot SHALL デフォルト値を持つ設定項目についてはデフォルト値を適用する

### Requirement 11: Docker環境

**User Story:** As a 開発者, I want to ローカル開発環境をDockerで構築する, so that チームメンバー全員が同一の環境で開発・検証を行える

#### Acceptance Criteria

1. THE Docker_Environment SHALL docker-compose.ymlを使用してFAQ_Chatbotアプリケーション（バックエンドおよびフロントエンド）を単一コマンドで起動する
2. WHEN Docker_Environment がコンテナを起動する, THE Docker_Environment SHALL Vector_Storeのデータディレクトリをホストマシンにマウントして永続化する
3. WHEN Docker_Environment がコンテナを起動する, THE Docker_Environment SHALL FAQソースExcelファイルおよび画像のディレクトリをホストマシンからマウントする
4. THE Docker_Environment SHALL .envファイルからAPIキー等の環境変数を読み込む
5. WHEN Dockerfileがビルドされる, THE Docker_Environment SHALL 依存パッケージを各サービスの設定ファイルに基づいてインストールする

### Requirement 12: Vue.jsフロントエンド

**User Story:** As a ユーザー, I want to ブラウザ上でチャットボットと対話する, so that 直感的なインターフェースでFAQの回答を得られる

#### Acceptance Criteria

1. THE Frontend_App SHALL チャットメッセージの入力欄と送信ボタンを表示する
2. WHEN ユーザーがメッセージを送信する, THE Frontend_App SHALL POST /api/chat エンドポイントにリクエストを送信し、回答を表示する
3. WHEN FAQ_Chatbot が画像ソースを含む回答を返す, THE Frontend_App SHALL 回答内に画像のサムネイルまたはリンクを表示する
4. WHEN ユーザーがページを開く, THE Frontend_App SHALL 新しいセッションを作成し、以降の質問にセッションIDを付与する
5. THE Frontend_App SHALL 会話履歴をチャット形式で時系列に表示する

### Requirement 13: DeepEvalによる精度評価

**User Story:** As a 開発者, I want to チャットボットの回答精度をDeepEvalで評価する, so that RAGパイプラインの品質を定量的に測定・改善できる

#### Acceptance Criteria

1. THE FAQ_Chatbot SHALL DeepEvalフレームワークを使用して回答の精度評価を実行するCLIコマンドを提供する
2. WHEN 精度評価が実行される, THE FAQ_Chatbot SHALL 評価用テストケース（質問、期待回答、コンテキスト）をJSONファイルから読み込む
3. WHEN 精度評価が実行される, THE FAQ_Chatbot SHALL Faithfulness（忠実性）、Answer Relevancy（回答関連性）、Contextual Relevancy（コンテキスト関連性）の指標を計算する
4. WHEN 精度評価が完了する, THE FAQ_Chatbot SHALL 各指標のスコアと全体サマリーをJSON形式で出力する
5. WHEN 評価用テストケースファイルが存在しない, THE FAQ_Chatbot SHALL テストケースのテンプレートファイルを生成する
