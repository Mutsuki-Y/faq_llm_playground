"""RAG evaluation using DeepEval framework."""

import json
import logging
from pathlib import Path

from config import AppConfig
from deepeval import evaluate
from deepeval.metrics import (AnswerRelevancyMetric, ContextualRelevancyMetric,
                              FaithfulnessMetric)
from deepeval.synthesizer import Synthesizer
from deepeval.test_case import LLMTestCase
from etl.excel_reader import ExcelReader
from models import EvalTestCase, EvaluationResult

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """DeepEvalを使用したRAGパイプラインの精度評価。

    Faithfulness、Answer Relevancy、Contextual Relevancyの3指標を計算する。
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def run_evaluation(self, test_cases_path: Path) -> EvaluationResult:
        """テストケースJSONを読み込んで精度評価を実行する。

        Args:
            test_cases_path: テストケースJSONファイルのパス

        Returns:
            各指標のスコアとサマリーを含むEvaluationResult
        """
        # テストケース読み込み
        with open(test_cases_path, "r", encoding="utf-8") as f:
            raw_cases = json.load(f)

        test_cases = [EvalTestCase.model_validate(tc) for tc in raw_cases]

        # DeepEval用テストケースに変換
        deepeval_cases = []
        for tc in test_cases:
            deepeval_cases.append(
                LLMTestCase(
                    input=tc.question,
                    actual_output=tc.expected_answer,
                    retrieval_context=tc.context,
                )
            )

        # メトリクス定義
        faithfulness = FaithfulnessMetric(model=self._config.openai_model)
        answer_relevancy = AnswerRelevancyMetric(model=self._config.openai_model)
        contextual_relevancy = ContextualRelevancyMetric(model=self._config.openai_model)

        # 評価実行
        results = evaluate(
            test_cases=deepeval_cases,
            metrics=[faithfulness, answer_relevancy, contextual_relevancy],
        )

        # スコア集計
        faith_scores = []
        relevancy_scores = []
        ctx_scores = []

        for result in results.test_results:
            for metric_data in result.metrics_data:
                if metric_data.name == "Faithfulness":
                    faith_scores.append(metric_data.score or 0.0)
                elif metric_data.name == "Answer Relevancy":
                    relevancy_scores.append(metric_data.score or 0.0)
                elif metric_data.name == "Contextual Relevancy":
                    ctx_scores.append(metric_data.score or 0.0)

        avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else 0.0
        avg_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0.0
        avg_ctx = sum(ctx_scores) / len(ctx_scores) if ctx_scores else 0.0

        return EvaluationResult(
            faithfulness=avg_faith,
            answer_relevancy=avg_relevancy,
            contextual_relevancy=avg_ctx,
            summary={
                "total_cases": len(test_cases),
                "faithfulness_scores": faith_scores,
                "answer_relevancy_scores": relevancy_scores,
                "contextual_relevancy_scores": ctx_scores,
            },
        )

    def generate_template(self, output_path: Path) -> None:
        """テストケースのテンプレートJSONファイルを生成する。

        Args:
            output_path: 出力先ファイルパス
        """
        template = [
            {
                "question": "VPNに接続できない場合はどうすればよいですか？",
                "expected_answer": "VPNクライアントを再起動し、ネットワーク設定を確認してください。",
                "context": [
                    "VPN接続のトラブルシューティング: まずVPNクライアントを再起動してください。",
                    "ネットワーク設定でプロキシが正しく設定されているか確認してください。",
                ],
            },
            {
                "question": "パスワードをリセットするにはどうすればよいですか？",
                "expected_answer": "パスワードリセットページからメールアドレスを入力してリセットリンクを受け取ってください。",
                "context": [
                    "パスワードリセット手順: パスワードリセットページにアクセスし、登録メールアドレスを入力します。",
                ],
            },
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        logger.info("テストケーステンプレートを生成しました: %s", output_path)

    def generate_auto(
        self,
        output_path: Path,
        max_goldens_per_context: int = 2,
    ) -> int:
        """取り込み済みFAQデータからテストケースを自動生成する。

        DeepEvalのSynthesizerを使用して、FAQのChunkテキストをコンテキストとして
        質問・期待回答のペアを自動生成する。

        Args:
            output_path: 生成したテストケースの出力先JSONファイルパス
            max_goldens_per_context: コンテキストあたりの最大生成数

        Returns:
            生成されたテストケース数
        """
        # FAQデータを読み込み
        reader = ExcelReader()
        faq_dir = Path(self._config.faq_data_dir)
        all_chunks_text: list[list[str]] = []
        source_files: list[str] = []

        if not faq_dir.exists():
            raise FileNotFoundError(f"FAQデータディレクトリが見つかりません: {faq_dir}")

        xlsx_files = list(faq_dir.glob("*.xlsx"))
        if not xlsx_files:
            raise FileNotFoundError(f"FAQデータディレクトリにExcelファイルがありません: {faq_dir}")

        for xlsx_path in xlsx_files:
            entries = reader.read_faq_excel(xlsx_path)
            published = reader.filter_published(entries)
            for entry in published:
                chunk = reader.faq_entry_to_chunk(entry)
                all_chunks_text.append([chunk.text])
                source_files.append(xlsx_path.name)

        if not all_chunks_text:
            raise ValueError("公開ステータスのFAQエントリが見つかりません")

        logger.info(
            "%d 件のFAQエントリからテストケースを自動生成します...",
            len(all_chunks_text),
        )

        # DeepEval Synthesizerでテストケース生成
        synthesizer = Synthesizer(model=self._config.openai_model)
        goldens = synthesizer.generate_goldens_from_contexts(
            contexts=all_chunks_text,
            include_expected_output=True,
            max_goldens_per_context=max_goldens_per_context,
            source_files=source_files,
        )

        # EvalTestCase形式に変換して保存
        test_cases = []
        for g in goldens:
            test_cases.append({
                "question": g.input or "",
                "expected_answer": g.expected_output or "",
                "context": g.context or [],
            })

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)

        logger.info(
            "%d 件のテストケースを生成しました: %s",
            len(test_cases),
            output_path,
        )
        return len(test_cases)
